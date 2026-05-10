from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from journal.models import MarketKline


def binance_klines_to_dataframe(klines: list[list[Any]]) -> pd.DataFrame:
    rows = []
    for item in klines:
        rows.append(
            {
                "open_time": datetime.fromtimestamp(int(item[0]) / 1000, tz=UTC),
                "open": float(item[1]),
                "high": float(item[2]),
                "low": float(item[3]),
                "close": float(item[4]),
                "volume": float(item[5]),
                "close_time": datetime.fromtimestamp(int(item[6]) / 1000, tz=UTC),
            }
        )
    return pd.DataFrame(rows)


def persist_kline_event(
    session: Session, symbol: str, timeframe: str, event: dict[str, Any]
) -> MarketKline:
    kline = event.get("k", event)
    record = MarketKline(
        symbol=symbol.upper(),
        timeframe=timeframe,
        open_time=datetime.fromtimestamp(int(kline["t"]) / 1000, tz=UTC),
        close_time=datetime.fromtimestamp(int(kline["T"]) / 1000, tz=UTC),
        open=Decimal(str(kline["o"])),
        high=Decimal(str(kline["h"])),
        low=Decimal(str(kline["l"])),
        close=Decimal(str(kline["c"])),
        volume=Decimal(str(kline["v"])),
        is_closed=bool(kline.get("x", False)),
    )
    session.add(record)
    session.flush()
    return record
