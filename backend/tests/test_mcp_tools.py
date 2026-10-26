"""MCP: discovery, invocation, authorization, scoping, and audit."""

from __future__ import annotations

import math
import uuid

import pytest
import pytest_asyncio
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.agents.deps import CompanyContext, GhostBoardDeps
from app.agents.factory import build_bundle, reset_agent_cache
from app.agents.registry import REGISTRY, AgentId, ToolScope
from app.mcp import server as server_mod
from app.mcp.context import ToolAuthorizationError, ToolContext, bind_context, current_context
from app.mcp.server import TOOL_SCOPES, build_mcp_server, tools_for_scopes
from app.mcp.tools import company as company_mod
from app.mcp.tools.financial import (
    FinancialScenario,
    RunwayInput,
    ScenarioComparisonInput,
    UnitEconomicsInput,
    calculate_cash_runway,
    calculate_unit_economics,
    compare_financial_scenarios,
)
from app.mcp.tools.operations import (
    CapacityInput,
    DependencyInput,
    DependencyTask,
    ImplementationPlanInput,
    PlanTask,
    WorkstreamLoad,
    assess_execution_capacity,
    build_implementation_plan,
    identify_operational_dependencies,
)
from app.models.enums import ToolInvocationStatus
from app.models.meeting import ToolInvocation


@pytest.fixture(autouse=True)
def _clear_cache():
    reset_agent_cache()
    yield
    reset_agent_cache()


@pytest_asyncio.fixture
async def tool_sessions(db_connection, monkeypatch):
    """Point the tools' own session factories at the test transaction."""
    maker = async_sessionmaker(
        bind=db_connection,
        expire_on_commit=False,
        autoflush=False,
        join_transaction_mode="create_savepoint",
    )
    monkeypatch.setattr(company_mod, "AsyncSessionLocal", maker)
    monkeypatch.setattr(server_mod, "AsyncSessionLocal", maker)
    return maker


def ctx_for(agent_id: AgentId, organization_id: uuid.UUID) -> ToolContext:
    return ToolContext(
        organization_id=organization_id,
        agent_id=agent_id,
        allowed_scopes=frozenset(REGISTRY[agent_id].tool_scopes),
    )


# --------------------------------------------------------------------------
# Financial calculations
# --------------------------------------------------------------------------


def test_runway_is_cash_over_burn():
    result = calculate_cash_runway(
        RunwayInput(cash_on_hand_usd=3_000_000, monthly_burn_usd=250_000)
    )
    assert result.runway_months == 12.0
    assert result.baseline_runway_months == 12.0
    assert "3,000,000" in result.calculation and "250,000" in result.calculation


def test_cutting_burn_extends_runway():
    result = calculate_cash_runway(
        RunwayInput(
            cash_on_hand_usd=3_000_000,
            monthly_burn_usd=250_000,
            monthly_burn_change_usd=-75_000,
        )
    )
    assert result.net_monthly_burn_usd == 175_000
    assert result.runway_months == pytest.approx(17.1, abs=0.1)
    assert result.change_in_runway_months > 5


def test_revenue_growth_offsets_burn():
    result = calculate_cash_runway(
        RunwayInput(
            cash_on_hand_usd=1_000_000,
            monthly_burn_usd=100_000,
            expected_monthly_revenue_growth_usd=40_000,
        )
    )
    assert result.net_monthly_burn_usd == 60_000
    assert result.runway_months == pytest.approx(16.7, abs=0.1)


def test_non_positive_burn_is_reported_not_divided_by():
    result = calculate_cash_runway(
        RunwayInput(
            cash_on_hand_usd=500_000,
            monthly_burn_usd=50_000,
            expected_monthly_revenue_growth_usd=60_000,
        )
    )
    assert result.runway_months == math.inf
    assert "not bounded" in result.calculation
    assert any("not infinite in practice" in c for c in result.caveats)


def test_runway_rejects_impossible_inputs():
    with pytest.raises(ValueError):
        RunwayInput(cash_on_hand_usd=-1, monthly_burn_usd=250_000)
    with pytest.raises(ValueError):
        RunwayInput(cash_on_hand_usd=100, monthly_burn_usd=0)


def test_unit_economics_matches_hand_calculation():
    result = calculate_unit_economics(
        UnitEconomicsInput(
            average_revenue_per_account_usd=12_000,
            gross_margin_rate=0.75,
            customer_acquisition_cost_usd=9_000,
            annual_churn_rate=0.15,
        )
    )
    # Lifetime 1/0.15 = 6.67y; annual GP 9,000; LTV 60,000; ratio 6.67
    assert result.average_customer_lifetime_years == pytest.approx(6.67, abs=0.01)
    assert result.lifetime_gross_profit_usd == pytest.approx(60_000, rel=0.01)
    assert result.ltv_to_cac_ratio == pytest.approx(6.67, abs=0.01)
    assert result.cac_payback_months == pytest.approx(12.0, abs=0.1)


def test_unit_economics_labels_rules_of_thumb_as_such():
    """The spec forbids presenting industry guidelines as facts."""
    result = calculate_unit_economics(
        UnitEconomicsInput(
            average_revenue_per_account_usd=1_000,
            gross_margin_rate=0.5,
            customer_acquisition_cost_usd=5_000,
            annual_churn_rate=0.5,
        )
    )
    assert result.ltv_to_cac_ratio < 3
    assert any("rules of thumb" in c for c in result.caveats)


def test_scenario_comparison_ranks_by_runway():
    result = compare_financial_scenarios(
        ScenarioComparisonInput(
            cash_on_hand_usd=3_000_000,
            monthly_burn_usd=250_000,
            scenarios=[
                FinancialScenario(name="status quo"),
                FinancialScenario(name="cut 30%", monthly_burn_change_usd=-75_000),
                FinancialScenario(
                    name="launch", monthly_burn_change_usd=80_000, one_off_cost_usd=200_000
                ),
            ],
        )
    )
    assert result.baseline_runway_months == 12.0
    assert result.longest_runway == "cut 30%"
    by_name = {o.name: o for o in result.outcomes}
    assert by_name["launch"].cash_after_one_off_usd == 2_800_000
    assert by_name["launch"].runway_months < 12.0
    assert "ignores what the spend would buy" in result.calculation_note


def test_scenario_comparison_invents_no_extra_scenarios():
    result = compare_financial_scenarios(
        ScenarioComparisonInput(
            cash_on_hand_usd=1_000_000,
            monthly_burn_usd=100_000,
            scenarios=[FinancialScenario(name="only one")],
        )
    )
    assert [o.name for o in result.outcomes] == ["only one"]


# --------------------------------------------------------------------------
# Operations calculations
# --------------------------------------------------------------------------


def test_capacity_accounts_for_existing_commitments():
    result = assess_execution_capacity(
        CapacityInput(
            available_people=10,
            weeks_available=12,
            existing_commitment_rate=0.7,
            workstreams=[WorkstreamLoad(name="retention", required_person_weeks=30)],
        )
    )
    # 10 people * 12 weeks * 30% free = 36 person-weeks
    assert result.available_person_weeks == 36.0
    assert result.required_person_weeks == 30.0
    assert result.feasible is True
    assert "tight" in result.verdict.lower()


def test_capacity_reports_infeasibility_with_the_shortfall():
    result = assess_execution_capacity(
        CapacityInput(
            available_people=4,
            weeks_available=10,
            existing_commitment_rate=0.5,
            workstreams=[WorkstreamLoad(name="launch", required_person_weeks=60)],
        )
    )
    assert result.feasible is False
    assert result.surplus_person_weeks == -40.0
    assert "Not feasible" in result.verdict


def test_dependencies_are_ordered_into_parallel_stages():
    result = identify_operational_dependencies(
        DependencyInput(
            tasks=[
                DependencyTask(id="a", name="Diagnose churn", duration_weeks=2),
                DependencyTask(id="b", name="Fix onboarding", depends_on=["a"], duration_weeks=3),
                DependencyTask(id="c", name="Survey customers", depends_on=["a"], duration_weeks=1),
                DependencyTask(id="d", name="Measure", depends_on=["b", "c"], duration_weeks=1),
            ]
        )
    )
    assert result.has_cycle is False
    assert result.ordered_stages == [["a"], ["b", "c"], ["d"]]
    assert result.critical_path == ["a", "b", "d"]
    assert result.critical_path_weeks == 6.0
    assert "a" in result.blocking_tasks


def test_dependency_cycles_are_reported_not_raised():
    """A circular plan is a finding the COO should surface, not a crash."""
    result = identify_operational_dependencies(
        DependencyInput(
            tasks=[
                DependencyTask(id="x", name="X", depends_on=["y"]),
                DependencyTask(id="y", name="Y", depends_on=["x"]),
            ]
        )
    )
    assert result.has_cycle is True
    assert sorted(result.blocking_tasks) == ["x", "y"]
    assert result.critical_path == []


def test_unknown_dependency_references_are_surfaced():
    result = identify_operational_dependencies(
        DependencyInput(tasks=[DependencyTask(id="a", name="A", depends_on=["ghost"])])
    )
    assert result.unresolved_dependencies == ["a -> ghost"]
    assert result.has_cycle is False


def test_implementation_plan_uses_relative_windows_only():
    result = build_implementation_plan(
        ImplementationPlanInput(
            objective="Reduce churn",
            tasks=[
                PlanTask(description="Diagnose churn", owner="Customer", effort_weeks=3),
                PlanTask(description="Ship fixes", owner="Eng", effort_weeks=4),
                PlanTask(description="Measure", effort_weeks=2),
            ],
        )
    )
    assert [p.window for p in result.phases] == ["0-30 days", "30-60 days", "60-90 days"]
    joined = " ".join(n for n in result.notes)
    assert "does not know" in joined
    # No calendar dates anywhere in the output.
    assert "2026" not in str(result.model_dump())


def test_over_scoped_plans_report_what_did_not_fit():
    result = build_implementation_plan(
        ImplementationPlanInput(
            objective="Too much",
            tasks=[PlanTask(description=f"Task {i}", effort_weeks=4) for i in range(6)],
            weeks_per_phase=4.0,
        )
    )
    assert result.unscheduled_tasks
    assert any("over-scoped" in n for n in result.notes)


# --------------------------------------------------------------------------
# Authorization
# --------------------------------------------------------------------------


def test_no_tool_accepts_an_organization_id():
    """The spec forbids trusting a model-supplied org id. The strongest form
    of that is giving the model nowhere to put one."""
    import inspect

    from app.mcp.tools import company, financial, operations

    for module in (company, financial, operations):
        for name in TOOL_SCOPES:
            func = getattr(module, name, None)
            if func is None:
                continue
            params = set(inspect.signature(func).parameters)
            assert "organization_id" not in params, f"{name} accepts an org id"
            assert "org_id" not in params, f"{name} accepts an org id"


def test_tool_scopes_cover_every_registered_tool():
    mcp = build_mcp_server()
    assert set(TOOL_SCOPES) == {
        "get_company_profile",
        "get_company_goals",
        "search_company_knowledge",
        "get_previous_decisions",
        "calculate_cash_runway",
        "calculate_unit_economics",
        "compare_financial_scenarios",
        "assess_execution_capacity",
        "identify_operational_dependencies",
        "build_implementation_plan",
    }
    assert mcp.name == "ghost-board"


def test_each_role_sees_only_its_own_tools():
    cfo = tools_for_scopes(tuple(REGISTRY[AgentId.CFO].tool_scopes))
    coo = tools_for_scopes(tuple(REGISTRY[AgentId.COO].tool_scopes))
    advocate = tools_for_scopes(tuple(REGISTRY[AgentId.CUSTOMER_ADVOCATE].tool_scopes))

    assert "calculate_cash_runway" in cfo
    assert "assess_execution_capacity" not in cfo

    assert "assess_execution_capacity" in coo
    assert "calculate_cash_runway" not in coo

    # The Customer Advocate holds only the company scope.
    assert advocate == tools_for_scopes((ToolScope.COMPANY,))
    assert "calculate_unit_economics" not in advocate


def test_context_require_rejects_an_unheld_scope():
    ctx = ToolContext(
        organization_id=uuid.uuid4(),
        agent_id=AgentId.COO,
        allowed_scopes=frozenset({ToolScope.OPERATIONS}),
    )
    ctx.require(ToolScope.OPERATIONS, "assess_execution_capacity")
    with pytest.raises(ToolAuthorizationError, match="not authorized"):
        ctx.require(ToolScope.FINANCIAL, "calculate_cash_runway")


def test_tools_fail_closed_with_no_bound_context():
    with pytest.raises(ToolAuthorizationError, match="No tool context"):
        current_context()


async def test_company_tool_refuses_to_run_unscoped(tool_sessions):
    from app.mcp.tools.company import get_company_profile

    with pytest.raises(ToolAuthorizationError):
        await get_company_profile()


# --------------------------------------------------------------------------
# Company tools against the database
# --------------------------------------------------------------------------


async def test_company_profile_tool_reads_the_scoped_organization(
    db, org_and_user, tool_sessions
):
    from app.mcp.tools.company import get_company_profile

    org, _ = org_and_user
    with bind_context(ctx_for(AgentId.CFO, org.id)):
        result = await get_company_profile()

    assert result.found is True
    assert result.company_name == "Northstar Labs"
    assert result.arr_usd == 2_000_000
    assert result.monthly_burn_usd == 250_000


async def test_company_profile_tool_is_scoped_to_the_bound_org(
    db, org_and_user, tool_sessions
):
    """A different organization sees nothing, even with the same tool."""
    from app.mcp.tools.company import get_company_profile

    with bind_context(ctx_for(AgentId.CFO, uuid.uuid4())):
        result = await get_company_profile()

    assert result.found is False
    assert "Do not invent figures" in result.note


async def test_profile_tool_names_what_it_does_not_know(db, org_and_user, tool_sessions):
    from app.mcp.tools.company import get_company_profile
    from app.models.identity import CompanyProfile

    org, _ = org_and_user
    profile = (
        await db.execute(
            select(CompanyProfile).where(CompanyProfile.organization_id == org.id)
        )
    ).scalar_one()
    profile.industry = None
    await db.flush()

    with bind_context(ctx_for(AgentId.CFO, org.id)):
        result = await get_company_profile()

    assert "industry" in result.missing_fields
    assert "unknown" in result.note


async def test_goals_tool_returns_recorded_goals(db, org_and_user, tool_sessions):
    from app.mcp.tools.company import get_company_goals

    org, _ = org_and_user
    with bind_context(ctx_for(AgentId.CEO, org.id)):
        result = await get_company_goals()

    assert "Sustainable growth" in result.goals
    assert "Choosing the next strategic priority" in result.challenges


async def test_knowledge_search_says_so_when_it_finds_nothing(
    db, org_and_user, tool_sessions
):
    from app.mcp.tools.company import search_company_knowledge

    org, _ = org_and_user
    with bind_context(ctx_for(AgentId.CEO, org.id)):
        result = await search_company_knowledge("quantum teleportation revenue")

    assert result.hits == []
    assert "do not" in result.note.lower()


async def test_knowledge_search_returns_provenance(db, org_and_user, tool_sessions):
    from app.mcp.tools.company import search_company_knowledge
    from app.models.enums import FactSource
    from app.models.memory import CompanyMemory

    org, _ = org_and_user
    db.add(
        CompanyMemory(
            organization_id=org.id,
            key="churn_driver",
            value="Churn concentrates in customers who never completed onboarding.",
            source_kind=FactSource.USER_CONFIRMED,
        )
    )
    await db.flush()

    with bind_context(ctx_for(AgentId.CUSTOMER_ADVOCATE, org.id)):
        result = await search_company_knowledge("onboarding")

    assert len(result.hits) == 1
    assert result.hits[0].provenance == "user_confirmed"
    assert "onboarding" in result.hits[0].excerpt


async def test_previous_decisions_tool_is_empty_before_any_meeting(
    db, org_and_user, tool_sessions
):
    from app.mcp.tools.company import get_previous_decisions

    org, _ = org_and_user
    with bind_context(ctx_for(AgentId.CEO, org.id)):
        result = await get_previous_decisions()

    assert result.decisions == []
    assert "not decided anything yet" in result.note


# --------------------------------------------------------------------------
# Discovery and invocation through the MCP protocol
# --------------------------------------------------------------------------


#: A minimally valid ConsultationResponse, used to end a tool-calling run.
_FINAL_OUTPUT = {
    "answer": "Answered using the tool result.",
    "key_points": [],
    "assumptions": [],
    "risks": [],
    "open_questions": [],
    "recommended_actions": [],
    "confidence_level": "medium",
    "out_of_scope": False,
    "refer_to_agent_id": None,
}


def _tool_calling_model(tool_name: str, args: dict):
    """A model that calls one tool, then closes with a valid structured output.

    The second turn has to go through the output tool: these agents have a
    structured output type, so returning plain text would fail validation and
    the test would be measuring the wrong thing.
    """
    seen: dict = {"offered": [], "result": None}
    state = {"n": 0}

    def fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        state["n"] += 1
        if state["n"] == 1:
            seen["offered"] = [t.name for t in (info.function_tools or [])]
            return ModelResponse(parts=[ToolCallPart(tool_name, args)])

        for part in messages[-1].parts:
            if part.part_kind in ("tool-return", "retry-prompt"):
                seen["result"] = getattr(part, "content", None)

        if info.output_tools:
            return ModelResponse(
                parts=[ToolCallPart(info.output_tools[0].name, _FINAL_OUTPUT)]
            )
        return ModelResponse(parts=[TextPart("done")])

    return seen, FunctionModel(fn)


async def test_cfo_discovers_its_tools_over_mcp(db, org_and_user, tool_sessions):
    org, _ = org_and_user
    seen, model = _tool_calling_model(
        "calculate_cash_runway",
        {"data": {"cash_on_hand_usd": 3_000_000, "monthly_burn_usd": 250_000}},
    )
    definition = REGISTRY[AgentId.CFO]
    bundle = build_bundle(definition, model)

    with bind_context(ctx_for(AgentId.CFO, org.id)):
        async with bundle.consultation_agent:
            await bundle.consultation_agent.run(
                "What is our runway?",
                deps=GhostBoardDeps(
                    organization_id=org.id,
                    user_id=None,
                    agent_id=AgentId.CFO,
                    company=CompanyContext(company_name="Northstar Labs"),
                    allowed_tool_scopes=tuple(definition.tool_scopes),
                ),
            )

    assert "calculate_cash_runway" in seen["offered"]
    assert "assess_execution_capacity" not in seen["offered"]


async def test_an_executive_really_invokes_a_tool_and_gets_the_result(
    db, org_and_user, tool_sessions
):
    """Phase 5 acceptance: discovered over MCP, invoked, result used."""
    org, _ = org_and_user
    seen, model = _tool_calling_model(
        "calculate_cash_runway",
        {"data": {"cash_on_hand_usd": 3_000_000, "monthly_burn_usd": 250_000}},
    )
    definition = REGISTRY[AgentId.CFO]
    bundle = build_bundle(definition, model)

    with bind_context(ctx_for(AgentId.CFO, org.id)):
        async with bundle.consultation_agent:
            await bundle.consultation_agent.run(
                "What is our runway?",
                deps=GhostBoardDeps(
                    organization_id=org.id,
                    user_id=None,
                    agent_id=AgentId.CFO,
                    allowed_tool_scopes=tuple(definition.tool_scopes),
                ),
            )

    assert seen["result"] is not None
    payload = seen["result"]
    text = str(payload)
    assert "12.0" in text or "12" in text
    assert "3,000,000" in text


async def test_every_invocation_is_audited(db, org_and_user, tool_sessions):
    org, _ = org_and_user
    _, model = _tool_calling_model(
        "calculate_cash_runway",
        {"data": {"cash_on_hand_usd": 1_000_000, "monthly_burn_usd": 100_000}},
    )
    definition = REGISTRY[AgentId.CFO]
    bundle = build_bundle(definition, model)

    with bind_context(ctx_for(AgentId.CFO, org.id)):
        async with bundle.consultation_agent:
            await bundle.consultation_agent.run(
                "runway?",
                deps=GhostBoardDeps(
                    organization_id=org.id,
                    user_id=None,
                    agent_id=AgentId.CFO,
                    allowed_tool_scopes=tuple(definition.tool_scopes),
                ),
            )

    rows = (
        (
            await db.execute(
                select(ToolInvocation).where(ToolInvocation.organization_id == org.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    row = rows[0]
    assert row.tool_name == "calculate_cash_runway"
    assert row.agent_id == "cfo"
    assert row.status is ToolInvocationStatus.SUCCEEDED
    assert row.result["runway_months"] == 10.0
    assert row.duration_ms is not None


async def test_a_tool_outside_the_agents_remit_is_denied_and_recorded(
    db, org_and_user, tool_sessions
):
    """Defence in depth: even if filtering were bypassed, the server refuses."""
    org, _ = org_and_user
    mcp = build_mcp_server()
    _seen, model = _tool_calling_model(
        "assess_execution_capacity",
        {
            "data": {
                "available_people": 5,
                "weeks_available": 10,
                "workstreams": [{"name": "x", "required_person_weeks": 10}],
            }
        },
    )
    # Unfiltered toolset: every tool is offered regardless of role.
    agent = Agent(model, toolsets=[MCPToolset(mcp)])

    with bind_context(ctx_for(AgentId.CFO, org.id)):  # CFO holds no operations scope
        async with agent:
            await agent.run("try it")

    rows = (
        (
            await db.execute(
                select(ToolInvocation).where(
                    ToolInvocation.organization_id == org.id,
                    ToolInvocation.tool_name == "assess_execution_capacity",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].status is ToolInvocationStatus.DENIED
    assert "not authorized" in rows[0].error_message


async def test_a_failing_tool_surfaces_an_error_rather_than_an_empty_result(
    db, org_and_user, tool_sessions
):
    org, _ = org_and_user
    seen, model = _tool_calling_model(
        "calculate_cash_runway",
        {"data": {"cash_on_hand_usd": -5, "monthly_burn_usd": 100}},  # invalid
    )
    definition = REGISTRY[AgentId.CFO]
    bundle = build_bundle(definition, model)

    with bind_context(ctx_for(AgentId.CFO, org.id)):
        async with bundle.consultation_agent:
            await bundle.consultation_agent.run(
                "runway?",
                deps=GhostBoardDeps(
                    organization_id=org.id,
                    user_id=None,
                    agent_id=AgentId.CFO,
                    allowed_tool_scopes=tuple(definition.tool_scopes),
                ),
            )

    # The model saw a validation error, not a fabricated success.
    assert seen["result"] is not None
    assert "valid" in str(seen["result"]).lower() or "error" in str(seen["result"]).lower()
