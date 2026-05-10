from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

import scripts.smoke_test_testnet as smoke
from ai.schemas import SignalReview
from binance_client.errors import BinanceAPIError
from binance_client.exchange_info import SymbolFilters
from strategies.base import StrategySignalPayload


@pytest.mark.asyncio
async def test_smoke_default_does_not_call_real_order_stage(monkeypatch) -> None:
    called_real_order = False

    monkeypatch.setattr(smoke, "_config_error", lambda summary, require_openai: None)
    monkeypatch.setattr(
        smoke,
        "run_diagnostics",
        lambda include_openai=False: _async(
            {
                "environment": {"proxy_env": {"HTTP_PROXY": "absent"}},
                "connectivity": {
                    "binance_testnet_rest": {"status": "OK"},
                    "binance_testnet_ws": {"status": "OK"},
                    "openai_api": {"status": "SKIPPED"},
                },
                "recommended_next_action": [],
            }
        ),
    )
    monkeypatch.setattr(
        smoke,
        "_stage1_rest",
        lambda report, broker, settings: _async(
            (
                {},
                {
                    "BTCUSDT": SymbolFilters(
                        "BTCUSDT",
                        Decimal("0.1"),
                        Decimal("0.001"),
                        Decimal("0.001"),
                        Decimal("10"),
                    )
                },
            )
        ),
    )
    monkeypatch.setattr(smoke, "_stage2_market_data", lambda report, broker, settings: _async({}))
    monkeypatch.setattr(
        smoke,
        "_build_signal_and_snapshot",
        lambda settings, frames: (_signal(), {"symbol": "BTCUSDT", "price": 100}),
    )
    monkeypatch.setattr(
        smoke,
        "_stage2_5_data_quality",
        lambda *args, **kwargs: {
            "overall_status": "OK",
            "safe_for_signal_review": True,
            "safe_for_order": True,
            "issues": [],
        },
    )
    monkeypatch.setattr(
        smoke,
        "_stage3_ai",
        lambda report, settings, snapshot, with_ai: _async((_review(), True)),
    )
    monkeypatch.setattr(
        smoke,
        "_stage4_risk",
        lambda report, settings, filters, signal, snapshot, review: (
            SimpleNamespace(approved=True, reason="ok", risk_state_json={}),
            SimpleNamespace(adjusted_entry_price=Decimal("100"), adjusted_quantity=Decimal("0.1")),
        ),
    )
    monkeypatch.setattr(
        smoke, "_stage5_test_order", lambda report, broker, signal, sized: _async(True)
    )

    async def fake_real_order(*args, **kwargs):
        nonlocal called_real_order
        called_real_order = True

    monkeypatch.setattr(smoke, "_stage6_real_testnet_order", fake_real_order)
    report = await smoke.smoke_test()
    assert report["status"] == "TEST_ORDER_COMPLETE"
    assert called_real_order is False


@pytest.mark.asyncio
async def test_smoke_signature_error_marks_test_order_signature_failed(monkeypatch) -> None:
    report = {"stages": []}

    class Broker:
        async def test_order(self, request):
            raise BinanceAPIError(-1022, "Signature for this request is not valid.")

    ok = await smoke._stage5_test_order(  # noqa: SLF001 - direct stage unit test
        report,
        Broker(),
        _signal(),
        SimpleNamespace(adjusted_entry_price=Decimal("100"), adjusted_quantity=Decimal("0.1")),
    )
    assert ok is False
    assert report["test_order_failure_status"] == "TEST_ORDER_SIGNATURE_FAILED"
    assert report["stages"][0]["error_code"] == -1022


def _async(value):
    async def inner(*args, **kwargs):
        return value

    return inner()


def _signal() -> StrategySignalPayload:
    return StrategySignalPayload(
        symbol="BTCUSDT",
        strategy_name="ema_trend",
        strategy_version="v1.0",
        timeframe="5m",
        side="BUY",
        signal_type="TEST",
        confidence=0.5,
        reason="test",
        raw_payload_json={},
    )


def _review() -> SignalReview:
    return SignalReview.model_validate(
        {
            "decision": "APPROVE_TO_RISK_ENGINE",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "confidence": 0.8,
            "risk_level": "low",
            "market_regime": "trend_up",
            "reason": "ok",
            "warnings": [],
            "max_position_pct": 1,
            "requires_human_review": False,
        }
    )
