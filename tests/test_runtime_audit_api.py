from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.main import app


class FakeManager:
    latest_diagnostics = None

    async def start_testnet(self, **kwargs: Any) -> dict[str, Any]:
        return {"started": True, "state": "RUNNING", **kwargs}

    async def stop_testnet(self) -> dict[str, Any]:
        return {"stopped": True}

    async def run_system_audit(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "overall_status": "WATCH",
            "highest_severity": "LOW",
            "issue_count": 1,
            "summary": "fake audit",
            "report": {"summary": "fake audit", "do_not_auto_modify": True},
        }

    def state(self) -> dict[str, Any]:
        return {"state": "RUNNING"}

    def health(self) -> dict[str, Any]:
        return {
            "state": "RUNNING",
            "trading_mode": "testnet",
            "symbols": ["BTCUSDT"],
            "market_stream_connected": True,
            "user_stream_connected": True,
            "last_kline_time": None,
            "last_user_event_time": None,
            "last_error": None,
            "dry_run": True,
            "ai_enabled": True,
            "order_execution_enabled": False,
            "audit_status": {
                "enabled": True,
                "latest_overall_status": "WATCH",
                "latest_highest_severity": "LOW",
                "latest_issue_count": 1,
                "latest_report_created_at": None,
                "latest_summary": "fake audit",
                "health_warning": False,
            },
        }

    def logs(self, limit: int = 100) -> list[dict[str, Any]]:
        return []

    def last_snapshots(self) -> dict[str, Any]:
        return {}

    def last_ai_reviews(self) -> list[dict[str, Any]]:
        return []

    def last_risk_decisions(self) -> list[dict[str, Any]]:
        return []


def test_runtime_audit_api_and_health_do_not_expose_keys() -> None:
    with TestClient(app) as client:
        client.app.state.runtime_manager = FakeManager()
        latest = client.get("/runtime/audits/latest")
        assert latest.status_code == 200
        assert latest.json()["status"] == "NO_AUDIT_REPORT"
        run = client.post("/runtime/audits/run")
        assert run.status_code == 200
        assert run.json()["report"]["do_not_auto_modify"] is True
        health = client.get("/runtime/health").json()
        assert "audit_status" in health
        assert "API_KEY" not in str(run.json())
