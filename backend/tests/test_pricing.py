"""Cost estimation: configured prices, and honest silence without them."""

from __future__ import annotations

import pytest

from app.agents import pricing


@pytest.fixture(autouse=True)
def _clear_price_cache():
    pricing.reset_price_cache()
    yield
    pricing.reset_price_cache()


def _configure(monkeypatch, value):
    monkeypatch.setattr(pricing.settings, "model_prices", value)
    pricing.reset_price_cache()


def test_no_configured_price_returns_unknown_not_zero(monkeypatch):
    """A 0.0 would be indistinguishable from a free call."""
    _configure(monkeypatch, None)
    assert pricing.estimate_cost("gpt-6-luna", 1000, 500) is None
    assert pricing.pricing_is_configured() is False


def test_a_configured_price_produces_a_real_cost(monkeypatch):
    _configure(
        monkeypatch,
        '{"gpt-6-luna": {"input_per_million": 2.5, "output_per_million": 10.0}}',
    )
    # 1M input at 2.50 + 0.5M output at 10.00 = 2.50 + 5.00
    assert pricing.estimate_cost("gpt-6-luna", 1_000_000, 500_000) == 7.5
    assert pricing.pricing_is_configured("gpt-6-luna") is True


def test_an_unpriced_model_is_unknown_even_when_others_are_priced(monkeypatch):
    _configure(
        monkeypatch,
        '{"gpt-6-luna": {"input_per_million": 1, "output_per_million": 2}}',
    )
    assert pricing.estimate_cost("some-other-model", 1000, 1000) is None
    assert pricing.pricing_is_configured("some-other-model") is False


def test_small_token_counts_do_not_round_to_zero(monkeypatch):
    _configure(
        monkeypatch,
        '{"m": {"input_per_million": 3.0, "output_per_million": 15.0}}',
    )
    cost = pricing.estimate_cost("m", 1500, 430)
    assert cost is not None
    assert cost > 0
    assert cost == pytest.approx((1500 * 3 + 430 * 15) / 1_000_000, abs=1e-9)


def test_malformed_json_disables_pricing_rather_than_crashing(monkeypatch, caplog):
    _configure(monkeypatch, "{not json")
    assert pricing.price_table() == {}
    assert pricing.estimate_cost("gpt-6-luna", 10, 10) is None


def test_a_malformed_entry_is_skipped_but_others_survive(monkeypatch):
    _configure(
        monkeypatch,
        '{"good": {"input_per_million": 1, "output_per_million": 2}, '
        '"bad": {"input_per_million": "free"}}',
    )
    table = pricing.price_table()
    assert set(table) == {"good"}
    assert pricing.estimate_cost("bad", 100, 100) is None


def test_price_table_is_cached_until_reset(monkeypatch):
    _configure(monkeypatch, '{"m": {"input_per_million": 1, "output_per_million": 1}}')
    assert pricing.estimate_cost("m", 1_000_000, 0) == 1.0

    # Changing the setting without clearing the cache keeps the old table;
    # reset_price_cache is the documented way to pick up a change.
    monkeypatch.setattr(pricing.settings, "model_prices", None)
    assert pricing.estimate_cost("m", 1_000_000, 0) == 1.0
    pricing.reset_price_cache()
    assert pricing.estimate_cost("m", 1_000_000, 0) is None
