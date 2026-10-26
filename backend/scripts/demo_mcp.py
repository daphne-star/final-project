"""Reproducible demonstration of a real MCP tool invocation.

Runs the CFO against the real provider with a question that cannot be answered
honestly without arithmetic, then prints the tool invocations recorded in
PostgreSQL. The point is to show discovery, invocation, use of the result, and
the audit row — not to show a nice answer.

Usage (from backend/, with PostgreSQL running):
    ./.venv/Scripts/python.exe -m scripts.demo_mcp
    ./.venv/Scripts/python.exe -m scripts.demo_mcp --agent coo

Makes real model calls. Requires PORTKEY_API_KEY.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid

from sqlalchemy import select

from app.agents.deps import GhostBoardDeps
from app.agents.factory import get_bundle
from app.agents.provider import provider_is_configured
from app.agents.registry import REGISTRY, AgentId
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.mcp.context import ToolContext, bind_context
from app.mcp.server import tools_for_scopes
from app.models.meeting import ToolInvocation
from app.services.consultation import load_company_context
from scripts.demo_meeting import seed_northstar


def _force_utf8_stdout() -> None:
    """The Windows console defaults to cp1252, which cannot encode the minus
    signs, dashes, and quotes the model returns. Reconfigure rather than let a
    successful run die while printing its own output."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


QUESTIONS = {
    AgentId.CFO: (
        "We have $3,000,000 in the bank and burn $250,000 a month. If we cut burn "
        "by $75,000 a month, exactly how much runway do we gain? Use your tools "
        "and show the arithmetic."
    ),
    AgentId.COO: (
        "We have 10 engineers for the next 12 weeks, already 70% committed to "
        "existing work. A retention project needs 30 person-weeks. Can we do it? "
        "Use your tools."
    ),
}


def rule(char: str = "=") -> str:
    return char * 78


async def main() -> int:
    _force_utf8_stdout()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", default="cfo", choices=["cfo", "coo"])
    args = parser.parse_args()

    if not provider_is_configured():
        print("PORTKEY_API_KEY is not set.", file=sys.stderr)
        return 2

    agent_id = AgentId(args.agent)
    definition = REGISTRY[agent_id]

    async with AsyncSessionLocal() as db:
        org, user = await seed_northstar(db)
        company = await load_company_context(db, org.id)

    print(rule())
    print("GHOST BOARD — MCP TOOL INVOCATION")
    print(rule())
    print(f"Agent  : {definition.display_name} ({definition.title})")
    print(f"Model  : {settings.default_model} via {settings.portkey_base_url}")
    print(f"Scopes : {', '.join(s.value for s in definition.tool_scopes)}")
    print("Tools visible to this agent:")
    for name in sorted(tools_for_scopes(tuple(definition.tool_scopes))):
        print(f"  - {name}")

    question = QUESTIONS[agent_id]
    print(f"\nQuestion:\n  {question}\n")

    bundle = get_bundle(agent_id)
    deps = GhostBoardDeps(
        organization_id=org.id,
        user_id=user.id,
        agent_id=agent_id,
        company=company,
        consultation_id=None,
        allowed_tool_scopes=tuple(definition.tool_scopes),
    )

    marker = uuid.uuid4()  # not stored; used only to time-bound the audit query
    started_at = None
    async with AsyncSessionLocal() as db:
        from sqlalchemy import func

        started_at = (await db.execute(select(func.now()))).scalar_one()
    del marker

    with bind_context(
        ToolContext(
            organization_id=org.id,
            agent_id=agent_id,
            allowed_scopes=frozenset(definition.tool_scopes),
            user_id=user.id,
        )
    ):
        async with bundle.consultation_agent:
            result = await bundle.consultation_agent.run(
                question, deps=deps, timeout=float(settings.model_timeout_seconds)
            )

    print(rule("-"))
    print("ANSWER")
    print(rule("-"))
    print(f"\n{result.output.answer}\n")
    if result.output.key_points:
        print("KEY POINTS")
        for point in result.output.key_points:
            print(f"  - {point}")

    print(f"\n{rule('-')}")
    print("TOOL INVOCATIONS RECORDED IN POSTGRES")
    print(rule("-"))

    async with AsyncSessionLocal() as db:
        rows = (
            (
                await db.execute(
                    select(ToolInvocation)
                    .where(
                        ToolInvocation.organization_id == org.id,
                        ToolInvocation.created_at >= started_at,
                    )
                    .order_by(ToolInvocation.created_at)
                )
            )
            .scalars()
            .all()
        )

    if not rows:
        print("\nNone. The model answered without calling a tool.")
        print("That is a legitimate outcome, but it does not demonstrate MCP.")
        return 1

    for row in rows:
        print(f"\n  tool     : {row.tool_name}")
        print(f"  agent    : {row.agent_id}")
        print(f"  status   : {row.status.value}")
        print(f"  duration : {row.duration_ms} ms")
        print(f"  arguments: {row.arguments}")
        if row.result:
            calc = row.result.get("calculation") or row.result.get("verdict")
            if calc:
                print(f"  result   : {calc}")
        if row.error_message:
            print(f"  error    : {row.error_message}")

    print(f"\n{rule()}")
    print(f"{len(rows)} tool invocation(s) discovered and called over MCP.")
    print(f"Model requests: {result.usage.requests}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
