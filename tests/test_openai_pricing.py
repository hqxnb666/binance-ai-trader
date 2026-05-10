from __future__ import annotations

from decimal import Decimal

from ai.pricing import estimate_openai_cost_usd


def test_gpt_55_cost_estimate() -> None:
    assert estimate_openai_cost_usd(
        model="gpt-5.5", input_tokens=1_000_000, output_tokens=1_000_000
    ) == Decimal("35.00000000")


def test_gpt_54_mini_cost_estimate() -> None:
    assert estimate_openai_cost_usd(
        model="gpt-5.4-mini", input_tokens=1_000_000, output_tokens=1_000_000
    ) == Decimal("5.25000000")


def test_gpt_54_nano_cost_estimate() -> None:
    assert estimate_openai_cost_usd(
        model="gpt-5.4-nano", input_tokens=1_000_000, output_tokens=1_000_000
    ) == Decimal("1.45000000")


def test_unknown_model_does_not_crash() -> None:
    assert estimate_openai_cost_usd(
        model="unknown", input_tokens=100, output_tokens=100
    ) is None
