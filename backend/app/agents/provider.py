"""Model provider wiring.

AGENTS.md pins this project to OpenAI-compatible calls routed through the
Portkey gateway. Pydantic AI talks to that through ``OpenAIChatModel`` with an
``OpenAIProvider`` pointed at the gateway base URL, so swapping provider later
is a change in this module alone — no agent definition references a provider.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
from pydantic_ai.providers.openai import OpenAIProvider

from app.core.config import settings

logger = logging.getLogger(__name__)


class ProviderNotConfigured(RuntimeError):
    """Raised when a real model run is attempted without an API key.

    Surfaced to the caller as a 503 rather than swallowed — spec section 22
    forbids silently substituting fake output for an unavailable model.
    """


@lru_cache
def _provider() -> OpenAIProvider:
    if not settings.portkey_api_key:
        raise ProviderNotConfigured(
            "PORTKEY_API_KEY is not set. Add it to the .env at the repo root "
            "to enable real model calls."
        )
    return OpenAIProvider(
        base_url=settings.portkey_base_url,
        api_key=settings.portkey_api_key,
    )


def build_model(model_name: str | None = None) -> Model:
    """Return the configured chat model.

    ``model_name`` lets a single agent override the default without changing
    how any other agent is constructed (spec section 3).
    """
    name = model_name or settings.default_model
    logger.debug("Building model %s via %s", name, settings.portkey_base_url)
    return OpenAIChatModel(name, provider=_provider())


def default_model_settings(
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> OpenAIChatModelSettings:
    """Per-agent generation settings, with the project timeout applied.

    ``openai_reasoning_effort`` is pinned because gpt-6-luna rejects function
    tools on /v1/chat/completions unless reasoning is off:

        "Function tools with reasoning_effort are not supported for
         gpt-6-luna-global in /v1/chat/completions."

    Structured output and every MCP tool in Phase 5 are function tools, so
    this is load-bearing rather than a tuning preference. It is configurable
    in case a future model does not need it.
    """
    return OpenAIChatModelSettings(
        temperature=0.3 if temperature is None else temperature,
        max_tokens=max_tokens or 2000,
        timeout=float(settings.model_timeout_seconds),
        openai_reasoning_effort=settings.openai_reasoning_effort,  # type: ignore[typeddict-item]
    )


def provider_is_configured() -> bool:
    """Cheap check for health reporting and for skipping live tests."""
    return bool(settings.portkey_api_key)
