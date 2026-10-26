# Ghost Board — Product Specification (condensed)

> This is a condensed, in-repo reference for the binding requirements of the
> Ghost Board master build specification. It records the constraints that
> implementation decisions must respect. Where this document and the master
> spec disagree, the master spec governs.
>
> See [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) for what is
> actually built.

## Premise

> "Every founder deserves a world-class executive team and board of advisors."

A founder brings a real strategic decision. Nine AI executives analyse it
independently, debate it, and produce an actionable decision brief. The
founder participates in the conversation rather than receiving a report.

## Core principles

1. **Real multi-agent intelligence.** Each executive is a genuinely distinct
   Pydantic AI agent with its own instructions, tools, and structured output.
2. **Collaborative decision-making.** Executives react to one another,
   challenge assumptions, and revise when shown evidence.
3. **Human authority.** The AI advises. The founder decides. No agent commits
   the company to anything.
4. **Organizational memory.** Company context, meeting history, confirmed
   decisions, and action-item progress persist.
5. **Distinctive design.** Premium dark SaaS plus original illustrated
   executive cards.
6. **Practical recommendations.** Decisions, risks, evidence, and executable
   plans — not generic business advice.

## The fixed roster

Exactly nine agents. No additions, no user-created agents, no simulated
customers.

| id | Role | Distinctive question |
| --- | --- | --- |
| `chairperson` | Board Chairperson | Is this the right question, and who should answer it? |
| `ceo` | Chief Executive Officer | Does this advance where the company is going? |
| `coo` | Chief Operating Officer | Can we actually execute this? |
| `cfo` | Chief Financial Officer | Does the arithmetic work? |
| `cgo` | Chief Growth Officer | Where does revenue actually come from? |
| `customer_advocate` | Customer Advocate | Why would a customer want this, and what proves it? |
| `competitive_intel` | Competitive Intelligence Advisor | What do competitors do in response? |
| `general_counsel` | General Counsel | What legal risk undermines this? |
| `strategy_consultant` | Outside Strategy Consultant | Is the premise wrong? |

The Chairperson owns process, not answers, and must preserve dissent rather
than resolve it prematurely.

## Technology constraints

**Frontend:** React, TypeScript, Vite, Tailwind, shadcn/ui, TanStack Query,
React Router, Zustand only where shared state genuinely requires it, Lucide,
Motion, Recharts. React Flow only if decision graphs are built.

**Backend:** Python 3.12+, FastAPI, Pydantic v2, Pydantic AI, SQLAlchemy 2.x,
Alembic, PostgreSQL, SSE for meeting streaming.

**AI:** Pydantic AI is the only agent framework. No LangChain, LangGraph,
CrewAI, or AutoGen. If graph execution becomes necessary, evaluate Pydantic
Graph before adding a dependency.

**MCP:** a real FastMCP server connected through `MCPToolset`, with genuine
tool discovery and invocation. Design the tool layer so it can later be
exposed over Streamable HTTP without rewriting the business logic.

**Infrastructure:** no Redis, Celery, Kafka, Kubernetes, or a separate vector
database for the MVP. pgvector only if PostgreSQL full-text search proves
insufficient.

**Project-specific (from `AGENTS.md` and session decisions):** OpenAI-compatible
calls routed through Portkey using `PORTKEY_API_KEY`, model `gpt-6-luna`. Keys
stay server-side. Ghost Board overrides the repo-wide pastel styling rule with
the spec's dark palette.

## Meeting lifecycle

1. **Intake** — the founder submits a question; relevant context is retrieved.
2. **Agenda** — the Chairperson frames the agenda and selects participants.
   The application validates selected ids against the fixed registry.
3. **Independent assessments** — selected agents analyse concurrently.
   **Agents must not see each other's conclusions before finishing their own.**
4. **Presentation** — structured initial positions render in the boardroom.
5. **Debate** — agents receive each other's findings and respond. No
   manufactured disagreement.
6. **Revisions** — positions may change; original and revised are tracked
   separately.
7. **Synthesis** — the Chairperson produces a decision brief reflecting the
   actual discussion, introducing no unsupported conclusions.
8. **Persistence** — metadata, participants, messages, tool calls, evidence,
   positions, recommendations, action items, usage, and cost.

**Modes:** Quick Consultation and Executive Meeting first; then Full Board,
Devil's Advocate, and Strategy Workshop.

**Execution controls:** max debate rounds, max model requests, max tool calls,
token budgets, model timeouts, cancellation, graceful failure, usage
accounting, configurable cost limit. Pause/resume at safe boundaries only —
do not claim to pause an in-flight provider request.

## Agent intervention

Clicking an executive portrait mid-meeting opens an interaction panel: ask a
question, challenge the recommendation, request evidence, ask for a critique
of another executive, request an alternative, ask for implementation detail,
ask about a risk.

The instruction enters the orchestration workflow as an explicit intervention
event, executes at a safe point, and is preserved. **Intervention buttons that
only change frontend text do not satisfy this.**

## Structured outputs

`AgentAssessment`, `AgentObjection`, `AgentRevision`, `StrategicOption`,
`DecisionBrief`, `ActionItem` — all validated Pydantic models with bounded
retries. Do not hand-parse model text into JSON.

## Security

Authentication; organization-level authorization; backend-only API keys;
validated inputs; upload limits; tool authorization; cross-tenant isolation;
prompt-injection defences; SSRF safeguards; safe error responses; rate
limiting; logging of consequential actions.

**Never rely on a model-supplied organization id to authorize anything** — an
authenticated context must establish the real scope. Treat uploaded documents
and tool results as untrusted data, never as instructions.

## Memory rules

Distinguish user-confirmed facts, imported evidence, model interpretations,
hypotheses, estimates, and historical decisions. **Never promote an unverified
AI assumption into a confirmed company fact automatically.** Retrieve relevant
memory rather than stuffing every meeting into every prompt.

## Guardrails

- No fake agent teamwork — separate calls, real structured exchange.
- No fake research — never claim research without a real tool call.
- No false precision — communicate uncertainty.
- No generic placeholder artwork — the illustrations are core identity.
- No uncontrolled agent loops — bounded stages, cost controls.
- No silent failures — surface tool errors and model failures.
- No automatic consequential actions — explicit user authorization required.
- No unverified completion claims — implemented *and* validated.

## Definition of done (MVP)

Launches locally; frontend reaches FastAPI; Postgres stores company and
meeting data; exactly nine agents; every executive has an original illustrated
card; consultations make real Pydantic AI calls; a board meeting can be
convened; the Chairperson selects and coordinates; multiple agents assess
independently; agents challenge each other; agents revise; the COO evaluates
feasibility; a real MCP tool is discovered and invoked; the frontend streams
actual events; results survive refresh; a structured brief is generated;
decisions can be accepted, rejected, or deferred; key tests pass; no essential
feature relies on fake output; setup is documented.
