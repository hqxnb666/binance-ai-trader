from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class ModelPrice:
    input_per_1m: Decimal
    output_per_1m: Decimal


MODEL_PRICES: dict[str, ModelPrice] = {
    "gpt-5.5": ModelPrice(Decimal("5.00"), Decimal("30.00")),
    "gpt-5.4": ModelPrice(Decimal("2.50"), Decimal("15.00")),
    "gpt-5.4-mini": ModelPrice(Decimal("0.75"), Decimal("4.50")),
    "gpt-5.4-nano": ModelPrice(Decimal("0.20"), Decimal("1.25")),
}


def estimate_openai_cost_usd(
    *,
    model: str,
    input_tokens: int | None,
    output_tokens: int | None,
    cached_tokens: int | None = None,
) -> Decimal | None:
    price = price_for_model(model)
    if price is None:
        return None
    input_count = max(int(input_tokens or 0), 0)
    output_count = max(int(output_tokens or 0), 0)
    cached_count = max(int(cached_tokens or 0), 0)
    billable_input = max(input_count - cached_count, 0) + cached_count
    cost = (
        Decimal(billable_input) * price.input_per_1m
        + Decimal(output_count) * price.output_per_1m
    ) / Decimal(1_000_000)
    return cost.quantize(Decimal("0.00000001"))


def price_for_model(model: str) -> ModelPrice | None:
    normalized = model.strip()
    if normalized in MODEL_PRICES:
        return MODEL_PRICES[normalized]
    for prefix in ("gpt-5.5", "gpt-5.4-mini", "gpt-5.4-nano", "gpt-5.4"):
        if normalized.startswith(prefix):
            return MODEL_PRICES[prefix]
    return None
