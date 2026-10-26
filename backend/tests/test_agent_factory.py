"""The agent layer: nine separate agents, each genuinely its own.

These are the assertions that would catch the failure mode the spec warns
about most loudly — one model call impersonating several executives.
"""

from __future__ import annotations

import uuid

import pytest
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from app.agents.deps import CompanyContext, GhostBoardDeps
from app.agents.factory import build_bundle, get_bundle, reset_agent_cache
from app.agents.prompts import ROLE_INSTRUCTIONS
from app.agents.registry import REGISTRY, ROSTER, AgentId
from app.agents.schemas import AgentAssessmentOutput, ConsultationResponse
from tests.capture import recorder_model


@pytest.fixture(autouse=True)
def _clear_cache():
    reset_agent_cache()
    yield
    reset_agent_cache()


def _deps(definition) -> GhostBoardDeps:
    return GhostBoardDeps(
        organization_id=uuid.uuid4(),
        user_id=None,
        agent_id=definition.agent_id,
        company=CompanyContext(company_name="Northstar Labs", arr_usd=2_000_000),
        allowed_tool_scopes=tuple(definition.tool_scopes),
    )


def test_every_roster_executive_has_role_instructions():
    assert set(ROLE_INSTRUCTIONS) == set(AgentId)
    for agent_id, text in ROLE_INSTRUCTIONS.items():
        assert len(text) > 300, f"{agent_id} instructions are too thin to differentiate it"


def test_role_instructions_are_all_different():
    assert len(set(ROLE_INSTRUCTIONS.values())) == 9


def test_each_executive_builds_its_own_agent_instances():
    bundles = [build_bundle(d, TestModel()) for d in ROSTER]
    agents = [b.consultation_agent for b in bundles]

    assert len(bundles) == 9
    # Nine distinct Agent objects, not one reused with a swapped prompt.
    assert len({id(a) for a in agents}) == 9
    assert all(isinstance(a, Agent) for a in agents)


def test_agents_are_named_per_executive():
    for definition in ROSTER:
        bundle = build_bundle(definition, TestModel())
        assert bundle.consultation_agent.name == f"ghostboard-{definition.agent_id.value}"


def test_output_types_are_the_structured_schemas():
    bundle = build_bundle(REGISTRY[AgentId.CFO], TestModel())
    assert bundle.consultation_agent.output_type is ConsultationResponse
    assert bundle.assessment_agent.output_type is AgentAssessmentOutput


@pytest.mark.parametrize("definition", ROSTER, ids=lambda d: d.agent_id.value)
async def test_agent_sends_its_own_identity_and_role_text_to_the_model(definition):
    """Read back the instructions the provider would actually have received."""
    recorder, model = recorder_model()
    bundle = build_bundle(definition, model)

    await bundle.consultation_agent.run("What should we prioritise?", deps=_deps(definition))

    sent = recorder.last.instructions
    assert definition.display_name in sent
    assert definition.title in sent
    # The role-specific block, not merely the shared preamble.
    assert ROLE_INSTRUCTIONS[definition.agent_id][:150] in sent
    # Per-run company context was injected through deps.
    assert "Northstar Labs" in sent
    # House rules travelled too.
    assert "Never invent facts" in sent


async def test_no_executive_sees_another_role_block():
    """The decisive anti-impersonation check.

    Every agent must receive exactly one role instruction block: its own.
    """
    for definition in ROSTER:
        recorder, model = recorder_model()
        bundle = build_bundle(definition, model)
        await bundle.consultation_agent.run("Hello", deps=_deps(definition))
        sent = recorder.last.instructions

        for other_id, other_text in ROLE_INSTRUCTIONS.items():
            marker = other_text[:150]
            if other_id is definition.agent_id:
                assert marker in sent
            else:
                assert marker not in sent, (
                    f"{definition.agent_id} was sent {other_id}'s role instructions"
                )


async def test_two_executives_get_different_instructions_for_the_same_question():
    cfo_rec, cfo_model = recorder_model()
    coo_rec, coo_model = recorder_model()

    cfo = build_bundle(REGISTRY[AgentId.CFO], cfo_model)
    coo = build_bundle(REGISTRY[AgentId.COO], coo_model)

    question = "Should we expand internationally?"
    await cfo.consultation_agent.run(question, deps=_deps(REGISTRY[AgentId.CFO]))
    await coo.consultation_agent.run(question, deps=_deps(REGISTRY[AgentId.COO]))

    assert cfo_rec.last.instructions != coo_rec.last.instructions
    assert "Yusuf Benali" in cfo_rec.last.instructions
    assert "Yusuf Benali" not in coo_rec.last.instructions.split("The full board")[0]
    assert "Priya Raghunathan" in coo_rec.last.instructions


async def test_each_run_is_a_separate_model_call():
    """Two executives means two calls, not one call producing two voices."""
    rec, model = recorder_model()
    for agent_id in (AgentId.CEO, AgentId.CFO, AgentId.COO):
        bundle = build_bundle(REGISTRY[agent_id], model)
        await bundle.consultation_agent.run("Same question", deps=_deps(REGISTRY[agent_id]))

    assert len(rec.calls) == 3
    assert len({c.instructions for c in rec.calls}) == 3


async def test_company_context_is_scoped_per_run_not_baked_into_the_agent():
    """One agent instance serves many organizations without leaking context."""
    recorder, model = recorder_model()
    definition = REGISTRY[AgentId.CEO]
    bundle = build_bundle(definition, model)

    deps_a = GhostBoardDeps(
        organization_id=uuid.uuid4(),
        user_id=None,
        agent_id=definition.agent_id,
        company=CompanyContext(company_name="Alpha Inc", arr_usd=1_000),
    )
    deps_b = GhostBoardDeps(
        organization_id=uuid.uuid4(),
        user_id=None,
        agent_id=definition.agent_id,
        company=CompanyContext(company_name="Beta Ltd", arr_usd=9_000),
    )

    await bundle.consultation_agent.run("hi", deps=deps_a)
    await bundle.consultation_agent.run("hi", deps=deps_b)

    first, second = recorder.calls
    assert "Alpha Inc" in first.instructions and "Beta Ltd" not in first.instructions
    assert "Beta Ltd" in second.instructions and "Alpha Inc" not in second.instructions


async def test_empty_company_context_tells_the_agent_it_knows_nothing():
    recorder, model = recorder_model()
    definition = REGISTRY[AgentId.CFO]
    bundle = build_bundle(definition, model)

    await bundle.consultation_agent.run(
        "What is our runway?",
        deps=GhostBoardDeps(
            organization_id=uuid.uuid4(), user_id=None, agent_id=definition.agent_id
        ),
    )

    assert "No company profile has been entered" in recorder.last.instructions


async def test_agent_output_is_validated_against_the_schema():
    _, model = recorder_model(answer="Structured answer.")
    definition = REGISTRY[AgentId.CGO]
    bundle = build_bundle(definition, model)

    result = await bundle.consultation_agent.run("Grow revenue?", deps=_deps(definition))

    assert isinstance(result.output, ConsultationResponse)
    assert result.output.answer == "Structured answer."
    assert result.output.confidence_level.value == "medium"
    assert result.output.risks[0].severity.value == "moderate"
    assert result.output.assumptions[0].how_to_validate


def test_chairperson_is_excluded_from_one_on_one_consultations():
    assert REGISTRY[AgentId.CHAIRPERSON].can_consult_one_on_one is False
    assert all(
        d.can_consult_one_on_one for d in ROSTER if d.agent_id is not AgentId.CHAIRPERSON
    )


def test_get_bundle_returns_one_instance_per_executive(monkeypatch):
    monkeypatch.setattr("app.agents.factory.build_model", lambda *a, **k: TestModel())
    reset_agent_cache()
    assert get_bundle(AgentId.CEO) is get_bundle(AgentId.CEO)
    assert get_bundle(AgentId.CEO) is not get_bundle(AgentId.CFO)
