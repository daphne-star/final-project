# Ghost Board

An AI executive boardroom. Nine distinct Pydantic AI agents assess a strategic
question independently, debate it, and produce a decision brief you can act on.

**Status: Phases 1–4 of 9 complete (backend).** Foundation, visual identity,
the Pydantic AI agent engine, and the multi-agent board meeting engine are
built and tested. You can hold a one-on-one consultation with any of the
eight consultable executives, and convene a real board meeting with
independent assessments, evidence-based debate, revisions, and a decision
brief. The live boardroom UI and SSE streaming are still to come.

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

Set `SECRET_KEY`. `PORTKEY_API_KEY` is already in the repo-root `.env` and is
picked up automatically — the backend searches the repo root, `final-project/`,
and `backend/` in that order.

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
│   │   ├── orchestration/       # meeting state machine + typed events
│   │   ├── services/            # consultation and meeting services
│   │   ├── models/              # 22 ORM entities
│   │   └── schemas/             # request/response models
│   ├── alembic/versions/        # 0001_initial, 0002_consult_msgs
│   ├── scripts/                 # demo_consultation.py, demo_meeting.py
│   └── tests/
└── frontend/
    └── src/
        ├── assets/executives/   # nine original SVG portraits
        ├── components/agents/   # ExecutiveCard, ExecutiveDetail
        ├── components/consultations/  # StructuredPanels
        ├── components/auth/     # AuthGate
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

**Organization scope is server-side.** `X-Organization-Id` only selects among
orgs the authenticated user already belongs to; it can never widen access. No
model-supplied org id is ever trusted for authorization.

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
| 4 | Meeting engine: agenda, assessments, debate, revision, synthesis | Done (backend) |
| 4b | Live boardroom UI + SSE streaming | Next |
| 5 | MCP server and tools | |
| 6 | All nine agents, Full Board / Devil's Advocate modes | |
| 7 | Company intelligence, documents, memory | |
| 8 | Interventions, pause/resume, export | |
| 9 | Reliability, accessibility, polish | |
