# Ghost Board

An AI executive boardroom. Nine distinct Pydantic AI agents assess a strategic
question independently, debate it, and produce a decision brief you can act on.

**Status: all nine phases complete.** Foundation, visual identity, the
Pydantic AI agent engine, the multi-agent meeting engine, and the live
streaming boardroom are built and tested. You can convene a board meeting
from the UI and watch the Chairperson and four executives analyse, argue,
and revise in real time, then read the decision brief. Refreshing mid-meeting
rebuilds the transcript and resumes the stream. Executives call real MCP
tools for company data and financial or operational arithmetic. Five meeting
modes run from a single executive up to the full nine-agent board, and the
board reasons over documents you upload. You can interrupt a meeting in
progress to put something to one executive directly, pause it, and export the
brief. Phase 9 added a token and cost ceiling that can actually bind, an
authorization sweep over every route, keyboard and screen-reader support
across all pages, and a halving of the test suite's runtime.

See [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md) for what is
verified versus merely implemented, and
[docs/PRODUCT_SPEC.md](docs/PRODUCT_SPEC.md) for the binding requirements.

---

## Stack

| Layer | Choice |
| --- | --- |
| Frontend | React 18, TypeScript, Vite 6, Tailwind v4, shadcn/ui conventions, TanStack Query, React Router |
| Backend | Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2 (async), Alembic |
| Database | PostgreSQL 17 (native install — this machine has no Docker) |
| AI | Pydantic AI, OpenAI-compatible calls routed through Portkey (`gpt-6-luna`) |

## Prerequisites

- Python 3.11+ (3.13 used here)
- Node 20+ (24 used here)
- PostgreSQL 17, running locally on port 5432

## Setup

### 1. PostgreSQL

Already installed and initialized on this machine as a **user-level cluster**
(the EDB installer needs UAC elevation, so the official binary archive was
extracted instead). It does not start on boot — start it each session:

```bash
"C:/Users/daphn/pgsql-dl/pgsql/bin/pg_ctl.exe" -D "C:/Users/daphn/pgdata" -l "C:/Users/daphn/pgdata/server.log" -o "-p 5432" start
```

Databases `ghostboard` and `ghostboard_test` already exist. To set this up on
a different machine, either install PostgreSQL 17 normally, or repeat the
portable route: download
`postgresql-17.11-1-windows-x64-binaries.zip` from EnterpriseDB, extract it,
then `initdb -D <datadir> -U postgres` and `createdb ghostboard`.

### 2. Environment

```bash
cp .env.example .env
```

Set `SECRET_KEY` and `PORTKEY_API_KEY`.

The backend looks for a `.env` in **two** places, resolved from the source
file rather than the working directory, so it does not matter where you
launch it from:

| Location | When to use it |
| --- | --- |
| this repo's own folder | a key just for this project |
| the folder above it | one key shared by several checkouts |

If both exist, this repo's own `.env` wins. A real environment variable beats
both, which is how a container or CI secret works with no file at all. The
rule is pinned by `backend/tests/test_config.py`.

### 3. Backend

```bash
cd backend && python -m venv .venv && ./.venv/Scripts/python.exe -m pip install -e ".[dev]"
```

Apply migrations (requires Postgres to be running):

```bash
cd backend && ./.venv/Scripts/python.exe -m alembic upgrade head
```

Run it:

```bash
cd backend && ./.venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000
```

API docs: <http://localhost:8000/api/docs>

### 4. Frontend

```bash
cd frontend && npm install && npm run dev
```

App: <http://localhost:5173>. Vite proxies `/api` to port 8000, so there is no
CORS hop and no API base URL in the client bundle.

## Tests

```bash
cd backend && ./.venv/Scripts/python.exe -m pytest -q
```

```bash
cd frontend && npx tsc --noEmit && npx vitest run
```

The backend suite needs PostgreSQL running (it uses `ghostboard_test`), but
**no suite makes a paid model call** — agent runs are driven by a deterministic
recording model. To exercise the real provider, run the demo script:

```bash
cd backend && ./.venv/Scripts/python.exe -m scripts.demo_consultation --agents cfo customer_advocate
```

Or convene a full board meeting on the seeded Northstar Labs company:

```bash
cd backend && ./.venv/Scripts/python.exe -m scripts.demo_meeting
```

In the UI, go to **Meetings → New meeting**, pick a question and who attends,
and watch it happen live.

## Layout

```
final-project/
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   ├── registry.py      # the fixed nine-executive roster
│   │   │   ├── factory.py       # one Pydantic AI Agent per executive
│   │   │   ├── deps.py          # typed per-run dependencies
│   │   │   ├── provider.py      # Portkey / OpenAI model wiring
│   │   │   ├── schemas.py       # structured agent outputs
│   │   │   ├── meeting_schemas.py  # agenda, debate, revision, brief
│   │   │   └── prompts/         # shared rules + nine role instruction sets
│   │   ├── api/                 # routes + auth/org dependencies
│   │   ├── core/                # settings, security
│   │   ├── db/                  # engine, session, declarative base
│   │   ├── mcp/                 # FastMCP server, auth context, tools
│   │   ├── orchestration/       # state machine, modes, events, interventions, SSE
│   │   ├── services/            # consultation, meeting, knowledge, ingestion, export
│   │   ├── models/              # 23 ORM entities
│   │   └── schemas/             # request/response models
│   ├── alembic/versions/        # 0001_initial .. 0006_token_usage
│   ├── scripts/                 # demo_consultation, demo_meeting, demo_mcp
│   └── tests/
└── frontend/
    └── src/
        ├── assets/executives/   # nine original SVG portraits
        ├── components/agents/   # ExecutiveCard, ExecutiveDetail
        ├── components/boardroom/      # rail, transcript, sidebar, progress, announcer
        ├── components/consultations/  # StructuredPanels
        ├── hooks/               # useMeetingStream
        ├── lib/boardroomState.ts  # pure event reducer
        ├── components/auth/     # AuthGate
        ├── components/ErrorBoundary.tsx
        ├── components/ui/       # shadcn-convention primitives
        └── pages/
```

## Design notes

**Dark, not pastel.** The repo-wide `AGENTS.md` asks for pastel web apps; Ghost
Board deliberately overrides that with the spec's premium dark boardroom
palette. Other apps in this repo still follow `AGENTS.md`.

**The portraits are original.** Nine hand-built SVG illustrations in
`src/assets/executives/`, informed by the card-art conventions of minimalist
mobile games but copying no existing artwork. Each executive has a distinct
silhouette, palette, emblem and accessory, and is identifiable without reading
the name. `ExecutiveCard` throws rather than falling back to a placeholder if a
portrait is missing — the illustrations are product, not decoration.

**An intervention is a row, not a button.** Interrupting a meeting writes a
queued record that the running orchestrator drains at its next checkpoint —
between stages, never inside one — so a founder cannot corrupt a round in
flight, and the exchange survives in the meeting's history.

**Nothing an agent infers becomes a fact.** Every stored item carries its
provenance, `USER_CONFIRMED` requires a human id at the database write, and
corrections supersede rather than overwrite. Retrieved records reach agents
labelled VERIFIED or UNVERIFIED and wrapped as data, never instructions.

**No MCP tool takes an organization id.** Scope comes from a context the
orchestrator binds around each agent run, so a model has nowhere to put a
spoofed id. Per-role filtering keeps each executive's tool list short; the
server re-checks the scope on every call, so filtering is convenience and the
server check is the boundary.

**Streaming reads the database, not a queue.** The SSE endpoint tails the
persisted event log, so reconnection is just "read after cursor N" and a
client that joins late — or after the meeting ended — sees the identical
ordered history. The orchestrator commits each event as it is emitted, which
is what makes that readable from another session. The trade is ~0.4s of
latency for durability without Redis.

**Organization scope is server-side.** `X-Organization-Id` only selects among
orgs the authenticated user already belongs to; it can never widen access. No
model-supplied org id is ever trusted for authorization.

**The cost estimate is measured, not derived.** The New Meeting hint could
have predicted model calls and multiplied by a tokens-per-call figure; checked
against real runs, that understates a Full Board roughly twofold, because the
call formula ignores debate rounds. It instead takes the median of what this
organization's own past meetings in the same mode actually used, widening to
all modes — scaled by relative size — only when this mode has no history, and
saying which it did.

**Usage is measured in tokens, not calls.** A request count says how many
times the board was asked something, not how much work it did: across real
meetings here, calls varied threefold for the same question shape while tokens
tracked the actual reasoning. The meeting carries `input_tokens_used` and
`output_tokens_used`, totalled by a property so the sum cannot drift from its
parts, and the running total rides on `stage_changed` rather than getting an
event of its own — `_emit` commits, and a counter worth six updates does not
justify ten more commits. `model_requests_used` stays as a runaway guard, not
as a figure anyone is shown.

**An unknown cost is not a zero.** Pydantic AI has no price table for
`gpt-6-luna`, so every usage row used to record `0.00` and the configured cost
ceiling enforced nothing. Prices now come from `MODEL_PRICES`; with none set,
`estimate_cost` returns `None` and says so. Backing it up is a token ceiling,
which is enforceable whether or not anyone configured a price, because token
counts are always known.

**The transcript announces arrivals, not contents.** Assessments run to a
couple of hundred words and three can land at once, so piping the transcript
into a live region would be unusable. A visually hidden `role="log"` announces
who spoke and what kind of turn it was; the transcript itself is a list of
headings a screen-reader user walks at their own pace.

**Provenance is a column, not a convention.** `CompanyMemory.source_kind`
records whether a fact was user-confirmed, imported from a document, or
inferred by a model, so an unverified assumption cannot quietly become a
company fact.

## Roadmap

| Phase | Scope | Status |
| --- | --- | --- |
| 1 | Monorepo, FastAPI, Postgres schema, auth, navigation | Done |
| 2 | Nine portraits, executive cards, My Board, design system | Done |
| 3 | Pydantic AI agent factory, consultations | Done |
| 4 | Meeting engine: agenda, assessments, debate, revision, synthesis | Done |
| 4b | SSE streaming + live boardroom UI | Done |
| 5 | MCP server and tools | Done |
| 6 | All nine agents, Full Board / Devil's Advocate modes | Done |
| 7 | Company intelligence, documents, memory | Done |
| 8 | Interventions, pause/resume, export | Done |
| 9 | Reliability, accessibility, polish | Done |
