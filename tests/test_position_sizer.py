from __future__ import annotations

from decimal import Decimal

import pytest

from binance_client.errors import OrderValidationError
from binance_client.exchange_info import SymbolFilters
from risk.position_sizer import PositionSizer


def _filters(min_notional: Decimal = Decimal("10")) -> SymbolFilters:
    return SymbolFilters(
        symbol="BTCUSDT",
        tick_size=Decimal("0.10"),
        step_size=Decimal("0.001"),
        min_qty=Decimal("0.001"),
        min_notional=min_notional,
    )


def test_position_sizer_calculates_and_adjusts_step() -> None:
    result = PositionSizer().size_position(
        account_equity_usdt=Decimal("1000"),
        max_single_trade_risk_pct=Decimal("0.5"),
        entry_price=Decimal("100.05"),
        stop_loss_price=Decimal("95"),
        max_position_pct_per_symbol=Decimal("10"),
        filters=_filters(),
    )
    assert result.risk_amount == Decimal("5.0")
    assert result.adjusted_entry_price == Decimal("100.00")
    assert result.adjusted_quantity % Decimal("0.001") == 0


def test_position_sizer_rejects_min_notional() -> None:
    with pytest.raises(OrderValidationError):
        PositionSizer().size_position(
            account_equity_usdt=Decimal("100"),
            max_single_trade_risk_pct=Decimal("0.5"),
            entry_price=Decimal("100"),
            stop_loss_price=Decimal("90"),
            max_position_pct_per_symbol=Decimal("1"),
            filters=_filters(min_notional=Decimal("50")),
        )

