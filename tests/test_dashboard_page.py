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
    assert "Binance AI Trader 本地运维控制台" in html
    assert "运行时 Runtime" in html
    assert "DataQualityGate" in html
    assert "影子模式 Shadow Mode" in html
    assert "RiskEngine" in html
    assert "策略参数设置中心" in html
    assert "风控配置只读查看器" in html
    assert "Testnet Readiness 检查" in html
    assert "OpenAI 用量报告" in html
    assert "复盘工作台" in html


def test_dashboard_html_contains_safety_boundaries() -> None:
    html = dashboard_html()

    assert "没有真实下单按钮" in html
    assert "没有 Live 开关" in html
    assert "没有关闭 dry-run 按钮" in html
    assert "没有开启 order execution 按钮" in html
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
