from __future__ import annotations

import re
from typing import Any

from fastapi.testclient import TestClient

import dashboard.api as dashboard_api
from app.main import app
from config.settings import load_settings
from dashboard.api import _account_profile_payload, _diagnostic_summary
from dashboard.web import dashboard_html


def test_dashboard_page_returns_simplified_console_html() -> None:
    with TestClient(app) as client:
        response = client.get("/dashboard")

    assert response.status_code == 200
    html = response.text
    assert "Binance AI Trader 控制台" in html
    assert "一键诊断中心" in html
    assert "一键刷新状态" in html
    assert "一键运行检查" in html
    assert "加载完整诊断包" in html
    assert "复制 GPT 完整复盘包" in html
    assert "运行控制" in html
    assert "启动 Dry Run" in html
    assert "停止 Dry Run" in html
    assert "安全总览" in html
    assert "当前结论" in html
    assert "Shadow Mode" in html
    assert "运行状态 Runtime" in html
    assert "行情与网络 Streams" in html
    assert "数据质量闸门 DataQualityGate" in html
    assert "策略快照 Strategy Snapshot" in html
    assert "AI 信号审查 SignalReview" in html
    assert "风控引擎 RiskEngine" in html
    assert "订单管理 OrderManager" in html
    assert "账户与仓位" in html
    assert "OpenAI 成本预算" in html
    assert "系统审计 SystemAuditor" in html
    assert "日志与链路" in html
    assert "高级操作与配置" in html
    assert "复盘工作台" in html


def test_dashboard_html_keeps_main_actions_small_and_summary_first() -> None:
    html = dashboard_html()

    assert len(re.findall(r'class="[^"]*\bprimary-action\b', html)) <= 5
    assert "raw_output_json" not in html
    assert "last_ai_reviews" not in html
    assert "last_risk_decisions" not in html
    assert "shadow_recent" not in html
    assert "没有真实下单按钮" in html
    assert "没有 Live 开关" in html
    assert "没有关闭 dry-run 按钮" in html
    assert "没有开启 order execution 按钮" in html
    assert "/runtime/testnet/start-dry-run" in html
    assert "/runtime/testnet/stop-dry-run" in html
    assert "/control/kill-switch/off" in html


def test_dashboard_route_does_not_break_health_or_status() -> None:
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/status").status_code == 200


def test_dashboard_summary_api_is_read_only_and_compact() -> None:
    with TestClient(app) as client:
        response = client.get("/runtime/dashboard-summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "dashboard_summary_v1"
    for key in [
        "safety",
        "diagnosis",
        "shadow",
        "strategy_plan",
        "signals",
        "ai_reviews",
        "risk",
        "audit",
    ]:
        assert key in payload
    assert "API_KEY" not in str(payload)
    assert "sk-" not in str(payload)


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
            "account_profile",
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
        assert "profile" in payload["account_profile"]
        assert "API_KEY" not in str(payload)
        assert "sk-" not in str(payload)


def test_diagnostic_snapshot_notes_account_profile_pollution() -> None:
    settings = load_settings()
    account_profile = _account_profile_payload(
        settings=settings,
        runtime_health={
            "dry_run": True,
            "order_execution_enabled": False,
            "account_position_status": {
                "account_profile": "binance_rest",
                "account_source": "binance_rest",
                "positions": [
                    {
                        "symbol": "BTCUSDT",
                        "position_pct": settings.risk_config.max_position_pct_per_symbol + 1,
                    }
                ],
            },
        },
    )
    summary = _diagnostic_summary(
        active_strategy_plan={"status": "NO_ACTIVE_STRATEGY_PLAN", "plan": None},
        account_profile=account_profile,
        data_quality={},
        readiness={},
        blocking_attribution={"would_place_order": 0},
        errors=[],
        counts={},
    )
    assert account_profile["shadow_position_polluted"] is True
    assert "TESTNET_POSITION_POLLUTION" in summary["primary_blockers"]
    assert any("Shadow results may be dominated" in note for note in summary["notes"])


def test_diagnostic_snapshot_notes_flat_account_profile() -> None:
    settings = load_settings().model_copy(update={"dry_run_account_profile": "flat"})
    account_profile = _account_profile_payload(
        settings=settings,
        runtime_health={
            "dry_run": True,
            "order_execution_enabled": False,
            "account_position_status": {
                "account_profile": "flat",
                "account_source": "dry_run_flat_profile",
                "positions": [],
            },
        },
    )
    assert account_profile["profile"] == "flat"
    assert account_profile["shadow_position_polluted"] is False
    assert any("simulated flat account" in note for note in account_profile["notes"])


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
