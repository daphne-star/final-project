"""Aggregates every versioned route under the API prefix."""

from fastapi import APIRouter

from app.api import (
    routes_agents,
    routes_auth,
    routes_consultations,
    routes_health,
    routes_knowledge,
    routes_meetings,
    routes_organizations,
)

api_router = APIRouter()
api_router.include_router(routes_health.router)
api_router.include_router(routes_auth.router)
api_router.include_router(routes_organizations.router)
api_router.include_router(routes_agents.router)
api_router.include_router(routes_consultations.router)
api_router.include_router(routes_meetings.router)
api_router.include_router(routes_knowledge.router)
