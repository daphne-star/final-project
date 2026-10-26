"""Read-only access to the fixed executive roster.

The roster is static, so these endpoints need no org scope and no auth — they
return the same nine public executive descriptions for everyone.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.agents.registry import ROSTER, ExecutiveDefinition, get_definition

router = APIRouter(tags=["agents"])


@router.get("/agents", response_model=list[ExecutiveDefinition])
async def list_agents() -> list[ExecutiveDefinition]:
    return list(ROSTER)


@router.get("/agents/{agent_id}", response_model=ExecutiveDefinition)
async def get_agent(agent_id: str) -> ExecutiveDefinition:
    try:
        return get_definition(agent_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"No executive with id {agent_id!r}"
        )
