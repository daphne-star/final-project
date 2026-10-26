"""Model pricing, and what to do without it.

Pydantic AI has no price table for `gpt-6-luna`, so until this session every
usage row recorded `estimated_cost_usd = 0.0` and the configured cost ceiling
silently enforced nothing. Two things fix that honestly:

* **Prices are configuration, not a guess.** Rates come from `MODEL_PRICES`
  in the environment. Inventing a plausible-looking number would be exactly
  the fabrication the rest of the system refuses to do.
* **A token ceiling backs it up.** Token counts are always known, so
  `max_total_tokens_per_meeting` is enforceable whether or not anyone has
  configured a price. Cost enforcement is a bonus on top; token enforcement
  is the guarantee.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from functools import lru_cache

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ModelPrice:
    """USD per million tokens."""

    input_per_million: float
    output_per_million: float

    def cost_for(self, input_tokens: int, output_tokens: int) -> float:
        return (
            input_tokens * self.input_per_million
            + output_tokens * self.output_per_million
        ) / 1_000_000


@lru_cache
def price_table() -> dict[str, ModelPrice]:
    """Parse MODEL_PRICES. Malformed config is ignored, loudly.

    Format: {"model-name": {"input_per_million": 2.5, "output_per_million": 10}}
    """
    raw = (settings.model_prices or "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("MODEL_PRICES is not valid JSON; cost estimation stays disabled")
        return {}

    table: dict[str, ModelPrice] = {}
    for name, entry in parsed.items():
        try:
            table[name] = ModelPrice(
                input_per_million=float(entry["input_per_million"]),
                output_per_million=float(entry["output_per_million"]),
            )
        except (TypeError, KeyError, ValueError):
            logger.error("MODEL_PRICES entry for %r is malformed; skipping", name)
    return table


def estimate_cost(model_name: str, input_tokens: int, output_tokens: int) -> float | None:
    """Cost in USD, or None when no price is configured for this model.

    None is the point: a caller can tell "we do not know" apart from "it was
    free", which a 0.0 cannot express.
    """
    price = price_table().get(model_name)
    if price is None:
        return None
    return round(price.cost_for(input_tokens, output_tokens), 6)


def pricing_is_configured(model_name: str | None = None) -> bool:
    table = price_table()
    if not table:
        return False
    return model_name is None or model_name in table


def reset_price_cache() -> None:
    """Used by tests that change the configured prices."""
    price_table.cache_clear()
