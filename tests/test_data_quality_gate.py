from __future__ import annotations

from datetime import UTC, datetime, timedelta

from config.settings import load_settings
from data_quality.gate import DataQualityGate
from data_quality.schemas import DataQualitySeverity


def _healthy_kwargs() -> dict[str, object]:
    now = datetime.now(UTC)
    return {
        "market_stream_connected": True,
        "user_stream_connected": True,
        "last_kline_time": now,
        "last_user_event_time": now,
        "data_delay_seconds": 1,
        "exchange_filters_available": True,
        "account_state_status": "ok",
        "position_state_status": "ok",
        "indicator_nan_count": 0,
        "kline_count": 120,
        "for_real_order": False,
    }


def test_market_stream_disconnected_is_critical() -> None:
    kwargs = _healthy_kwargs() | {"market_stream_connected": False}
    snapshot = DataQualityGate(load_settings()).evaluate_runtime_health(**kwargs)
    assert snapshot.overall_status == DataQualitySeverity.CRITICAL
    assert snapshot.safe_for_signal_review is False


def test_stale_kline_blocks_signal_review() -> None:
    kwargs = _healthy_kwargs() | {"last_kline_time": datetime.now(UTC) - timedelta(hours=2)}
    snapshot = DataQualityGate(load_settings()).evaluate_runtime_health(**kwargs)
    assert snapshot.overall_status == DataQualitySeverity.CRITICAL
    assert snapshot.safe_for_signal_review is False


def test_nan_indicator_blocks_signal_review() -> None:
    kwargs = _healthy_kwargs() | {"indicator_nan_count": 1}
    snapshot = DataQualityGate(load_settings()).evaluate_runtime_health(**kwargs)
    assert snapshot.overall_status == DataQualitySeverity.CRITICAL
    assert snapshot.safe_for_signal_review is False


def test_missing_exchange_filters_is_unsafe_for_real_order() -> None:
    kwargs = _healthy_kwargs() | {"exchange_filters_available": False, "for_real_order": True}
    snapshot = DataQualityGate(load_settings()).evaluate_runtime_health(**kwargs)
    assert snapshot.safe_for_order is False
    assert snapshot.safe_for_real_testnet_order is False


def test_user_stream_missing_in_dry_run_is_degraded_not_fatal() -> None:
    kwargs = _healthy_kwargs() | {"user_stream_connected": False, "for_real_order": False}
    snapshot = DataQualityGate(load_settings()).evaluate_runtime_health(**kwargs)
    assert snapshot.overall_status == DataQualitySeverity.DEGRADED
    assert snapshot.safe_for_order is True


def test_user_stream_missing_for_real_order_blocks_order() -> None:
    kwargs = _healthy_kwargs() | {"user_stream_connected": False, "for_real_order": True}
    snapshot = DataQualityGate(load_settings()).evaluate_runtime_health(**kwargs)
    assert snapshot.safe_for_order is False


def test_account_and_position_unknown_for_real_order_blocks_order() -> None:
    kwargs = _healthy_kwargs() | {
        "account_state_status": "unknown",
        "position_state_status": "unknown",
        "for_real_order": True,
    }
    snapshot = DataQualityGate(load_settings()).evaluate_runtime_health(**kwargs)
    assert snapshot.safe_for_order is False


def test_live_enabled_is_critical(monkeypatch) -> None:
    monkeypatch.setenv("LIVE_TRADING_ENABLED", "true")
    snapshot = DataQualityGate(load_settings()).evaluate_runtime_health(**_healthy_kwargs())
    assert snapshot.overall_status == DataQualitySeverity.CRITICAL


def test_ai_direct_order_flag_is_critical(monkeypatch) -> None:
    monkeypatch.setenv("AI_CAN_PLACE_ORDER_DIRECTLY", "true")
    snapshot = DataQualityGate(load_settings()).evaluate_runtime_health(**_healthy_kwargs())
    assert snapshot.overall_status == DataQualitySeverity.CRITICAL
