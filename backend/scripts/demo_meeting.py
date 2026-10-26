"""Reproducible demonstration of a full board meeting.

Seeds the Northstar Labs company if it is not already present, convenes an
Executive Meeting on the session-3 question, and prints every stage: the
Chair's agenda, each independent assessment, the challenges raised, any
revisions, and the final decision brief.

Usage (from backend/, with PostgreSQL running):
    ./.venv/Scripts/python.exe -m scripts.demo_meeting
    ./.venv/Scripts/python.exe -m scripts.demo_meeting --question "..."

Makes real model calls. Requires PORTKEY_API_KEY.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid

from sqlalchemy import select

from app.agents.provider import provider_is_configured
from app.agents.registry import REGISTRY, AgentId
from app.core.config import settings
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.enums import OrgRole
from app.models.identity import CompanyProfile, Organization, OrganizationMember, User
from app.models.meeting import Meeting
from app.orchestration.events import MeetingEventModel
from app.orchestration.meeting import MeetingAborted, MeetingCancelled, MeetingLimits
from app.services import meeting as svc


def _force_utf8_stdout() -> None:
    """The Windows console defaults to cp1252, which cannot encode the minus
    signs, dashes, and quotes the model returns. Reconfigure rather than let a
    successful run die while printing its own output."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


DEMO_EMAIL = "founder@northstarlabs.example.com"
DEMO_SLUG = "northstar-labs-demo"

QUESTION = (
    "Should we prioritize improving retention, international expansion, "
    "or launching a new product?"
)


def rule(char: str = "=", width: int = 78) -> str:
    return char * width


def wrap(text: str, indent: str = "  ", width: int = 76) -> str:
    import textwrap

    return textwrap.fill(text, width=width, initial_indent=indent, subsequent_indent=indent)


def name_of(agent_id: str) -> str:
    try:
        d = REGISTRY[AgentId(agent_id)]
        return f"{d.display_name} ({d.short_title})"
    except (ValueError, KeyError):
        return agent_id


async def seed_northstar(db) -> tuple[Organization, User]:
    """Idempotent seed of the demonstration company (spec section 18)."""
    org = (
        await db.execute(select(Organization).where(Organization.slug == DEMO_SLUG))
    ).scalar_one_or_none()
    user = (
        await db.execute(select(User).where(User.email == DEMO_EMAIL))
    ).scalar_one_or_none()

    if user is None:
        user = User(
            email=DEMO_EMAIL,
            hashed_password=hash_password("northstar-demo-pw"),
            full_name="Northstar Founder",
        )
        db.add(user)
        await db.flush()

    if org is None:
        org = Organization(name="Northstar Labs", slug=DEMO_SLUG)
        db.add(org)
        await db.flush()
        db.add(
            OrganizationMember(organization_id=org.id, user_id=user.id, role=OrgRole.OWNER)
        )
        await db.flush()

    profile = (
        await db.execute(
            select(CompanyProfile).where(CompanyProfile.organization_id == org.id)
        )
    ).scalar_one_or_none()
    if profile is None:
        db.add(
            CompanyProfile(
                organization_id=org.id,
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
                goals=[{"text": "Sustainable growth"}],
                challenges=[{"text": "Choosing the next strategic priority"}],
                constraints=[],
            )
        )
        await db.flush()

    await db.commit()
    return org, user


async def live_sink(event: MeetingEventModel) -> None:
    """Print stage transitions as they happen, so a long run is legible."""
    kind = event.event_type.value
    if kind in {"stage_changed"}:
        print(f"\n  [stage] {event.payload.get('stage')}")
    elif kind == "agent_started":
        print(f"    -> {name_of(event.agent_id or '')} ({event.payload.get('stage')})")
    elif kind == "agent_failed":
        print(f"    !! {name_of(event.agent_id or '')} FAILED: {event.payload.get('error')}")
    elif kind == "objection_raised":
        print(
            f"    ** {name_of(event.agent_id or '')} -> "
            f"{name_of(event.payload.get('target_agent_id', ''))} "
            f"[{event.payload.get('stance')}]"
        )
    elif kind == "position_revised":
        moved = "CHANGED" if event.payload.get("position_changed") else "HELD"
        print(f"    ~~ {name_of(event.agent_id or '')} {moved}")


async def main() -> int:
    _force_utf8_stdout()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--question", default=QUESTION)
    parser.add_argument("--rounds", type=int, default=1, help="Max debate rounds")
    args = parser.parse_args()

    if not provider_is_configured():
        print(
            "PORTKEY_API_KEY is not set. Add it to the .env at the repo root.\n"
            "This script makes real model calls by design; there is no mock mode.",
            file=sys.stderr,
        )
        return 2

    async with AsyncSessionLocal() as db:
        org, user = await seed_northstar(db)

        print(rule())
        print("GHOST BOARD — EXECUTIVE MEETING")
        print(rule())
        print("Company : Northstar Labs (B2B SaaS, $2M ARR, 12mo runway, 15% churn)")
        print(f"Model   : {settings.default_model} via {settings.portkey_base_url}")
        print(f"Question: {args.question}")

        meeting = await svc.create_meeting(
            db, organization_id=org.id, user_id=user.id, question=args.question
        )
        await db.commit()

        try:
            decision = await svc.run_meeting(
                db,
                meeting,
                user_id=user.id,
                limits=MeetingLimits(
                    max_debate_rounds=args.rounds,
                    model_timeout_seconds=float(settings.model_timeout_seconds),
                ),
                sink=live_sink,
            )
            await db.commit()
        except MeetingCancelled:
            await db.commit()
            print("\nMeeting cancelled.")
            return 1
        except MeetingAborted as exc:
            await db.commit()
            print(f"\nMeeting aborted ({exc.code}): {exc}", file=sys.stderr)
            return 1

        await _report(db, meeting.id, decision.id)
        print(f"\nMeeting id : {meeting.id}")
        print(f"Decision id: {decision.id}")
        print("Retrieve later with: GET /api/meetings/<meeting_id>")
    return 0


async def _report(db, meeting_id: uuid.UUID, decision_id: uuid.UUID) -> None:
    meeting = await db.get(Meeting, meeting_id)
    parts = await svc.get_meeting_contributions(db, meeting_id)
    agenda = meeting.agenda or {}

    print(f"\n\n{rule()}")
    print("STAGE 1 — AGENDA (Chairperson)")
    print(rule())
    print(f"\nReframed question:\n{wrap(agenda.get('reframed_question', '—'))}")
    for item in agenda.get("agenda_items", []):
        print(f"\n  • {item['title']}")
        print(wrap(item["question"], indent="      "))
    tensions = agenda.get("tensions_to_test") or []
    if tensions:
        print("\nTensions the Chair wants surfaced:")
        for t in tensions:
            print(wrap(f"- {t}"))

    print(f"\n\n{rule()}")
    print("STAGES 2–3 — INDEPENDENT ASSESSMENTS")
    print(rule())
    print("\nEach produced by a separate model call, with no sight of the others.")
    for a in parts["assessments"]:
        print(f"\n{rule('-')}")
        print(f"{name_of(a.agent_id)}  [confidence: {a.confidence_level.value}]")
        print(rule("-"))
        print(f"\nPosition:\n{wrap(a.recommended_position)}")
        print(f"\nReasoning:\n{wrap(a.summary)}")
        if a.assumptions:
            print("\nAssumptions:")
            for item in a.assumptions[:3]:
                print(wrap(f"- {item['statement']}"))
        if a.risks:
            print("\nRisks:")
            for item in a.risks[:3]:
                print(wrap(f"- [{item['severity']}] {item['description']}"))

    print(f"\n\n{rule()}")
    print("STAGE 4 — DEBATE")
    print(rule())
    if not parts["objections"]:
        print("\nNo challenges were assigned; the executives substantially agreed.")
    for o in parts["objections"]:
        print(f"\n{rule('-')}")
        print(f"{name_of(o.source_agent_id)}  →  {name_of(o.target_agent_id)}")
        print(f"severity: {o.severity.value}")
        print(rule("-"))
        print(f"\nClaim challenged:\n{wrap(o.challenged_claim)}")
        print(f"\nArgument:\n{wrap(o.objection)}")
        if o.proposed_resolution:
            print(f"\nProposed resolution:\n{wrap(o.proposed_resolution)}")

    print(f"\n\n{rule()}")
    print("STAGE 5 — REVISIONS")
    print(rule())
    if not parts["revisions"]:
        print("\nNo executive was asked to reconsider.")
    for r in parts["revisions"]:
        print(f"\n{name_of(r.agent_id)}")
        print(f"\nBefore:\n{wrap(r.original_position)}")
        print(f"\nAfter:\n{wrap(r.updated_position)}")
        print(f"\nWhy:\n{wrap(r.reason_for_change)}")

    decision = parts["decision"]
    print(f"\n\n{rule()}")
    print("STAGE 6 — DECISION BRIEF (Chairperson synthesis)")
    print(rule())
    print(f"\nExecutive summary:\n{wrap(decision.executive_summary)}")
    print(f"\nProblem:\n{wrap(decision.problem_statement)}")

    print("\nOptions considered:")
    for opt in decision.strategic_options:
        marker = " ← RECOMMENDED" if opt["option_id"] == decision.recommended_option_id else ""
        print(f"\n  [{opt['option_id']}] {opt['title']}{marker}")
        print(wrap(opt["description"], indent="      "))

    print(f"\nWhy:\n{wrap(decision.recommendation_rationale or '—')}")

    if decision.dissenting_opinions:
        print("\nDissent recorded:")
        for d in decision.dissenting_opinions:
            print(f"\n  {name_of(d['agent_id'])}:")
            print(wrap(d["position"], indent="      "))

    if decision.unresolved_questions:
        print("\nStill unresolved:")
        for q in decision.unresolved_questions:
            print(wrap(f"- {q['question']}"))

    print(f"\nConfidence:\n{wrap(decision.confidence_and_uncertainty or '—')}")

    plan = decision.action_plan or {}
    for label, key in (
        ("First 30 days", "first_30_days"),
        ("Days 30–60", "days_30_to_60"),
        ("Days 60–90", "days_60_to_90"),
    ):
        items = plan.get(key) or []
        if items:
            print(f"\n{label}:")
            for item in items:
                owner = f" [{item['suggested_owner']}]" if item.get("suggested_owner") else ""
                print(wrap(f"- ({item['priority']}) {item['description']}{owner}"))

    print(f"\n\n{rule()}")
    print("ACCOUNTING")
    print(rule())
    print(f"Model requests : {meeting.model_requests_used}")
    print(f"Debate rounds  : {meeting.debate_rounds_used}")
    print(f"Assessments    : {len(parts['assessments'])}")
    print(f"Objections     : {len(parts['objections'])}")
    print(f"Revisions      : {len(parts['revisions'])}")
    events = await svc.list_events(db, meeting_id)
    print(f"Events logged  : {len(events)}")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
