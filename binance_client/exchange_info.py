from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class SymbolFilters:
    symbol: str
    tick_size: Decimal
    step_size: Decimal
    min_qty: Decimal
    min_notional: Decimal
    max_qty: Decimal | None = None


def _decimal_filter(
    filters: list[dict[str, Any]], filter_type: str, key: str, default: str
) -> Decimal:
    for item in filters:
        if item.get("filterType") == filter_type:
            return Decimal(str(item.get(key, default)))
    return Decimal(default)


def _decimal_filter_any(
    filters: list[dict[str, Any]],
    candidates: list[tuple[str, str]],
    default: str,
) -> Decimal:
    for filter_type, key in candidates:
        for item in filters:
            if item.get("filterType") == filter_type and item.get(key) is not None:
                return Decimal(str(item[key]))
    return Decimal(default)


def parse_symbol_filters(exchange_info: dict[str, Any], symbol: str) -> SymbolFilters:
    symbol = symbol.upper()
    for item in exchange_info.get("symbols", []):
        if item.get("symbol") != symbol:
            continue
        filters = list(item.get("filters", []))
        max_qty = _decimal_filter(filters, "LOT_SIZE", "maxQty", "0")
        return SymbolFilters(
            symbol=symbol,
            tick_size=_decimal_filter(filters, "PRICE_FILTER", "tickSize", "0.00000001"),
            step_size=_decimal_filter(filters, "LOT_SIZE", "stepSize", "0.00000001"),
            min_qty=_decimal_filter(filters, "LOT_SIZE", "minQty", "0"),
            min_notional=_decimal_filter_any(
                filters,
                [("MIN_NOTIONAL", "minNotional"), ("NOTIONAL", "minNotional")],
                "0",
            ),
            max_qty=max_qty if max_qty > 0 else None,
        )
    msg = f"Symbol filters not found for {symbol}"
    raise KeyError(msg)


def parse_all_symbol_filters(exchange_info: dict[str, Any]) -> dict[str, SymbolFilters]:
    result: dict[str, SymbolFilters] = {}
    for item in exchange_info.get("symbols", []):
        symbol = str(item.get("symbol", "")).upper()
        if symbol:
            result[symbol] = parse_symbol_filters(exchange_info, symbol)
    return result
