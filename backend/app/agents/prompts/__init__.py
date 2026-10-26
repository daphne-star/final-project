"""Agent instruction text, kept out of the API and service layers."""

from app.agents.prompts.roles import ROLE_INSTRUCTIONS, role_instructions
from app.agents.prompts.shared import ONE_ON_ONE_SUFFIX, SHARED_RULES

__all__ = [
    "ONE_ON_ONE_SUFFIX",
    "ROLE_INSTRUCTIONS",
    "SHARED_RULES",
    "role_instructions",
]
