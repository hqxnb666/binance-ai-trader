from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from binance_client.rest_client import BinanceRestClient
from features.kline_store import binance_klines_to_dataframe
from journal.models import MarketKline

INTERVAL_MS = {
    "5m": 5 * 60 * 1000,
    "1h": 60 * 60 * 1000,
}


async def load_klines_from_binance(
    *,
    rest_base: str,
    symbol: str,
    interval: str,
    start: datetime,
    end: datetime,
) -> pd.DataFrame:
    client = BinanceRestClient(base_url=rest_base)
    try:
        all_rows: list[list[Any]] = []
        cursor = int(start.timestamp() * 1000)
        end_ms = int(end.timestamp() * 1000)
        while cursor < end_ms:
            batch = await client.get_klines(
                symbol,
                interval,
                1000,
                start_time_ms=cursor,
                end_time_ms=end_ms,
            )
            if not batch:
                break
            all_rows.extend(batch)
            next_cursor = int(batch[-1][0]) + INTERVAL_MS[interval]
            if next_cursor <= cursor:
                break
            cursor = next_cursor
            await asyncio.sleep(0.05)
        frame = binance_klines_to_dataframe(all_rows)
        return _dedupe_sort(frame)
    finally:
        await client.aclose()


def load_klines_from_database(
    *,
    session: Session,
    symbol: str,
    timeframe: str,
    start: datetime,
    end: datetime,
) -> pd.DataFrame:
    rows = session.scalars(
        select(MarketKline)
        .where(MarketKline.symbol == symbol.upper())
        .where(MarketKline.timeframe == timeframe)
        .where(MarketKline.open_time >= start)
        .where(MarketKline.open_time <= end)
        .order_by(MarketKline.open_time)
    ).all()
    data = [
        {
            "open_time": row.open_time,
            "open": float(row.open),
            "high": float(row.high),
            "low": float(row.low),
            "close": float(row.close),
            "volume": float(row.volume),
            "close_time": row.close_time,
        }
        for row in rows
    ]
    return pd.DataFrame(data)


def parse_backtest_window(
    *, start: str | None, end: str | None, days: int | None
) -> tuple[datetime, datetime]:
    if days is not None:
        end_dt = datetime.now(UTC)
        return end_dt - timedelta(days=days), end_dt
    if not start or not end:
        msg = "Provide either --days or both --start and --end"
        raise ValueError(msg)
    return _parse_date(start), _parse_date(end)


def _parse_date(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _dedupe_sort(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    return (
        frame.drop_duplicates(subset=["open_time"])
        .sort_values("open_time")
        .reset_index(drop=True)
    )

