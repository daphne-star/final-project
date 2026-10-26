# Ghost Board — Implementation Status

Last updated: 2026-10-26 (end of Session 9)

| Phase | Scope | Status |
| --- | --- | --- |
| 1 | Monorepo, FastAPI, Postgres schema, auth, navigation | **Complete** |
| 2 | Nine original portraits, executive cards, My Board, design system | **Complete** |
| 3 | Pydantic AI agent engine, one-on-one consultations | **Complete** |
| 4 | Multi-agent board meeting engine (backend) | **Complete** |
| 4b | SSE streaming and the live boardroom interface | **Complete** |
| 5 | MCP server and tools | **Complete** |
| 6 | All nine agents; Full Board / Devil's Advocate / Strategy Workshop | **Complete** |
| 7 | Company intelligence, documents, memory retrieval | **Complete** |
| 8 | Agent interventions, pause/resume, export | **Complete** |
| 9 | Reliability, accessibility, performance, final polish | **Complete** |

---

## Session 4 — the live boardroom

### Verified working

**SSE streaming.** `GET /api/meetings/{id}/stream` serves `text/event-stream`,
authenticated like every other endpoint. Each frame carries the event's
sequence number as the SSE `id`.

**Reconnection cannot duplicate.** The stream tails the *persisted* event log
rather than an in-memory bus, so resuming is just "read after cursor N".
`Last-Event-ID` and `?after=` both work, the header winning. Proved two ways:
`test_resuming_after_a_cursor_delivers_no_duplicates` asserts that the head
and the resumed tail concatenate to exactly the full log, and on the client
`reduceEvent` ignores anything at or before its cursor, so replaying the whole
log over an existing state is a no-op.

**The live boardroom.** Three columns on desktop — participants left,
transcript centre, agenda/tensions/disagreements/positions right — collapsing
to drawers below `lg`/`xl`. Verified in the browser at 1600px, 1280px and
375px.

**Real agent activity.** Card status comes only from backend
`agent_started` / `agent_status_changed` / `agent_failed` events. There are no
timers anywhere in the UI.

**Chair vs specialist is visible.** Chair turns get a dashed container and a
`Chair · …` badge; specialist turns get an `Independent assessment` badge and
a quoted "Recommends" block. Asserted in
`Transcript.test.tsx › distinguishes Chair commentary from specialist analysis`.

**Live end-to-end run.** Started from the React UI, watched the Chair open,
four executives analyse concurrently, six challenges land, four positions get
revised, and the brief generate. Then refreshed: all 18 transcript entries
came back (3 chair turns, 4 assessments, 6 objections, 4 revisions, 1
decision), status `Complete`, brief link intact.

**Failure and error states.** A failed meeting shows the reason, keeps
whatever the board produced, and offers reload / new meeting. A meeting in
another organization renders the 404 state. A dropped stream shows a
"disconnected" banner that says the meeting is still running server-side, with
a reconnect button. All checked in the browser.

**New meeting flow.** Question input with length validation and suggestions,
participant selection (defaulting to CEO/COO/CFO/Consultant, Chair fixed and
non-removable), a cost hint, and a disabled submit until the form is valid.
Selected executives are written as participant rows and become the Chair's
candidate pool.

### Deliberately not implemented

**`agent_message_delta` is never emitted.** The spec asks for it "where
genuine streaming is supported". It is not, here. Every agent output is a
structured tool call, and probing `run_stream`/`stream_output` against
`gpt-6-luna` yielded two partials where the *first* already contained the
complete 264-character summary — the provider does not stream tool-call
arguments incrementally in a usable way.

Emitting synthetic deltas by chunking a finished string would be exactly the
fake activity the spec forbids. The event type is kept in `EventType` and in
the frontend union so the contract is complete and a future model can start
emitting it without a schema change, but nothing produces one today. The UI
shows per-agent "is analyzing / challenging / revising" from real status
events instead.

### Known limitations

**Meetings run as in-process asyncio tasks.** This is the honest weak point
and the spec called it out directly. Three things were done about it rather
than pretending otherwise:

1. **State is durable, not in-memory.** `_emit` now *commits* each event
   instead of flushing it. That is what makes the event log readable from
   another session at all — before the change the SSE stream saw nothing
   until the whole meeting finished. It also means a crashed meeting keeps
   everything it produced up to the failure.
2. **The stream does not depend on the producer.** Readers poll the database,
   so a second worker, a later reconnect, or a client opening a finished
   meeting all see the identical ordered history. Cost: updates land within
   one ~0.4s poll rather than instantly.
3. **Orphans are reconciled at startup.** `reconcile_orphaned_meetings()`
   marks any meeting still `RUNNING` as failed, with a message saying the
   server restarted. Without it a killed meeting would sit at `RUNNING`
   forever and its stream would poll to the 30-minute ceiling.

**In-flight work is still lost on restart — not resumed.** Making meetings
resumable needs either a durable job queue (Redis/Celery, which the spec rules
out for the MVP) or per-stage checkpointing with replay. Neither is built.

**Multi-worker caveat.** `asyncio.create_task` runs the meeting in whichever
worker took the POST. Streaming works from any worker because it reads the
database, but the orchestrator itself is not distributed.

**`estimated_cost_usd` is still 0.0** — Pydantic AI has no pricing table for
`gpt-6-luna`, so the cost ceiling remains unenforceable. The model-request
ceiling is the real guard.

**`openai_reasoning_effort` must stay `"none"`** — structured output is a
function tool and the provider rejects function tools with reasoning on.

**PostgreSQL is a user-level cluster** and does not start on boot:

```bash
"C:/Users/daphn/pgsql-dl/pgsql/bin/pg_ctl.exe" -D "C:/Users/daphn/pgdata" -l "C:/Users/daphn/pgdata/server.log" -o "-p 5432" start
```

**Not covered by automated tests:** the `POST /meetings/{id}/start` background
path and the crash-recovery branch inside `run_meeting_in_background`. The
suite drives the orchestrator directly so assertions stay deterministic.

---

## Session 5 — the MCP server

### Verified working

**A real MCP server with ten tools.** `app/mcp/server.py` builds a FastMCP
instance; agents reach it through Pydantic AI's `MCPToolset`. Discovery and
invocation go through the MCP protocol, not a Python function call dressed up
as one — `test_cfo_discovers_its_tools_over_mcp` asserts on the tool list the
*model* was offered.

Company intelligence: `get_company_profile`, `get_company_goals`,
`search_company_knowledge`, `get_previous_decisions`.
Financial: `calculate_cash_runway`, `calculate_unit_economics`,
`compare_financial_scenarios`.
Operations: `assess_execution_capacity`, `identify_operational_dependencies`,
`build_implementation_plan`.

**Live invocation against the real provider.** The CFO was asked for a runway
delta and called `calculate_cash_runway` with
`{cash: 3,000,000, burn: 250,000, burn_change: -75,000}`, then answered with
the tool's numbers verbatim:

> Cutting monthly burn by $75,000 increases runway by **5.1 months**: from
> **12.0 months** to **17.1 months**.

The COO, on a separate scope, called `assess_execution_capacity` and got
`10 people x 12 weeks x 30% free = 36.0 person-weeks available`. Both
invocations are rows in `tool_invocations` with arguments, result, status and
duration.

**No tool accepts an organization id.** This is the spec's hardest MCP
requirement and the design answer is to leave the model nowhere to put one.
Scope comes from a `ToolContext` bound by the orchestrator around each agent
run; `test_no_tool_accepts_an_organization_id` inspects every registered
tool's signature and fails if one grows an `organization_id` parameter.
Tools fail closed when no context is bound.

**Per-role tool access, enforced twice.** Each agent gets an `MCPToolset`
filtered to the tools its registry scopes allow, so the CFO never sees
`assess_execution_capacity`. That is a prompt-quality measure, not the
boundary: the server re-checks the scope on every call, and
`test_a_tool_outside_the_agents_remit_is_denied_and_recorded` bypasses the
filter entirely to prove an unauthorized call is refused and audited as
`DENIED`.

**Every call is audited.** `tool_invocations` rows carry the organization,
agent, tool, arguments, result, status, duration, and error.

**Calculations are checked against hand arithmetic**, not just smoke-tested:
runway, LTV/CAC and payback, scenario ranking, capacity utilisation, and
critical-path ordering all have tests with worked expected values.

### Design notes

**Tool logic is transport-independent.** Nothing in `app/mcp/tools/` imports
MCP or FastAPI; they are plain functions over Pydantic models. Serving them
over Streamable HTTP later means pointing `MCPToolset` at a URL and serving
the same `FastMCP` instance — the tool bodies do not change.

The one piece that *would* need rework is `app/mcp/context.py`: a
cross-process server cannot read a contextvar, so the scope would have to
travel in a server-validated token instead. That boundary is called out in the
module docstring rather than designed around prematurely.

**Research tools are deliberately absent.** The spec says to add external web
research "after the initial local workflow functions", and that research tools
must return real sourced findings. There is no web access configured here, so
adding one would mean either a stub or a fabrication. The Competitive Advisor
and General Counsel hold the `research` scope in the registry and currently
resolve to no tools, which is why their instructions tell them to state what
they would need to verify rather than asserting it.

### Known limitations

**`duration_ms` reads 0 for the pure calculators.** They complete in well
under a millisecond and the column is an integer. Accurate, if uninformative.

**No approval gate is implemented**, because no tool mutates anything. Every
tool is read-only or a pure calculation. The spec requires approval for
consequential mutations; when the first mutating tool arrives it will need
one, and nothing in the current wrapper provides it.

**Knowledge search is `ILIKE`, not full-text.** The schema has `tsvector`
columns and GIN indexes ready, but nothing populates them yet — document
ingestion is Phase 7. Until then `search_company_knowledge` does a substring
match over company memories and document chunks, which is honest but weak.

---

## Session 6 — all nine agents and the meeting modes

### Verified working

**All nine agents in one meeting.** A live Full Board run seated 9
participants, produced 8 independent assessments, 6 challenges and 6
revisions in 35 model calls. Each executive contributed from its own angle —
the General Counsel on compliance diligence, the Customer Advocate on
customer-level evidence, the Competitive Advisor on defining the target
outcome first.

**Five modes, each changing what the board is asked to do.**
`app/orchestration/modes.py` holds one `ModeProfile` per mode: candidate
pool, participant bounds, model-request budget, challenge cap, and per-stage
task framing. All five run the same six stages — what differs is who is in
the room and what they are asked.

| Mode | Room | What it asks for |
| --- | --- | --- |
| Quick Consultation | 1 | A direct answer, cheaply |
| Executive Meeting | 3–6 of 8 | Relevant functions only |
| Full Board | all 8 + Chair | Every function, tightly scoped |
| Devil's Advocate | 3–5 | How an existing recommendation fails |
| Strategy Workshop | 3–6 | Alternatives, then a COO roadmap |

**Devil's Advocate works on a real prior decision.** A live run against the
Full Board's own recommendation produced genuine attacks, including the CFO
turning the board's caution against itself: *"Do not treat bounded diagnosis
as automatically safer than acting."* The subject decision — its options,
rationale, and the dissent already recorded — is injected into every stage
prompt, so nobody re-raises a point the board already answered.

**Relevant agent selection.** Executive Meeting now draws from all eight
specialists rather than a fixed four, with the Chair choosing and the mode
capping. A Chair that under-seats is topped up to the mode minimum, because
a stress test with two attackers is not much of one.

**Strategy Workshop adds a COO roadmap stage** after synthesis, recorded as
its own contribution (round 99) rather than overwriting the Chair's plan. If
the COO is not in the pool the stage is skipped and the Chair's plan stands.

### Known limitations

**The board still converges.** Eight executives on a thin company profile all
reached "do not commit yet, run a bounded diagnosis". Each got there by a
different route, and the debate stage found six real conflicts, so the
mechanism works — but the shared epistemic rules keep pulling every executive
toward the same cautious conclusion. Richer company data is the likely fix;
this remains the most interesting open question in the product.

**Full Board costs roughly 3x an Executive Meeting** (35 calls versus ~10).
The budget scales with the mode, but there is no spend guard beyond the
model-request ceiling, since cost estimation still reports 0.0.

**Mode framing is prompt-level, not structural.** A Devil's Advocate agent is
the same `Agent` instance as in any other meeting, handed a different task.
That is deliberate — nine agents, not forty-five — but it means mode
adherence depends on instruction-following rather than being enforced.

**`min_participants` is enforced by topping up, `max_participants` by
trimming.** Both override the Chair's judgement when it falls outside the
mode's bounds. Trimming takes the first N, which is arbitrary where the Chair
had a reason for its ordering.

---

## Session 7 — company intelligence and memory

### Verified working

**The board changed its answer because of an uploaded document.** This is the
Phase 7 acceptance criterion and it was tested end to end against the real
provider.

A churn analysis was uploaded saying the headline 15% figure is misleading:
enterprise renews at 96%, self-serve churns at 34%, 71% of churned self-serve
accounts never completed onboarding, and net revenue retention is 104%. Then
the founder asked a question built on the misleading premise — *"Our churn is
15%. Should we fund a company-wide retention programme?"*

All three executives cited every document-only fact, and all three **declined
the premise**: a bounded test on self-serve accounts that have not reached
first value, explicitly not a company-wide programme. None of those figures
exists in the company profile; they came only from the document.

**Ingestion.** PDF, DOCX and text, validated by magic number rather than the
declared content type, size-capped before parsing, extracted off the event
loop, chunked with overlap, and indexed. A scanned PDF fails with a message
saying it needs OCR rather than indexing as empty.

**Retrieval is real full-text search**, ranked by `ts_rank` over company
memories and document chunks together, scoped to the organization in the
query itself.

**Provenance is enforced, not conventional.** `USER_CONFIRMED` requires a
user id — `record_memory` raises without one, so there is no code path by
which an agent writes a confirmed fact. `confirm_memory` is the only
promotion route and it takes a human id. Corrections supersede rather than
overwrite, so the record still shows what the board was told when it decided.

**Meeting context labels what is trustworthy.** Retrieved records arrive
wrapped in explicit markers, tagged `[VERIFIED · user_confirmed]` or
`[UNVERIFIED · model_interpretation]`, with a line telling the agent that
everything between the markers is data and never instructions.

**Decisions become retrievable history.** Every completed meeting records its
recommendation as `HISTORICAL_DECISION` — true as history regardless of
whether the recommendation was right, and visible in the Knowledge tab
alongside documents with its own badge.

**Company Intelligence page.** Profile editing, document upload with status
and chunk counts, a knowledge list with provenance badges and
confirm/correct/delete, and a search box that shows exactly what a meeting on
a given question would retrieve.

### Bugs this session surfaced

**Long questions matched nothing.** `websearch_to_tsquery` ANDs bare terms,
so "Should we invest in reducing churn?" required a record containing every
one of those words. Retrieval now strips stopwords and ORs the rest, letting
`ts_rank` order the results. Without this the whole feature silently returned
empty for every realistic question.

**Search vectors were application-populated**, so any row written by a path
that forgot to set them was invisible to search — a silent retrieval gap
rather than an error. They are now Postgres generated columns (migration
`0004`), which cannot be written and cannot go stale.

**UTF-16 was tried speculatively** during text extraction and "succeeded" on
single-byte text, indexing mojibake. It is now only attempted when a BOM says
so.

### Known limitations

**No OCR.** A scanned PDF is rejected with an explanation. Adding OCR means a
system dependency the spec does not call for.

**No embeddings.** Keyword search with ranking is doing the job, and the spec
says to add pgvector only if it proves insufficient. It has not yet, but the
test for that is a bigger corpus than exists here.

**The test suite has slowed considerably** — roughly 80s before this session,
91s to 226s after, varying between runs on identical code. Every meeting test
now runs a retrieval query, and the variance suggests contention with the
running dev server rather than the query itself. Not investigated further;
flagged because it will get worse.

**Document deletion removes the bytes but keeps the row**, so prior evidence
citations still resolve to something. Chunks go, so the content is no longer
retrievable — but a meeting transcript that quoted the document still shows
the quote.

**Memory has no size limit.** A founder could record thousands of facts and
the retrieval cap (8 per meeting) would quietly hide most of them. There is no
warning when that happens.

---

## Session 8 — directing a live meeting

### Verified working

**An intervention changed an executive's mind, live.** Mid-meeting, the
founder challenged the COO: *"You keep saying capacity is the constraint.
Name the specific team that is the bottleneck and what it is doing instead."*
The COO withdrew its own claim:

> "I can't name a specific bottleneck team from the information we have.
> Saying 'capacity is the constraint' without identifying the team and its
> current work was too strong; I withdraw that claim."

That is the Phase 8 acceptance criterion: the founder meaningfully directed
the meeting, and the exchange is in its persisted history.

**Interventions are rows, not UI state.** The spec forbids buttons that only
change frontend text, so an intervention is a `meeting_interventions` row
(migration `0005`) written by an authenticated REST call and drained by the
running meeting. `test_an_intervention_is_a_persisted_row_not_a_ui_state`
asserts exactly that.

**They run between stages, never inside one.** `_checkpoint` is the single
safe point: cancel, pause, drain interventions, budget — all between units of
work. `test_interventions_run_between_stages_never_inside_one` proves a
founder interruption cannot land in the middle of the assessment wave and
corrupt a round in flight.

**Seven intervention kinds**, each framing the task differently: ask,
challenge, request evidence, critique a colleague, request an alternative,
implementation detail, explain a risk. A critique prompt carries the
colleague's *actual* conclusion, and every prompt quotes the founder verbatim.

**Pause and resume.** Pause holds the meeting at its next checkpoint;
anything queued while paused is answered before it continues. A paused
meeting still holds a worker, so there is a 30-minute ceiling after which it
aborts rather than parking forever.

**Validation that matters.** You cannot address an executive who is not in
the room, an executive that does not exist, or a meeting that is not live.
Anything still queued when a meeting ends is marked `ABANDONED` rather than
left looking pending.

**Evidence display.** The boardroom's right panel now lists the citations
from each assessment, attributed to the executive and flagged when
unverified.

**Action items** can be assigned an owner and moved through
open/in-progress/blocked/done from the Decision Center.

**Export.** Markdown and PDF, both rendered from the same structure so they
cannot describe the decision differently. Empty sections are omitted rather
than filled with placeholders, and the legal disclaimer travels with the file.

### Known limitations

**A paused meeting consumes a worker.** It is an asyncio task parked at a
checkpoint, not persisted work that could be rehydrated. The 30-minute cap
keeps that bounded, but it is the same in-process limitation as Session 4.

**Pause does not abort a request in flight** — the current step finishes
first. Said plainly in the UI tooltip rather than implied otherwise.

**At most three interventions are drained per checkpoint**, so a founder who
queues ten will see them answered across several stages. The cap exists so
one impatient user cannot stall the meeting.

**The PDF uses core fonts only.** Characters outside latin-1 — em dashes,
curly quotes, arrows the model likes — are replaced rather than rendered.
Bundling a Unicode TTF would fix it and is the right answer eventually; it is
a binary dependency this project does not otherwise need.

**Interventions show up in the transcript only after a page refresh or the
next stream event**, because the panel invalidates the meeting query rather
than optimistically inserting. Correct, but it can feel slow.

### Bugs this session surfaced

- **fpdf leaves the cursor at the right margin** after `multi_cell`, so the
  second heading had no width left and the whole export raised. Every call
  now resets with `new_x=LMARGIN, new_y=NEXT`.
- **Margins set after `add_page`** are ignored for content width.
- **A `` bullet** has no glyph in latin-1 core fonts and made fpdf refuse
  the line. Replaced with ASCII.
- **The autogenerated downgrade did not drop its enum types**, so a
  downgrade/upgrade cycle failed on "type already exists". Fixed in the
  migration.

---

## Session 9 — reliability, accessibility, and performance

### Verified working

**The test suite runs in half the time.** cProfile over the slowest file put
`bcrypt._bcrypt.hashpass` at 17.9s across 45 calls — the suite creates a user
per test and was hashing each password at the production work factor. The
factor is now `BCRYPT_ROUNDS` (default 12), and `conftest` sets it to 4 before
`app.core.security` builds its `CryptContext`. **The full suite went 225s to
131s.** Agent construction (0.34s for nine bundles), engine setup (~13s across
the suite) and MCP connection (26.6ms a call) were measured and ruled out
first.

**MCP toolsets are entered once per meeting.** Previously each agent call
opened and closed its toolset: ~27ms of setup per call, a quarter-second over
a ten-call meeting. An `AsyncExitStack` on the orchestrator now holds them for
the meeting's life, entered lazily on the serial path and pre-entered before
the concurrent assessment wave.

**An unknown cost is reported as unknown.** Pydantic AI has no price table for
`gpt-6-luna`, so every usage row recorded `estimated_cost_usd = 0.0` and the
configured `MEETING_COST_LIMIT_USD` silently enforced nothing.
`app/agents/pricing.py` now reads rates from `MODEL_PRICES`; with none
configured `estimate_cost` returns `None`, which a caller can tell apart from
"it was free". Backing it up is `MAX_TOTAL_TOKENS_PER_MEETING`, enforceable
whether or not a price is set because token counts are always known.
`Budget.exceeded_reason()` reports which ceiling was hit and the abort code is
`usage_limit`. Seven tests in `test_pricing.py` cover it, including that
malformed `MODEL_PRICES` disables pricing rather than crashing.

**Every route demands a token.** `test_authorization.py` reads the route list
from the app's own OpenAPI schema and calls all 36 non-public routes with no
`Authorization` header, asserting 401. Five routes are allow-listed as public
on purpose: `/health`, `/agents`, `/agents/{id}`, `/auth/register`,
`/auth/login`. A route added later without an auth dependency fails this test
rather than shipping.

**One organization cannot reach another's rows.** A second org with its own
owner is given the *real* ids of the first org's meeting, decision, action
item, consultation, document and memory, and gets 404 — not 403, which would
confirm the id exists — on 15 by-id endpoints and 5 write paths. Six list
endpoints return `[]` and `/company-profile` returns `null`.
`X-Organization-Id` pointed at a non-member org returns 403. **The sweep found
no holes:** the scoping was already correct everywhere, and what this adds is
the regression guard.

**Keyboard and screen-reader access across every page.** Audited against the
live DOM, not by reading source. What it found and what was fixed:

- *Focus rings were suppressed on 16 form controls.* `focus:outline-none`
  overrode the global `:focus-visible` outline, leaving a 1px border colour
  change on a near-black canvas as the only focus indicator (WCAG 2.4.7). The
  utility is gone from every input, textarea and select; it stays on the
  dialog and tab *containers*, which Radix focuses programmatically.
- *No skip link.* Four nav links, or nine participant buttons in the
  boardroom, sat between the top of every page and its content. Both shells
  now open with a "Skip to content" / "Skip to transcript" link, and `<main>`
  carries `id="main"`.
- *The boardroom had no `h1`* — the meeting title was a `<p>`, and every
  heading on the page was an `h3`.
- *Two inputs on Company Intelligence had only a placeholder* for a name, and
  three more were unlabelled once the audit covered the other tabs.
- *Heading levels skipped* `h1` to `h3` on the dashboard and Company
  Intelligence. `CardTitle` now takes an `as` prop instead of hard-coding
  `h3`.
- *The sidebar scrolled away* on long pages, taking the nav and sign-out with
  it; it is `sticky` on large screens now.

Re-audited after the fixes: every page reports one `h1`, no heading jumps, no
unnamed interactive element, no unlabelled control, a `<main>` landmark and a
skip link.

**Streaming content is announced without being read aloud.** The transcript
had no live region at all, so a screen-reader user got nothing as the meeting
progressed. Piping the transcript *into* a live region would be worse:
assessments run to a couple of hundred words and three can land at once. A
visually hidden `role="log"` announces arrivals — "Objection from Marcus Webb
to Alex Chen" — while each speaker's name became an `h2` so the transcript is
walkable by heading. A separate `role="status"` carries stage and terminal
status, so a queue of turns cannot bury "the meeting failed". The `aria-live`
that was on the "who is thinking" row is gone; it churned every few seconds
and would have drowned out the arrivals. Six tests in `Announcer.test.tsx`,
including that a finished meeting opened from scratch announces nothing.

**A render error no longer blanks the page.** There was no error boundary: any
bad render unmounted the tree and left a white screen with the error only in
the console. `ErrorBoundary` wraps the app and offers retry and reload, saying
plainly that the fault is in the page and the board's work is on the server.

**An expired token returns you to sign-in.** Access tokens expire while a tab
is open; every request then failed with a generic error behind a shell that
still looked signed in. `apiFetch` now drops a rejected token and fires
`ghostboard:unauthorized`, which `AuthGate` uses to clear the query cache.
**And there is a way to sign out** — `logout()` existed in `api/auth.ts` but
nothing had ever called it.

**Provider failures read as sentences.** The raw `f"{type(exc).__name__}:
{exc}"` went straight into `failure_reason`, which the boardroom shows and the
export includes — an unbounded provider blob. `summarize_agent_error`
classifies the common cases ("the model provider is rate-limiting this
workspace") and otherwise keeps the first line, capped at 200 characters. The
full exception and traceback stay in the log via `exc_info=True`.

**The PDF export keeps the board's punctuation.** fpdf declares its core fonts
WinAnsiEncoding, so their real repertoire is cp1252 — but the exporter encoded
to latin-1 first, which turned every em dash, curly quote, ellipsis and euro
sign into `?`. Setting `core_fonts_encoding = "cp1252"` and transliterating
per character (an unencodable `ā` folds to `a`; an encodable `é` is left
alone) fixed it. **Demonstrated on a real 4-page brief:** 7 em dashes, 22
bullets and 5 middots survive where all 34 were previously question marks.

**Three dependencies were missing from `pyproject.toml`.** `pypdf`,
`python-docx` and `fpdf2` were imported by `services/ingestion.py` and
`services/export.py` but never declared, so a clean `pip install -e ".[dev]"`
produced an app that crashed on the first document upload. Now declared.

**The migration chain round-trips.** `upgrade head`, `downgrade base`,
`upgrade head` again on a fresh database, then `alembic check` reports no
drift against the ORM models.

**Three frontend dependencies were dead.** `recharts`, `zustand` and
`@radix-ui/react-tooltip` were declared and imported nowhere; removed. They
were already tree-shaken, so the bundle is unchanged at 541 kB — the win is
install time and an honest manifest. `motion` *is* used, via `motion/react`.

### Corrected during this session

**A wrapper made every portrait announce twice.** Adding `role="img"` to the
dashboard's roster strip looked like an improvement until the re-audit counted
18 images for nine executives: `PortraitFrame` already carries `role="img"`
and a full label. The wrapper is a plain box again.

### Known limitations

**Bundle size.** 541 kB (167 kB gzipped) in one chunk, over Vite's 500 kB
warning. Route-level code splitting would help, but every route past sign-in
needs the portraits and the query client, so the saving is small and the
Suspense boundaries are real risk this late. Left as-is, deliberately.

**`ruff format` is not a gate.** `ruff check` passes clean, but the project
has never been `ruff format`-ed and running it now would reformat 38 files for
no behavioural gain. `ruff check` remains the lint contract.

**B904 across 14 raise sites.** Widening the ruff rule set to `B` surfaces
`raise ... from err` suggestions throughout the API layer. Real, but a
refactor of its own rather than Phase 9 polish; the enabled rule set is
unchanged.

**No automated accessibility test.** The audit ran against the live DOM in a
browser and the fixes are covered by unit tests, but nothing re-runs the
sweep. An axe-core pass inside vitest would close that.

**The cost ceiling still needs a price.** `MODEL_PRICES` is unset by default
and this project has no authoritative rate for `gpt-6-luna`, so cost
enforcement is opt-in. The token ceiling is what actually binds out of the
box — which is the honest arrangement, not a workaround.

---

## Reproducing the primary workflow

Prerequisites: PostgreSQL running, `PORTKEY_API_KEY` in the repo-root `.env`.

```bash
cd backend && ./.venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend && npm run dev
```

Open <http://localhost:5173>, create a workspace, then **Meetings → New
meeting**. Pick a question, choose who attends, and convene. Watch the Chair
open the meeting and the executives work. Refresh mid-meeting — the transcript
rebuilds from the event log and the stream resumes from where it left off.

Headless equivalents:

```bash
cd backend && ./.venv/Scripts/python.exe -m scripts.demo_meeting
```

```bash
cd backend && ./.venv/Scripts/python.exe -m scripts.demo_consultation --agents cfo customer_advocate
```

**A Full Board meeting (all nine agents), or a Devil's Advocate run:**

```bash
curl -s -X POST localhost:8000/api/meetings -H "Content-Type: application/json"   -H "Authorization: Bearer $TOKEN"   -d '{"question":"...","mode":"full_board","start_immediately":true}'
```

Or pick the mode in the UI at **Meetings → New meeting**.

**Direct a live meeting:**

Start a meeting, and while it is running click any executive in the left rail.
Pick a kind, type your instruction, and send. It is answered at the next safe
point and appears in the transcript as a pair: your question, then their
reply. Pause holds the meeting so you can ask several.

**Prove the board uses an uploaded document:**

Upload a file on the **Company** page, then ask a meeting a question whose
premise the document contradicts. The Knowledge tab's search box shows what a
meeting on that question would retrieve before you run it.

**A real MCP tool call, with the audit row printed:**

```bash
cd backend && ./.venv/Scripts/python.exe -m scripts.demo_mcp
cd backend && ./.venv/Scripts/python.exe -m scripts.demo_mcp --agent coo
```

**Check the PDF export keeps its characters:**

```bash
curl -s -H "Authorization: Bearer $TOKEN" "localhost:8000/api/decisions/$DECISION_ID/export?format=pdf" -o brief.pdf
```

```bash
cd backend && ./.venv/Scripts/python.exe -c "from pypdf import PdfReader; t=''.join(p.extract_text() for p in PdfReader('../brief.pdf').pages); print({hex(ord(c)) for c in t if ord(c)>127})"
```

Em dashes (`0x2014`), bullets (`0x2022`) and middots (`0xb7`) should all be
present. Before Session 9 every one of them was a `?`.

**Re-run the accessibility audit:** open any page and, in the browser console,
check that no interactive element lacks an accessible name, no form control
lacks a label, there is exactly one `h1`, and the first focusable element is a
skip link. Tab from the top of the page: the first stop should be "Skip to
content", and every field should show a violet focus ring.

**Check the authorization sweep by hand** — any endpoint without a token:

```bash
curl -s -o /dev/null -w "%{http_code}\n" localhost:8000/api/meetings
```

Should print `401`. `/api/health` and `/api/agents` are the only read routes
that answer without one.

**Tests:**


```bash
cd backend && ./.venv/Scripts/python.exe -m pytest -q && ./.venv/Scripts/python.exe -m ruff check app tests scripts
```

```bash
cd frontend && npx tsc --noEmit && npx vitest run
```

---

## Test and check results (end of Session 9)

| Check | Result |
| --- | --- |
| `pytest` (backend) | **270 passed in 131s** |
| — meeting orchestration | 38 |
| — knowledge and ingestion | 35 |
| — MCP tools | 34 |
| — interventions, pause, export | 32 |
| — meeting modes | 25 |
| — agent factory | 22 |
| — consultations API | 20 |
| — meetings API | 17 |
| — SSE stream | 15 |
| — registry | 11 |
| — **authorization sweep** | **9** |
| — **model pricing** | **7** |
| — agents API | 5 |
| `ruff check` (backend) | All checks passed |
| `alembic upgrade / downgrade / upgrade` | Clean round-trip on a fresh database |
| `alembic check` | No drift |
| `tsc --noEmit` (frontend) | Clean |
| `vitest run` (frontend) | **65 passed, 6 files** |
| — boardroom reducer | 22 |
| — SSE parser | 11 |
| — transcript / rail rendering | 11 |
| — executive card + portraits | 9 |
| — **screen-reader announcer** | **6** |
| — structured panels | 6 |
| `npm run build` | Clean, 541 kB / 167 kB gzipped |
| Accessibility audit (live DOM, 6 pages + 3 tabs) | No findings remaining |
| Live meeting from the UI | Verified: streamed, refreshed, 18 entries intact |
| Live MCP tool call | Verified: CFO runway, COO capacity, both audited |
| Live Full Board | Verified: 9 participants, 8 assessments, 6 challenges |
| Live Devil's Advocate | Verified: attacked a real prior decision |
| Live document-grounded meeting | Verified: board rejected a false premise from an uploaded file |
| Live intervention | Verified: COO withdrew a claim under challenge |
| Live PDF export | Verified: 4 pages, 34 non-ASCII characters intact |
