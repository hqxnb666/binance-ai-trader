from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

import dashboard.api as api_module
from app.main import app


def test_runtime_diagnostics_latest_does_not_return_api_keys(monkeypatch) -> None:
    async def fake_run_diagnostics() -> dict[str, Any]:
        return {
            "environment": {
                "proxy_env": {"HTTP_PROXY": "present"},
                "required_env": {"OPENAI_API_KEY": "present"},
            },
            "connectivity": {
                "binance_testnet_rest": {"status": "OK"},
                "binance_testnet_ws": {"status": "OK"},
                "openai_api": {"status": "OK"},
            },
            "readiness": {},
            "recommended_next_action": [],
            "created_at": "now",
        }

    monkeypatch.setattr(api_module, "run_diagnostics", fake_run_diagnostics)
    with TestClient(app) as client:
        run = client.post("/runtime/diagnostics/run")
        assert run.status_code == 200
        latest = client.get("/runtime/diagnostics/latest").json()
        assert "sk-" not in str(latest)
        health = client.get("/runtime/health").json()
        assert health["network_readiness"]["binance_testnet_rest"] == "OK"

