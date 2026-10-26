# Ghost Board — Implementation Status

Last updated: 2026-10-25 (end of Session 3)

| Phase | Scope | Status |
| --- | --- | --- |
| 1 | Monorepo, FastAPI, Postgres schema, auth, navigation | **Complete** |
| 2 | Nine original portraits, executive cards, My Board, design system | **Complete** |
| 3 | Pydantic AI agent engine, one-on-one consultations | **Complete** |
| 4 | Multi-agent board meeting engine (backend) | **Complete** |
| 4b | Live boardroom UI + SSE streaming | Not started |
| 5 | MCP server and tools | Not started |
| 6 | Full Board / Devil's Advocate / Strategy Workshop modes | Not started |
| 7 | Company intelligence, documents, memory retrieval | Not started |
| 8 | Interventions, pause/resume, export | Not started |
| 9 | Reliability, accessibility, final polish | Not started |

---

## Session 3 — the meeting engine

Backend only, by instruction. No boardroom UI was built.

### Verified working

**Six-stage orchestration.** `app/orchestration/meeting.py` drives agenda →
independent assessments → presentation → debate → revision → synthesis in
plain async Python. No graph framework.

**Independent assessments are structurally independent.** Stage 2 agents
receive the question, the agenda, and the company context — nothing from a
colleague. Asserted directly in
`test_assessments_are_produced_without_seeing_colleagues`, which inspects the
prompt each agent actually received and fails if any sibling's position text
appears in it.

**Bounded concurrency.** The four assessments fan out under a semaphore.
`test_assessments_run_concurrently` measures peak in-flight calls and fails if
the stage serialises; `test_assessment_concurrency_respects_the_limit` proves
the semaphore bounds it.

**Debate uses the real structured positions.** Challengers receive the
target's actual recommended position, summary, and assumptions, plus the
specific claim the Chair asked them to address — verified in
`test_challengers_receive_the_actual_claim_being_challenged`.

**Predictable call count.** A standard meeting is 10 model calls: 1 agenda +
4 assessments + 1 debate plan + 2 objections + 1 revision + 1 synthesis.
Asserted exactly in `test_model_call_count_is_small_and_predictable`.

**Live run against the real provider** (`gpt-6-luna`, Northstar Labs seed):

- Chair reframed the question and selected CEO, COO, CFO, Consultant.
- Four independent assessments, all reaching retention-first by different routes.
- Two evidence-based challenges:
  - **CFO → CEO** on "a focused retention diagnosis can be conducted without
    materially disrupting core delivery": *"its low-disruption cost is not
    established… the company facts do not specify who would do the work, how
    much capacity it requires, or whether that capacity can be spared."*
  - **COO → Consultant** on the fixed 60–90 day window: *"spending up to a
    quarter of [runway] before a decision gate risks delaying a needed change
    in allocation."*
- Both targets revised. The CEO: *"Yusuf's objection lands on an unsupported
  premise… we should not call the diagnosis capacity-neutral."*
- Decision brief generated, with dissent and unresolved questions recorded.

**Persistence and retrieval.** Assessments, objections, revisions,
participants, events, usage records, the decision, per-agent positions, and
action items all land in PostgreSQL and come back through
`GET /api/meetings/{id}`.

**Event log.** Every event is persisted *before* being handed to the sink, in
a gap-free sequence, and `GET /api/meetings/{id}/events?after=N` replays from
a cursor. The `EventSink` seam is where Phase 4b attaches SSE.

**Partial failure.** One agent failing is recorded as an `agent_failed` event,
marks that participant `skipped`, writes a usage row with zero tokens and the
error, and the meeting continues. Below two surviving assessments it aborts
rather than faking a board. A failed debate plan degrades to synthesis; a
failed agenda or synthesis aborts. No stage retries the whole meeting.

**Limits and cancellation.** Debate rounds, model-request ceiling, per-call
timeout, and assessment concurrency are all configurable and tested.
Cancellation is checked at stage boundaries — it does not claim to abort an
in-flight provider request.

### Implemented but not yet verified

- **`run_meeting_in_background` / `POST /meetings/{id}/start`.** The
  fire-and-forget path works in manual use but is not covered by an automated
  test; the suite drives the orchestrator directly so assertions are
  deterministic. The crash-recovery branch (marking a RUNNING meeting FAILED
  after an unexpected error) has never executed.
- **Multi-round debate.** `max_debate_rounds` defaults to 1 and the live runs
  used 1. Rounds > 1 are bounded and tested with the scripted board, but no
  live meeting has run two rounds.
- **Five of nine executives in meetings.** Only CEO, COO, CFO, Consultant and
  the Chair participate. The other four have meeting agents built and
  schema-tested but have never been in a live meeting.
- **`estimated_cost_usd` is always 0.0.** Unchanged from Session 2 — Pydantic
  AI has no pricing table for `gpt-6-luna`, so the cost ceiling in
  `MeetingLimits` is **not enforceable**. The model-request ceiling is, and is
  the real guard.

### Not implemented (out of session scope)

The live boardroom interface, SSE streaming, agent interventions, MCP tools,
and the other meeting modes.

---

## Known issues

**The board converges, and that is partly by design.** The shared house rules
("never invent facts", "uncertainty beats false precision") push every
executive toward the same epistemic stance, so on a thin company profile all
four independently recommend "diagnose before committing". The first two live
runs produced *no* challenges, and the Chair's reasoning for assigning none
was sound: the differences were implementation timing, not conflicting claims.

This was fixed by broadening what counts as a conflict in the Chair's debate
instructions — the spec's Stage 5 covers "assumptions requiring validation",
not only contradictions, and an unvalidated assumption shared by four people
is exposure rather than agreement. After that change the same question
produced two substantive challenges. Worth watching: richer company data
should produce more natural disagreement, and if it does not, the convergence
is a prompt-design problem rather than a data problem.

**Agenda and synthesis are single points of failure.** If the Chairperson
fails at either end, the meeting aborts. That is correct — there is no
meeting without an agenda and no deliverable without a brief — but it means
the Chair's reliability bounds the whole feature.

**Token budgets are per-purpose and hand-tuned.** The decision brief needs
8000 output tokens; at the previous flat 2000 the provider truncated it
mid-tool-call (`IncompleteToolCall`). Assessments get 3500, objections and
revisions 2000. If a future model is more verbose these will need revisiting.

**`openai_reasoning_effort` must stay `"none"`** — unchanged from Session 2.
Structured output is a function tool and `gpt-6-luna` rejects function tools
on `/v1/chat/completions` with reasoning enabled.

**PostgreSQL is a user-level cluster**, not a service, and does not start on
boot:

```bash
"C:/Users/daphn/pgsql-dl/pgsql/bin/pg_ctl.exe" -D "C:/Users/daphn/pgdata" -l "C:/Users/daphn/pgdata/server.log" -o "-p 5432" start
```

**No live-provider test in the default suite.** Real calls happen only in the
demo scripts, run manually.

---

## Reproducing the primary workflow

Prerequisites: PostgreSQL running, `PORTKEY_API_KEY` in the repo-root `.env`.

**Full board meeting, real model, Northstar Labs seed:**

```bash
cd backend && ./.venv/Scripts/python.exe -m scripts.demo_meeting
```

Seeds the company if absent, prints every stage live, then reports the agenda,
all four assessments, every challenge, every revision, the decision brief, and
the call accounting. Pass `--question "..."` to vary it.

**One-on-one consultation (Session 2):**

```bash
cd backend && ./.venv/Scripts/python.exe -m scripts.demo_consultation --agents cfo customer_advocate
```

**Retrieve a completed meeting over the API:**

```bash
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/meetings/$MEETING_ID
```

**Tests:**

```bash
cd backend && ./.venv/Scripts/python.exe -m pytest -q && ./.venv/Scripts/python.exe -m ruff check app tests scripts
```

```bash
cd frontend && npx tsc --noEmit && npx vitest run
```

---

## Test and check results (end of Session 3)

| Check | Result |
| --- | --- |
| `pytest` (backend) | 104 passed |
| — orchestration | 29 |
| — meetings API | 17 |
| — agent factory | 22 |
| — consultations API | 14 |
| — registry / agents API | 22 |
| `ruff check` (backend) | All checks passed |
| `tsc --noEmit` (frontend) | Clean |
| `vitest run` (frontend) | 15 passed |
| `alembic check` | No drift |
| Live board meeting | Verified: 4 assessments, 2 challenges, 2 revisions, brief |
