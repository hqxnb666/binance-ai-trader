from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from binance_client.errors import OrderValidationError
from binance_client.exchange_info import SymbolFilters
from risk.order_filter_validator import OrderFilterValidator, floor_to_step


@dataclass(frozen=True)
class PositionSizeResult:
    quantity: Decimal
    notional: Decimal
    risk_amount: Decimal
    adjusted_quantity: Decimal
    adjusted_entry_price: Decimal


class PositionSizer:
    def size_position(
        self,
        *,
        account_equity_usdt: Decimal,
        max_single_trade_risk_pct: Decimal,
        entry_price: Decimal,
        stop_loss_price: Decimal,
        max_position_pct_per_symbol: Decimal,
        filters: SymbolFilters,
    ) -> PositionSizeResult:
        if account_equity_usdt <= 0:
            raise OrderValidationError("account equity must be positive")
        stop_distance = abs(entry_price - stop_loss_price)
        if stop_distance <= 0:
            raise OrderValidationError("stop loss distance must be positive")
        adjusted_price = floor_to_step(entry_price, filters.tick_size)
        risk_amount = account_equity_usdt * (max_single_trade_risk_pct / Decimal("100"))
        risk_quantity = risk_amount / stop_distance
        max_notional = account_equity_usdt * (max_position_pct_per_symbol / Decimal("100"))
        max_quantity_by_position = max_notional / adjusted_price
        raw_quantity = min(risk_quantity, max_quantity_by_position)
        adjusted_quantity = floor_to_step(raw_quantity, filters.step_size)
        notional = adjusted_price * adjusted_quantity
        validator = OrderFilterValidator(filters)
        result = validator.validate_order(price=adjusted_price, quantity=adjusted_quantity)
        if not result.valid:
            raise OrderValidationError(result.reason)
        return PositionSizeResult(
            quantity=raw_quantity,
            notional=notional,
            risk_amount=risk_amount,
            adjusted_quantity=adjusted_quantity,
            adjusted_entry_price=adjusted_price,
        )

