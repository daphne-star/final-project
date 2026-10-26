"""Reproducible demonstration of the one-on-one consultation workflow.

Runs two different executives against the same question using the real
configured provider, and prints both answers side by side. The point is to
show that two agents produce genuinely role-specific responses from separate
model calls — not one model doing voices.

Usage (from backend/):
    ./.venv/Scripts/python.exe -m scripts.demo_consultation
    ./.venv/Scripts/python.exe -m scripts.demo_consultation --agents cfo coo --question "..."

Requires PORTKEY_API_KEY in the environment or the repo-root .env.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid

from app.agents.deps import CompanyContext, GhostBoardDeps
from app.agents.factory import get_bundle
from app.agents.provider import provider_is_configured
from app.agents.registry import REGISTRY, AgentId
from app.core.config import settings


def _force_utf8_stdout() -> None:
    """The Windows console defaults to cp1252, which cannot encode the minus
    signs, dashes, and quotes the model returns. Reconfigure rather than let a
    successful run die while printing its own output."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


NORTHSTAR = CompanyContext(
    company_name="Northstar Labs",
    industry="B2B SaaS",
    business_model="Annual per-seat subscriptions",
    stage="Series A",
    headcount=28,
    description="Workflow automation for mid-market logistics teams.",
    revenue_model="Per-seat annual contracts",
    arr_usd=2_000_000,
    monthly_burn_usd=250_000,
    cash_on_hand_usd=3_000_000,
    runway_months=12,
    annual_churn_rate=0.15,
    goals=("Sustainable growth",),
    challenges=("Choosing the next strategic priority",),
)

DEFAULT_QUESTION = (
    "Northstar Labs must choose between international expansion, improving "
    "customer retention, and launching a new product. Which should we "
    "prioritise over the next 12 months?"
)


def _rule(char: str = "-") -> str:
    return char * 78


async def consult(agent_id: AgentId, question: str) -> None:
    definition = REGISTRY[agent_id]
    bundle = get_bundle(agent_id)
    deps = GhostBoardDeps(
        organization_id=uuid.uuid4(),
        user_id=None,
        agent_id=agent_id,
        company=NORTHSTAR,
        allowed_tool_scopes=tuple(definition.tool_scopes),
    )

    print(f"\n{_rule('=')}")
    print(f"{definition.display_name} — {definition.title}")
    print(_rule("="))

    result = await bundle.consultation_agent.run(
        question, deps=deps, timeout=float(settings.model_timeout_seconds)
    )
    out = result.output

    print(f"\n{out.answer}\n")

    if out.key_points:
        print("KEY POINTS")
        for p in out.key_points:
            print(f"  - {p}")
    if out.assumptions:
        print("\nASSUMPTIONS")
        for a in out.assumptions:
            print(f"  - {a.statement}")
            print(f"      why: {a.why_it_matters}")
    if out.risks:
        print("\nRISKS")
        for r in out.risks:
            print(f"  - [{r.severity.value}] {r.description}")
    if out.open_questions:
        print("\nOPEN QUESTIONS")
        for q in out.open_questions:
            print(f"  - {q.question}")
    if out.recommended_actions:
        print("\nRECOMMENDED ACTIONS")
        for a in out.recommended_actions:
            print(f"  - [{a.priority.value}] {a.description}")

    usage = result.usage
    print(f"\nconfidence={out.confidence_level.value}  out_of_scope={out.out_of_scope}")
    print(
        f"usage: requests={usage.requests} "
        f"input_tokens={usage.input_tokens} output_tokens={usage.output_tokens}"
    )


async def main() -> int:
    _force_utf8_stdout()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--agents",
        nargs="+",
        default=["cfo", "customer_advocate"],
        help="Roster agent ids to consult (default: cfo customer_advocate)",
    )
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    args = parser.parse_args()

    if not provider_is_configured():
        print(
            "PORTKEY_API_KEY is not set. Add it to the .env at the repo root.\n"
            "This script makes real model calls by design; there is no mock mode.",
            file=sys.stderr,
        )
        return 2

    try:
        agent_ids = [AgentId(a) for a in args.agents]
    except ValueError as exc:
        print(f"Unknown agent id: {exc}", file=sys.stderr)
        print(f"Valid ids: {', '.join(a.value for a in AgentId)}", file=sys.stderr)
        return 2

    print(f"Model: {settings.default_model} via {settings.portkey_base_url}")
    print(f"Question: {args.question}")

    # Separate, sequential runs. Each agent sees only its own instructions.
    for agent_id in agent_ids:
        await consult(agent_id, args.question)

    print(f"\n{_rule('=')}")
    print(f"{len(agent_ids)} independent agent runs completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
