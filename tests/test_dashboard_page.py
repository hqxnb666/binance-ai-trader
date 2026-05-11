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
    assert "完整诊断包 / Diagnostic Snapshot" in html
    assert "复盘工作台" in html
    assert "加载完整诊断包" in html
    assert "复制完整诊断包 JSON" in html
    assert "复制 GPT 完整诊断复盘包" in html
    assert "blocking_attribution" in html


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


def test_strategy_plan_and_diagnostic_snapshot_apis_are_read_only() -> None:
    with TestClient(app) as client:
        latest = client.get("/runtime/strategy-plan/latest")
        assert latest.status_code == 200
        assert latest.json()["status"] in {"OK", "NO_ACTIVE_STRATEGY_PLAN"}

        recent = client.get("/runtime/strategy-plan/recent?limit=10")
        assert recent.status_code == 200
        assert recent.json()["status"] == "OK"
        assert "items" in recent.json()

        snapshot = client.get("/runtime/diagnostic-snapshot")
        assert snapshot.status_code == 200
        payload = snapshot.json()
        assert payload["schema_version"] == "diagnostic_snapshot_v1"
        for key in [
            "runtime_health",
            "strategy_config",
            "risk_config",
            "active_strategy_plan",
            "recent_strategy_plans",
            "last_snapshots",
            "recent_signals",
            "shadow_report",
            "shadow_recent",
            "blocking_attribution",
            "audit_latest",
        ]:
            assert key in payload
        assert "API_KEY" not in str(payload)
        assert "sk-" not in str(payload)


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
