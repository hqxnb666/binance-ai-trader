from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.main import app


class FakeManager:
    async def start_testnet(self, **kwargs: Any) -> dict[str, Any]:
        return {"started": True, "state": "RUNNING", **kwargs}

    async def stop_testnet(self) -> dict[str, Any]:
        return {"stopped": True, "state": "STOPPED"}

    def state(self) -> dict[str, Any]:
        return {"state": "RUNNING", "dry_run": True}

    def health(self) -> dict[str, Any]:
        return {
            "state": "RUNNING",
            "trading_mode": "testnet",
            "symbols": ["BTCUSDT", "ETHUSDT"],
            "market_stream_connected": True,
            "user_stream_connected": False,
            "last_kline_time": None,
            "last_user_event_time": None,
            "last_error": None,
            "dry_run": True,
            "ai_enabled": True,
            "order_execution_enabled": False,
        }

    def logs(self, limit: int = 100) -> list[dict[str, Any]]:
        return [{"event": "daemon_running"}]

    def last_snapshots(self) -> dict[str, Any]:
        return {"BTCUSDT": {"symbol": "BTCUSDT"}}

    def last_ai_reviews(self) -> list[dict[str, Any]]:
        return []

    def last_risk_decisions(self) -> list[dict[str, Any]]:
        return []


def test_runtime_api_does_not_expose_keys_and_can_start_dry_run() -> None:
    with TestClient(app) as client:
        client.app.state.runtime_manager = FakeManager()
        config = client.get("/config/safe").json()
        assert "API_KEY" not in str(config)
        health = client.get("/runtime/health")
        assert health.status_code == 200
        assert health.json()["trading_mode"] == "testnet"
        started = client.post("/runtime/testnet/start-dry-run")
        assert started.status_code == 200
        assert started.json()["dry_run"] is True
        stopped = client.post("/runtime/testnet/stop-dry-run")
        assert stopped.status_code == 200
        assert stopped.json()["stopped"] is True

