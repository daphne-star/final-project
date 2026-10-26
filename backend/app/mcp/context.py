"""Server-side authorization context for MCP tool calls.

The spec is blunt about this: *never rely only on a model-supplied
organization id to authorize a tool operation*. So no tool takes an
`organization_id` argument. The orchestrator binds the authenticated scope to
a context variable before running an agent, and the tool layer reads it from
there. A model that invents an org id has nothing to invent it into.

Context variables carry correctly across `await` and are isolated per asyncio
task, which is what makes this safe while four assessments run concurrently.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from app.agents.registry import AgentId, ToolScope


class ToolAuthorizationError(RuntimeError):
    """Raised when a tool runs with no authorized scope, or outside its remit."""


@dataclass(frozen=True, slots=True)
class ToolContext:
    """Who is calling, on whose behalf, and what they may touch."""

    organization_id: uuid.UUID
    agent_id: AgentId
    allowed_scopes: frozenset[ToolScope]
    user_id: uuid.UUID | None = None
    meeting_id: uuid.UUID | None = None
    consultation_id: uuid.UUID | None = None

    def require(self, scope: ToolScope, tool_name: str) -> None:
        if scope not in self.allowed_scopes:
            raise ToolAuthorizationError(
                f"{self.agent_id.value} is not authorized to call {tool_name!r} "
                f"(requires the {scope.value} tool scope)."
            )


_CURRENT: ContextVar[ToolContext | None] = ContextVar("ghostboard_tool_context", default=None)


def current_context() -> ToolContext:
    """The active authorization context, or an error.

    Failing closed matters: if this were to return a default, a tool invoked
    outside a bound scope would read some other organization's data.
    """
    ctx = _CURRENT.get()
    if ctx is None:
        raise ToolAuthorizationError(
            "No tool context is bound. Tools may only run inside an agent run "
            "started by the application."
        )
    return ctx


@contextmanager
def bind_context(ctx: ToolContext) -> Iterator[ToolContext]:
    """Bind the scope for the duration of one agent run."""
    token = _CURRENT.set(ctx)
    try:
        yield ctx
    finally:
        _CURRENT.reset(token)
