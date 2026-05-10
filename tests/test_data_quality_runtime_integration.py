from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from broker.base import Broker
from config.settings import load_settings
from journal.models import Base
from runtime.trading_daemon import TestnetTradingDaemon as TradingDaemon
from strategies.base import StrategySignalPayload


class FakeBroker(Broker):
    async def get_account(self):
        return {}

    async def get_exchange_info(self):
        return {"symbols": []}

    async def get_klines(self, symbol, interval, limit):
        return []

    async def place_order(self, order_request):
        raise AssertionError("DataQualityGate must not call place_order")

    async def cancel_order(self, symbol, order_id):
        return {}

    async def get_order(self, symbol, order_id):
        return {}


def _factory():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, class_=Session, expire_on_commit=False, future=True)


def test_runtime_health_contains_data_quality_status() -> None:
    daemon = TradingDaemon(
        settings=load_settings(),
        session_factory=_factory(),
        broker=FakeBroker(),
        poll_interval_seconds=0.01,
    )
    health = daemon.health().model_dump(mode="json")
    assert "data_quality_status" in health
    assert health["data_quality_status"]["enabled"] is True


class ShouldNotCallPlanner:
    def plan(self, **kwargs):
        raise AssertionError("StrategyPlanner should be blocked by DataQualityGate")


class ShouldNotCallSignalReviewer:
    def review_with_schema(self, *args, **kwargs):
        raise AssertionError("SignalReviewer should be blocked by DataQualityGate")


class FakeStrategy:
    def generate_signal(self, **kwargs):
        return StrategySignalPayload(
            symbol="BTCUSDT",
            strategy_name="ema_trend",
            strategy_version="v1.0",
            timeframe="5m",
            side="BUY",
            signal_type="TEST",
            confidence=0.8,
            reason="test signal",
            raw_payload_json={},
        )


@pytest.mark.asyncio
async def test_critical_data_quality_blocks_strategy_planner() -> None:
    daemon = TradingDaemon(
        settings=load_settings(),
        session_factory=_factory(),
        broker=FakeBroker(),
        poll_interval_seconds=0.01,
    )
    daemon.strategy_planner = ShouldNotCallPlanner()
    task = asyncio.create_task(daemon._strategy_planner_worker())
    await asyncio.sleep(0.05)
    daemon.stop_event.set()
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    assert daemon.active_strategy_plan is not None
    assert daemon.active_strategy_plan["risk_mode"] == "no_trade"


@pytest.mark.asyncio
async def test_critical_data_quality_blocks_signal_reviewer_and_order_manager() -> None:
    daemon = TradingDaemon(
        settings=load_settings(),
        session_factory=_factory(),
        broker=FakeBroker(),
        signal_reviewer=ShouldNotCallSignalReviewer(),
        poll_interval_seconds=0.01,
    )
    daemon.strategy = FakeStrategy()
    frame = _market_frame(120)
    daemon.frames[("BTCUSDT", "5m")] = frame
    daemon.frames[("BTCUSDT", "1h")] = frame
    await daemon._process_symbol("BTCUSDT")
    assert daemon.last_ai_reviews[-1]["actual_model"] == "data_quality_gate"
    assert daemon.last_ai_reviews[-1]["review"]["decision"] == "HUMAN_REVIEW_REQUIRED"


def _market_frame(rows: int) -> pd.DataFrame:
    start = datetime.now(UTC) - timedelta(minutes=rows * 5)
    values = [100 + item for item in range(rows)]
    return pd.DataFrame(
        {
            "open_time": [start + timedelta(minutes=5 * item) for item in range(rows)],
            "close_time": [start + timedelta(minutes=5 * (item + 1)) for item in range(rows)],
            "open": values,
            "high": [value + 1 for value in values],
            "low": [value - 1 for value in values],
            "close": values,
            "volume": [1000 + item for item in range(rows)],
        }
    )
