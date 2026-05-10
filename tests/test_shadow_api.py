from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.main import app


class FakeManager:
    latest_diagnostics = None

    def shadow_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        return [{"shadow_id": "shadow-1", "limit": limit}]

    def shadow_open(self, limit: int = 50) -> list[dict[str, Any]]:
        return []

    def shadow_report(self, hours: int = 24) -> dict[str, Any]:
        return {"schema_version": "shadow_report_v1", "hours": hours}

    async def run_shadow_evaluation(self) -> dict[str, Any]:
        return {"evaluated": 0, "evaluations": []}

    async def stop_testnet(self) -> dict[str, Any]:
        return {"stopped": True}


def test_shadow_api_endpoints_do_not_order_or_expose_keys() -> None:
    with TestClient(app) as client:
        client.app.state.runtime_manager = FakeManager()
        assert client.get("/runtime/shadow/recent").status_code == 200
        assert client.get("/runtime/shadow/open").json() == []
        assert client.get("/runtime/shadow/report").json()["schema_version"] == "shadow_report_v1"
        payload = client.post("/runtime/shadow/evaluate").json()
        assert payload["evaluated"] == 0
        assert "API_KEY" not in str(payload)
