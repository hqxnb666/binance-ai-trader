from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from ai.audit_schemas import AuditReportType
from config.settings import Settings
from runtime.daemon_state import DaemonState
from runtime.trading_daemon import TestnetTradingDaemon

DaemonFactory = Callable[..., TestnetTradingDaemon]


class RuntimeTaskManager:
    def __init__(
        self,
        *,
        settings: Settings,
        session_factory: sessionmaker[Session],
        daemon_factory: DaemonFactory = TestnetTradingDaemon,
    ):
        self.settings = settings
        self.session_factory = session_factory
        self.daemon_factory = daemon_factory
        self.daemon: TestnetTradingDaemon | None = None
        self.latest_diagnostics: dict[str, Any] | None = None
        self._lock = asyncio.Lock()

    async def start_testnet(
        self, *, dry_run: bool | None = None, order_execution_enabled: bool | None = None
    ) -> dict[str, Any]:
        async with self._lock:
            if self.daemon and self.daemon.state in {DaemonState.STARTING, DaemonState.RUNNING}:
                return {
                    "started": False,
                    "state": self.daemon.state.value,
                    "reason": "already running",
                }
            self.daemon = self.daemon_factory(
                settings=self.settings,
                session_factory=self.session_factory,
                dry_run=self.settings.trading_dry_run if dry_run is None else dry_run,
                order_execution_enabled=self.settings.order_execution_enabled
                if order_execution_enabled is None
                else order_execution_enabled,
            )
            return await self.daemon.start()

    async def stop_testnet(self) -> dict[str, Any]:
        async with self._lock:
            if self.daemon is None:
                return {
                    "stopped": False,
                    "state": DaemonState.STOPPED.value,
                    "reason": "not started",
                }
            return await self.daemon.stop()

    def state(self) -> dict[str, Any]:
        if self.daemon is None:
            return {"state": DaemonState.STOPPED.value}
        return {
            "state": self.daemon.state.value,
            "dry_run": self.daemon.dry_run,
            "order_execution_enabled": self.daemon.order_execution_enabled,
        }

    def health(self) -> dict[str, Any]:
        if self.daemon is None:
            return {
                "state": DaemonState.STOPPED.value,
                "trading_mode": "testnet",
                "symbols": self.settings.symbols.enabled_symbols,
                "market_stream_connected": False,
                "user_stream_connected": False,
                "last_kline_time": None,
                "last_user_event_time": None,
                "last_error": None,
                "dry_run": self.settings.trading_dry_run,
                "ai_enabled": self.settings.ai_analysis_enabled,
                "order_execution_enabled": self.settings.order_execution_enabled,
                "audit_status": {
                    "enabled": self.settings.enable_system_auditor,
                    "latest_overall_status": "UNKNOWN",
                    "latest_highest_severity": "UNKNOWN",
                    "latest_issue_count": 0,
                    "latest_report_created_at": None,
                    "latest_summary": None,
                    "health_warning": False,
                },
            }
        return self.daemon.health().model_dump(mode="json")

    def logs(self, limit: int = 100) -> list[dict[str, Any]]:
        return [] if self.daemon is None else self.daemon.logs.recent(limit)

    def last_snapshots(self) -> dict[str, Any]:
        return {} if self.daemon is None else self.daemon.last_snapshots

    def last_ai_reviews(self) -> list[dict[str, Any]]:
        return [] if self.daemon is None else self.daemon.last_ai_reviews

    def last_risk_decisions(self) -> list[dict[str, Any]]:
        return [] if self.daemon is None else self.daemon.last_risk_decisions

    async def run_system_audit(
        self,
        *,
        report_type: AuditReportType = AuditReportType.INCIDENT_AUDIT,
        lookback_hours: int | None = None,
        deep: bool = False,
    ) -> dict[str, Any]:
        temporary = self.daemon is None
        daemon = self.daemon or self.daemon_factory(
            settings=self.settings,
            session_factory=self.session_factory,
            dry_run=True,
            order_execution_enabled=False,
        )
        try:
            return await daemon.run_system_audit_once(
                report_type=report_type,
                lookback_hours=lookback_hours,
                deep=deep,
            )
        finally:
            if temporary:
                await daemon._close_broker()
