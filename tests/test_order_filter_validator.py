from __future__ import annotations

from decimal import Decimal

from binance_client.exchange_info import SymbolFilters, parse_symbol_filters
from risk.order_filter_validator import OrderFilterValidator


def _validator() -> OrderFilterValidator:
    return OrderFilterValidator(
        SymbolFilters(
            symbol="BTCUSDT",
            tick_size=Decimal("0.10"),
            step_size=Decimal("0.001"),
            min_qty=Decimal("0.001"),
            min_notional=Decimal("10"),
        )
    )


def test_price_tick_size_validation() -> None:
    validator = _validator()
    assert validator.validate_price(Decimal("100.00")).valid is True
    assert validator.validate_price(Decimal("100.05")).valid is False


def test_quantity_step_size_validation() -> None:
    validator = _validator()
    assert validator.validate_quantity(Decimal("0.002")).valid is True
    assert validator.validate_quantity(Decimal("0.0025")).valid is False


def test_min_notional_validation() -> None:
    validator = _validator()
    assert validator.validate_min_notional(Decimal("100"), Decimal("0.2")).valid is True
    assert validator.validate_min_notional(Decimal("100"), Decimal("0.01")).valid is False


def test_parse_symbol_filters_supports_notional_filter() -> None:
    filters = parse_symbol_filters(
        {
            "symbols": [
                {
                    "symbol": "BTCUSDT",
                    "filters": [
                        {"filterType": "PRICE_FILTER", "tickSize": "0.10"},
                        {"filterType": "LOT_SIZE", "stepSize": "0.001", "minQty": "0.001"},
                        {"filterType": "NOTIONAL", "minNotional": "100.00"},
                    ],
                }
            ]
        },
        "BTCUSDT",
    )
    assert filters.min_notional == Decimal("100.00")
