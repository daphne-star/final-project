"""The Ghost Board MCP server.

Runs in-process for now. Every tool is registered through ``_register``, which
is the single place that enforces authorization, records the invocation, and
normalises errors — so a tool author cannot forget any of it.

Transport note: nothing in this module or in ``app/mcp/tools/`` knows how it
is reached. Moving to Streamable HTTP later means serving this same
``FastMCP`` instance over a different transport and pointing ``MCPToolset`` at
a URL; the tool bodies do not change. The one thing that would need rework is
``app/mcp/context.py``, because a cross-process server cannot read a
contextvar — it would carry the scope in a server-validated token instead.
That boundary is deliberate and documented rather than designed around
prematurely.
"""

from __future__ import annotations

import inspect
import logging
import time
from collections.abc import Callable
from typing import Any, get_type_hints

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import BaseModel

from app.agents.registry import ToolScope
from app.db.session import AsyncSessionLocal
from app.mcp.context import ToolAuthorizationError, ToolContext, current_context
from app.mcp.tools import company, financial, operations
from app.models.enums import ToolInvocationStatus
from app.models.meeting import ToolInvocation

logger = logging.getLogger(__name__)

#: Which scope each tool needs. The registry on each executive says which
#: scopes it holds; the two together decide who may call what.
TOOL_SCOPES: dict[str, ToolScope] = {
    "get_company_profile": ToolScope.COMPANY,
    "get_company_goals": ToolScope.COMPANY,
    "search_company_knowledge": ToolScope.COMPANY,
    "get_previous_decisions": ToolScope.COMPANY,
    "calculate_cash_runway": ToolScope.FINANCIAL,
    "calculate_unit_economics": ToolScope.FINANCIAL,
    "compare_financial_scenarios": ToolScope.FINANCIAL,
    "assess_execution_capacity": ToolScope.OPERATIONS,
    "identify_operational_dependencies": ToolScope.OPERATIONS,
    "build_implementation_plan": ToolScope.OPERATIONS,
}


async def _record_invocation(
    ctx: ToolContext,
    tool_name: str,
    arguments: dict[str, Any],
    *,
    status: ToolInvocationStatus,
    result: dict[str, Any] | None,
    error: str | None,
    duration_ms: int,
) -> None:
    """Audit every call (spec section 8).

    Opens its own session: tools can run concurrently and must not share the
    orchestrator's. Logging failure is swallowed — losing an audit row is bad,
    but failing the tool call the agent is waiting on is worse, and the error
    is logged either way.
    """
    try:
        async with AsyncSessionLocal() as db:
            db.add(
                ToolInvocation(
                    organization_id=ctx.organization_id,
                    meeting_id=ctx.meeting_id,
                    consultation_id=ctx.consultation_id,
                    agent_id=ctx.agent_id.value,
                    tool_name=tool_name,
                    arguments=arguments,
                    result=result,
                    status=status,
                    error_message=error[:2000] if error else None,
                    duration_ms=duration_ms,
                )
            )
            await db.commit()
    except Exception:
        logger.exception(
            "AUDIT GAP: failed to record invocation of %s for org %s",
            tool_name,
            ctx.organization_id,
        )


def _jsonable(value: Any) -> Any:
    """Make a value safe to store in JSONB.

    Tool arguments arrive as validated Pydantic models, which asyncpg cannot
    serialize. Without this the audit insert fails — and because the audit
    path deliberately swallows its own errors, the row would vanish silently.
    """
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _register(mcp: FastMCP, func: Callable[..., Any], scope: ToolScope) -> None:
    """Wrap one tool with authorization, auditing, and error normalisation."""
    name = func.__name__
    is_async = inspect.iscoroutinefunction(func)

    async def invoke(**kwargs: Any) -> Any:
        started = time.perf_counter()
        try:
            ctx = current_context()
        except ToolAuthorizationError as exc:
            # No bound scope: refuse rather than guess an organization.
            logger.warning("Unscoped call to %s refused", name)
            raise ToolError(str(exc)) from exc

        try:
            ctx.require(scope, name)
        except ToolAuthorizationError as exc:
            await _record_invocation(
                ctx,
                name,
                _jsonable(kwargs),
                status=ToolInvocationStatus.DENIED,
                result=None,
                error=str(exc),
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
            raise ToolError(str(exc)) from exc

        try:
            result = await func(**kwargs) if is_async else func(**kwargs)
        except Exception as exc:
            duration = int((time.perf_counter() - started) * 1000)
            message = f"{type(exc).__name__}: {exc}"
            logger.warning("Tool %s failed: %s", name, message)
            await _record_invocation(
                ctx,
                name,
                _jsonable(kwargs),
                status=ToolInvocationStatus.FAILED,
                result=None,
                error=message,
                duration_ms=duration,
            )
            # Surfaced to the agent as a tool error it can react to, not a
            # silent empty result (spec: no silent failures).
            raise ToolError(f"{name} failed: {message}") from exc

        duration = int((time.perf_counter() - started) * 1000)
        payload = _jsonable(result)
        await _record_invocation(
            ctx,
            name,
            _jsonable(kwargs),
            status=ToolInvocationStatus.SUCCEEDED,
            result=payload if isinstance(payload, dict) else {"result": payload},
            error=None,
            duration_ms=duration,
        )
        # Return the model, not the dict: FastMCP serializes against the
        # declared return annotation and warns if handed a bare dict.
        return result

    invoke.__name__ = name
    invoke.__doc__ = inspect.getdoc(func) or name
    # Preserve the typed signature so FastMCP derives the real input schema
    # from the Pydantic models rather than from **kwargs. The annotations have
    # to be *resolved* here: the tool modules use `from __future__ import
    # annotations`, so copying the raw strings would leave FastMCP trying to
    # evaluate names like "RunwayInput" in this module, where they do not exist.
    hints = get_type_hints(func)
    invoke.__annotations__ = hints
    invoke.__signature__ = inspect.signature(func).replace(  # type: ignore[attr-defined]
        parameters=[
            param.replace(annotation=hints.get(param_name, param.annotation))
            for param_name, param in inspect.signature(func).parameters.items()
        ],
        return_annotation=hints.get("return", inspect.Signature.empty),
    )

    mcp.tool(invoke)


def build_mcp_server() -> FastMCP:
    """Construct the server with every Ghost Board tool registered."""
    mcp = FastMCP(
        "ghost-board",
        instructions=(
            "Company intelligence, financial calculation, and operational "
            "analysis tools for the Ghost Board executive agents. Every tool is "
            "scoped to the calling organization by the server; none accepts an "
            "organization identifier."
        ),
    )

    for func in (
        company.get_company_profile,
        company.get_company_goals,
        company.search_company_knowledge,
        company.get_previous_decisions,
        financial.calculate_cash_runway,
        financial.calculate_unit_economics,
        financial.compare_financial_scenarios,
        operations.assess_execution_capacity,
        operations.identify_operational_dependencies,
        operations.build_implementation_plan,
    ):
        _register(mcp, func, TOOL_SCOPES[func.__name__])

    return mcp


_SERVER: FastMCP | None = None


def get_mcp_server() -> FastMCP:
    """The process-wide server instance, built on first use."""
    global _SERVER
    if _SERVER is None:
        _SERVER = build_mcp_server()
        logger.info("Ghost Board MCP server built with %d tools", len(TOOL_SCOPES))
    return _SERVER


def tools_for_scopes(scopes: tuple[ToolScope, ...]) -> set[str]:
    """Tool names an agent holding these scopes may see."""
    allowed = set(scopes)
    return {name for name, scope in TOOL_SCOPES.items() if scope in allowed}
