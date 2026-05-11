from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

import dashboard.api as dashboard_api
from app.main import app
from dashboard.web import dashboard_html


def test_dashboard_page_returns_local_operations_html() -> None:
    with TestClient(app) as client:
        response = client.get("/dashboard")

    assert response.status_code == 200
    html = response.text
    assert "Binance AI Trader Local Operations Dashboard" in html
    assert "Runtime" in html
    assert "DataQualityGate" in html
    assert "Shadow Mode" in html
    assert "RiskEngine" in html
    assert "Strategy Parameter Center" in html
    assert "Risk Config Viewer" in html
    assert "Testnet Readiness Check" in html
    assert "OpenAI Usage Report" in html
    assert "Review Workspace" in html


def test_dashboard_html_contains_safety_boundaries() -> None:
    html = dashboard_html()

    assert "No real order button" in html
    assert "No Live switch" in html
    assert "No disable-dry-run button" in html
    assert "No order execution enable button" in html
    assert "/runtime/testnet/start-dry-run" in html
    assert "/control/kill-switch/off" in html


def test_dashboard_route_does_not_break_health_or_status() -> None:
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/status").status_code == 200


def test_strategy_and_risk_config_dashboard_apis() -> None:
    with TestClient(app) as client:
        strategy = client.get("/config/strategy")
        assert strategy.status_code == 200
        payload = strategy.json()["config"]
        valid = client.post("/config/strategy/validate", json=payload)
        assert valid.status_code == 200
        assert valid.json()["valid"] is True
        invalid_payload = {
            **payload,
            "ema_trend": {
                **payload["ema_trend"],
                "ema_fast": 100,
                "ema_slow": 20,
            },
        }
        invalid = client.post("/config/strategy/validate", json=invalid_payload)
        assert invalid.status_code == 200
        assert invalid.json()["valid"] is False
        risk = client.get("/config/risk")
        assert risk.status_code == 200
        assert risk.json()["read_only"] is True


def test_readiness_and_openai_usage_dashboard_apis_are_safe(monkeypatch) -> None:
    async def fake_readiness_report(settings: Any = None) -> dict[str, Any]:
        return {
            "report_type": "testnet_order_readiness",
            "ready_for_dry_run": True,
            "ready_for_test_order_only": False,
            "ready_for_real_testnet_order": False,
            "ready_for_live": False,
            "blockers": ["mocked"],
            "warnings": [],
        }

    monkeypatch.setattr(dashboard_api, "build_readiness_report", fake_readiness_report)
    with TestClient(app) as client:
        readiness = client.post("/runtime/readiness/check")
        assert readiness.status_code == 200
        assert readiness.json()["ready_for_dry_run"] is True
        latest = client.get("/runtime/readiness/latest")
        assert latest.status_code == 200
        assert latest.json()["ready_for_live"] is False
        usage = client.get("/runtime/openai-usage?days=1")
        assert usage.status_code == 200
        assert "summary" in usage.json()
        assert "API_KEY" not in str(usage.json())
        assert "sk-" not in str(usage.json())


def test_dashboard_does_not_add_real_order_routes() -> None:
    route_paths = {getattr(route, "path", "") for route in app.routes}

    forbidden = {
        "/runtime/testnet/order",
        "/runtime/testnet/new-order",
        "/runtime/testnet/order-lifecycle",
        "/runtime/live/start",
        "/control/order-execution/on",
    }
    assert route_paths.isdisjoint(forbidden)
