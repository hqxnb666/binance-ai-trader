from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from config.settings import load_settings
from journal.models import Base
from runtime.daemon_state import DaemonState
from runtime.task_manager import RuntimeTaskManager


class FakeDaemon:
    instances = 0

    def __init__(self, **kwargs: Any):
        FakeDaemon.instances += 1
        self.state = DaemonState.STOPPED
        self.dry_run = kwargs["dry_run"]
        self.order_execution_enabled = kwargs["order_execution_enabled"]
        self.logs = type("Logs", (), {"recent": lambda _self, limit=100: []})()
        self.last_snapshots = {}
        self.last_ai_reviews = []
        self.last_risk_decisions = []

    async def start(self) -> dict[str, Any]:
        self.state = DaemonState.RUNNING
        return {"started": True, "state": self.state.value}

    async def stop(self) -> dict[str, Any]:
        self.state = DaemonState.STOPPED
        return {"stopped": True, "state": self.state.value}

    def health(self):
        return type(
            "Health",
            (),
            {"model_dump": lambda _self, mode="json": {"state": self.state.value}},
        )()


def _session_factory():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, class_=Session, expire_on_commit=False, future=True)


@pytest.mark.asyncio
async def test_daemon_state_start_stop_and_idempotent_start() -> None:
    FakeDaemon.instances = 0
    manager = RuntimeTaskManager(
        settings=load_settings(),
        session_factory=_session_factory(),
        daemon_factory=FakeDaemon,
    )
    first = await manager.start_testnet(dry_run=True, order_execution_enabled=False)
    second = await manager.start_testnet(dry_run=True, order_execution_enabled=False)
    assert first["started"] is True
    assert second["started"] is False
    assert FakeDaemon.instances == 1
    assert manager.state()["state"] == "RUNNING"
    stopped = await manager.stop_testnet()
    assert stopped["stopped"] is True
    assert manager.state()["state"] == "STOPPED"

