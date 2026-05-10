from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal

from binance_client.errors import OrderValidationError
from binance_client.exchange_info import SymbolFilters


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    reason: str


def floor_to_step(value: Decimal, step: Decimal) -> Decimal:
    if step <= 0:
        return value
    return (value / step).to_integral_value(rounding=ROUND_DOWN) * step


def is_multiple(value: Decimal, step: Decimal) -> bool:
    if step <= 0:
        return True
    return floor_to_step(value, step) == value


class OrderFilterValidator:
    def __init__(self, filters: SymbolFilters):
        self.filters = filters

    def validate_price(self, price: Decimal) -> ValidationResult:
        if price <= 0:
            return ValidationResult(False, "price must be positive")
        if not is_multiple(price, self.filters.tick_size):
            return ValidationResult(False, "price does not match tickSize")
        return ValidationResult(True, "ok")

    def validate_quantity(self, quantity: Decimal) -> ValidationResult:
        if quantity <= 0:
            return ValidationResult(False, "quantity must be positive")
        if quantity < self.filters.min_qty:
            return ValidationResult(False, "quantity below minQty")
        if self.filters.max_qty is not None and quantity > self.filters.max_qty:
            return ValidationResult(False, "quantity above maxQty")
        if not is_multiple(quantity, self.filters.step_size):
            return ValidationResult(False, "quantity does not match stepSize")
        return ValidationResult(True, "ok")

    def validate_min_notional(self, price: Decimal, quantity: Decimal) -> ValidationResult:
        notional = price * quantity
        if notional < self.filters.min_notional:
            return ValidationResult(False, "notional below minNotional")
        return ValidationResult(True, "ok")

    def validate_order(self, *, price: Decimal, quantity: Decimal) -> ValidationResult:
        for result in (
            self.validate_price(price),
            self.validate_quantity(quantity),
            self.validate_min_notional(price, quantity),
        ):
            if not result.valid:
                return result
        return ValidationResult(True, "ok")

    def assert_order(self, *, price: Decimal, quantity: Decimal) -> None:
        result = self.validate_order(price=price, quantity=quantity)
        if not result.valid:
            raise OrderValidationError(result.reason)
