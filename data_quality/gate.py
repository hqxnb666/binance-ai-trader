from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

import pandas as pd

from config.settings import Settings
from data_quality.schemas import (
    DataQualityAction,
    DataQualityCategory,
    DataQualityIssue,
    DataQualitySeverity,
    DataQualitySnapshot,
)

SEVERITY_RANK = {
    DataQualitySeverity.OK: 0,
    DataQualitySeverity.INFO: 1,
    DataQualitySeverity.WARNING: 2,
    DataQualitySeverity.DEGRADED: 3,
    DataQualitySeverity.CRITICAL: 4,
}


class DataQualityGate:
    """Read-only data quality gate. It can block or warn, never place orders."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def evaluate_runtime_health(
        self,
        *,
        runtime_health: dict[str, Any] | None = None,
        market_stream_connected: bool | None = None,
        user_stream_connected: bool | None = None,
        last_kline_time: datetime | str | None = None,
        last_user_event_time: datetime | str | None = None,
        data_delay_seconds: float | None = None,
        exchange_filters_available: bool | None = None,
        account_state_status: str = "unknown",
        position_state_status: str = "unknown",
        indicator_nan_count: int = 0,
        kline_count: int | None = None,
        active_strategy_plan: dict[str, Any] | None = None,
        for_real_order: bool | None = None,
    ) -> DataQualitySnapshot:
        health = runtime_health or {}
        market_connected = _first_bool(
            market_stream_connected, health.get("market_stream_connected")
        )
        user_connected = _first_bool(user_stream_connected, health.get("user_stream_connected"))
        kline_time = _coerce_datetime(last_kline_time or health.get("last_kline_time"))
        user_event_time = _coerce_datetime(
            last_user_event_time or health.get("last_user_event_time")
        )
        delay = _coerce_float(data_delay_seconds, health.get("data_delay_seconds"))
        return self._evaluate(
            market_stream_connected=market_connected,
            user_stream_connected=user_connected,
            last_kline_time=kline_time,
            last_user_event_time=user_event_time,
            data_delay_seconds=delay,
            exchange_filters_available=exchange_filters_available,
            account_state_status=_state_status(account_state_status),
            position_state_status=_state_status(position_state_status),
            indicator_nan_count=max(indicator_nan_count, 0),
            kline_count=kline_count,
            active_strategy_plan=active_strategy_plan,
            for_real_order=self._is_real_order_path()
            if for_real_order is None
            else for_real_order,
        )

    def evaluate_market_snapshot(
        self,
        *,
        snapshot: dict[str, Any],
        entry_df: pd.DataFrame | None = None,
        trend_df: pd.DataFrame | None = None,
        exchange_filters_available: bool | None = None,
    ) -> DataQualitySnapshot:
        kline_count = _min_frame_count(entry_df, trend_df)
        return self._evaluate(
            market_stream_connected=str(snapshot.get("ws_health", "")).lower() == "ok",
            user_stream_connected=None,
            last_kline_time=_latest_frame_time(entry_df),
            last_user_event_time=None,
            data_delay_seconds=_as_float(snapshot.get("data_delay_seconds")),
            exchange_filters_available=exchange_filters_available,
            account_state_status="unknown",
            position_state_status="unknown",
            indicator_nan_count=_indicator_nan_count(snapshot),
            kline_count=kline_count,
            active_strategy_plan=None,
            for_real_order=False,
        )

    def evaluate_signal_context(
        self,
        *,
        snapshot: dict[str, Any],
        entry_df: pd.DataFrame | None = None,
        trend_df: pd.DataFrame | None = None,
        active_strategy_plan: dict[str, Any] | None = None,
    ) -> DataQualitySnapshot:
        result = self.evaluate_market_snapshot(
            snapshot=snapshot,
            entry_df=entry_df,
            trend_df=trend_df,
        )
        if active_strategy_plan is None:
            return result
        return self._evaluate(
            market_stream_connected=result.market_stream_connected,
            user_stream_connected=result.user_stream_connected,
            last_kline_time=result.last_kline_time,
            last_user_event_time=result.last_user_event_time,
            data_delay_seconds=result.data_delay_seconds,
            exchange_filters_available=result.exchange_filters_available,
            account_state_status=result.account_state_status,
            position_state_status=result.position_state_status,
            indicator_nan_count=result.indicator_nan_count,
            kline_count=None,
            active_strategy_plan=active_strategy_plan,
            for_real_order=False,
        )

    def evaluate_order_preconditions(
        self,
        *,
        symbol: str,
        market_health: dict[str, Any] | None,
        exchange_filters_available: bool,
        account_state_status: str,
        position_state_status: str,
        active_strategy_plan: dict[str, Any] | None = None,
        for_real_order: bool | None = None,
    ) -> DataQualitySnapshot:
        del symbol
        health = market_health or {}
        return self._evaluate(
            market_stream_connected=_first_bool(health.get("market_stream_connected")),
            user_stream_connected=_first_bool(health.get("user_stream_connected")),
            last_kline_time=_coerce_datetime(health.get("last_kline_time")),
            last_user_event_time=_coerce_datetime(health.get("last_user_event_time")),
            data_delay_seconds=_as_float(health.get("data_delay_seconds")),
            exchange_filters_available=exchange_filters_available,
            account_state_status=_state_status(account_state_status),
            position_state_status=_state_status(position_state_status),
            indicator_nan_count=0,
            kline_count=None,
            active_strategy_plan=active_strategy_plan,
            for_real_order=self._is_real_order_path()
            if for_real_order is None
            else for_real_order,
        )

    def evaluate_strategy_planner_preconditions(
        self,
        *,
        runtime_health: dict[str, Any] | None,
        active_strategy_plan: dict[str, Any] | None = None,
    ) -> DataQualitySnapshot:
        return self.evaluate_runtime_health(
            runtime_health=runtime_health,
            active_strategy_plan=active_strategy_plan,
            for_real_order=False,
        )

    def _evaluate(
        self,
        *,
        market_stream_connected: bool | None,
        user_stream_connected: bool | None,
        last_kline_time: datetime | None,
        last_user_event_time: datetime | None,
        data_delay_seconds: float | None,
        exchange_filters_available: bool | None,
        account_state_status: str,
        position_state_status: str,
        indicator_nan_count: int,
        kline_count: int | None,
        active_strategy_plan: dict[str, Any] | None,
        for_real_order: bool,
    ) -> DataQualitySnapshot:
        now = datetime.now(UTC)
        issues: list[DataQualityIssue] = []
        live_enabled = self.settings.live_trading_enabled or self.settings.live_trading.enabled
        if self.settings.trading_mode != "testnet":
            issues.append(
                _issue(
                    DataQualitySeverity.CRITICAL,
                    DataQualityCategory.RUNTIME_STATE,
                    "Runtime is not in testnet mode",
                    [f"trading_mode={self.settings.trading_mode}"],
                    "Return to testnet mode before running this MVP.",
                    strategy=True,
                    signal=True,
                    order=True,
                )
            )
        if live_enabled:
            issues.append(
                _issue(
                    DataQualitySeverity.CRITICAL,
                    DataQualityCategory.RUNTIME_STATE,
                    "Live trading is enabled",
                    ["live_trading_enabled=true"],
                    "Disable live trading; this phase only supports Testnet and dry-run.",
                    strategy=True,
                    signal=True,
                    order=True,
                )
            )
        if self.settings.ai_can_place_order_directly:
            issues.append(
                _issue(
                    DataQualitySeverity.CRITICAL,
                    DataQualityCategory.RUNTIME_STATE,
                    "AI direct order placement flag is enabled",
                    ["AI_CAN_PLACE_ORDER_DIRECTLY=true"],
                    "Disable AI direct order placement; all orders must go through RiskEngine.",
                    strategy=True,
                    signal=True,
                    order=True,
                )
            )
        if self.settings.data_quality_require_market_stream_for_daemon:
            if market_stream_connected is False:
                issues.append(
                    _issue(
                        DataQualitySeverity.CRITICAL,
                        DataQualityCategory.MARKET_STREAM,
                        "Market stream is disconnected",
                        ["market_stream_connected=false"],
                        "Wait for market stream recovery or use REST-only diagnostics.",
                        strategy=True,
                        signal=True,
                        order=True,
                    )
                )
            elif market_stream_connected is None:
                issues.append(
                    _issue(
                        DataQualitySeverity.DEGRADED,
                        DataQualityCategory.MARKET_STREAM,
                        "Market stream state is unknown",
                        ["market_stream_connected=unknown"],
                        "Confirm market stream health before relying on live signals.",
                        strategy=False,
                        signal=True,
                        order=True,
                    )
                )
        if data_delay_seconds is not None and math.isfinite(data_delay_seconds):
            if data_delay_seconds > self.settings.data_quality_max_market_delay_seconds:
                severity = (
                    DataQualitySeverity.CRITICAL
                    if data_delay_seconds > self.settings.data_quality_max_kline_staleness_seconds
                    else DataQualitySeverity.DEGRADED
                )
                issues.append(
                    _issue(
                        severity,
                        DataQualityCategory.MARKET_STREAM,
                        "Market data delay exceeds threshold",
                        [f"data_delay_seconds={data_delay_seconds:.3f}"],
                        "Wait for fresh market data before reviewing new signals.",
                        strategy=severity == DataQualitySeverity.CRITICAL,
                        signal=True,
                        order=True,
                    )
                )
        elif data_delay_seconds is not None:
            issues.append(
                _issue(
                    DataQualitySeverity.DEGRADED,
                    DataQualityCategory.MARKET_STREAM,
                    "Market data delay is not finite",
                    [f"data_delay_seconds={data_delay_seconds}"],
                    "Verify stream or REST polling before continuing.",
                    strategy=True,
                    signal=True,
                    order=True,
                )
            )
        staleness = _staleness_seconds(last_kline_time, now)
        if last_kline_time is None:
            issues.append(
                _issue(
                    DataQualitySeverity.DEGRADED,
                    DataQualityCategory.KLINE_STALENESS,
                    "Latest kline timestamp is missing",
                    ["last_kline_time=null"],
                    "Load closed klines before creating trade reviews or orders.",
                    strategy=False,
                    signal=True,
                    order=True,
                )
            )
        elif (
            staleness is not None
            and staleness > self.settings.data_quality_max_kline_staleness_seconds
        ):
            issues.append(
                _issue(
                    DataQualitySeverity.CRITICAL,
                    DataQualityCategory.KLINE_STALENESS,
                    "Kline data is stale",
                    [f"kline_staleness_seconds={staleness:.3f}"],
                    "Refresh klines before generating signals.",
                    strategy=True,
                    signal=True,
                    order=True,
                )
            )
        if kline_count is not None and kline_count < self.settings.data_quality_min_required_klines:
            issues.append(
                _issue(
                    DataQualitySeverity.CRITICAL,
                    DataQualityCategory.KLINE_STALENESS,
                    "Insufficient closed klines",
                    [
                        f"kline_count={kline_count}",
                        f"minimum={self.settings.data_quality_min_required_klines}",
                    ],
                    "Collect enough 5m/1h klines before generating a signal.",
                    strategy=True,
                    signal=True,
                    order=True,
                )
            )
        if indicator_nan_count > self.settings.data_quality_max_nan_indicators:
            issues.append(
                _issue(
                    DataQualitySeverity.CRITICAL,
                    DataQualityCategory.INDICATORS,
                    "Indicator output contains NaN values",
                    [f"indicator_nan_count={indicator_nan_count}"],
                    "Rebuild indicators from complete kline data.",
                    strategy=True,
                    signal=True,
                    order=True,
                )
            )
        if (
            self.settings.data_quality_require_exchange_filters
            and exchange_filters_available is False
        ):
            severity = (
                DataQualitySeverity.CRITICAL if for_real_order else DataQualitySeverity.WARNING
            )
            issues.append(
                _issue(
                    severity,
                    DataQualityCategory.EXCHANGE_FILTERS,
                    "Exchange filters are unavailable",
                    ["exchange_filters_available=false"],
                    "Load exchangeInfo filters before validating quantity and price.",
                    strategy=False,
                    signal=False,
                    order=True,
                )
            )
        if for_real_order and self.settings.data_quality_require_user_stream_for_real_order:
            if user_stream_connected is not True:
                issues.append(
                    _issue(
                        DataQualitySeverity.CRITICAL,
                        DataQualityCategory.USER_STREAM,
                        "User stream is required for real Testnet orders",
                        [f"user_stream_connected={user_stream_connected}"],
                        "Reconnect the user stream before submitting a real Testnet order.",
                        strategy=False,
                        signal=False,
                        order=True,
                    )
                )
        elif (
            user_stream_connected is False
            and self.settings.data_quality_allow_user_stream_missing_in_dry_run
        ):
            issues.append(
                _issue(
                    DataQualitySeverity.DEGRADED,
                    DataQualityCategory.USER_STREAM,
                    "User stream is missing in dry-run",
                    ["user_stream_connected=false", "dry_run=true"],
                    "Dry-run can continue, but real Testnet orders need user stream health.",
                    strategy=False,
                    signal=False,
                    order=False,
                )
            )
        user_staleness = _staleness_seconds(last_user_event_time, now)
        if (
            user_staleness is not None
            and user_staleness > self.settings.data_quality_max_user_stream_delay_seconds
        ):
            issues.append(
                _issue(
                    DataQualitySeverity.WARNING,
                    DataQualityCategory.USER_STREAM,
                    "User stream has not emitted recent events",
                    [f"user_stream_staleness_seconds={user_staleness:.3f}"],
                    "If orders are active, verify user stream and REST reconciliation.",
                    strategy=False,
                    signal=False,
                    order=for_real_order,
                )
            )
        if for_real_order and self.settings.data_quality_require_account_state_for_real_order:
            if account_state_status != "ok":
                issues.append(
                    _issue(
                        DataQualitySeverity.CRITICAL,
                        DataQualityCategory.ACCOUNT_STATE,
                        "Account state is not confirmed",
                        [f"account_state_status={account_state_status}"],
                        "Fetch account state before submitting a real Testnet order.",
                        strategy=False,
                        signal=False,
                        order=True,
                    )
                )
        elif account_state_status == "simulated_default":
            issues.append(
                _issue(
                    DataQualitySeverity.INFO,
                    DataQualityCategory.ACCOUNT_STATE,
                    "Account state is simulated",
                    ["account_state_status=simulated_default"],
                    "Treat results as dry-run only until account state is synchronized.",
                    strategy=False,
                    signal=False,
                    order=False,
                )
            )
        if for_real_order and self.settings.data_quality_require_position_state_for_real_order:
            if position_state_status != "ok":
                issues.append(
                    _issue(
                        DataQualitySeverity.CRITICAL,
                        DataQualityCategory.POSITION_STATE,
                        "Position state is not confirmed",
                        [f"position_state_status={position_state_status}"],
                        "Synchronize positions before submitting a real Testnet order.",
                        strategy=False,
                        signal=False,
                        order=True,
                    )
                )
        elif position_state_status == "simulated_default":
            issues.append(
                _issue(
                    DataQualitySeverity.INFO,
                    DataQualityCategory.POSITION_STATE,
                    "Position state is simulated",
                    ["position_state_status=simulated_default"],
                    "Treat results as dry-run only until position state is synchronized.",
                    strategy=False,
                    signal=False,
                    order=False,
                )
            )
        if active_strategy_plan:
            issues.extend(_strategy_plan_issues(active_strategy_plan))
        return _snapshot(
            issues=issues,
            market_stream_connected=market_stream_connected,
            user_stream_connected=user_stream_connected,
            last_kline_time=last_kline_time,
            last_user_event_time=last_user_event_time,
            data_delay_seconds=data_delay_seconds,
            kline_staleness_seconds=staleness,
            indicator_nan_count=indicator_nan_count,
            exchange_filters_available=exchange_filters_available,
            account_state_status=_state_status(account_state_status),
            position_state_status=_state_status(position_state_status),
            block_order_on_warning=self.settings.data_quality_block_order_on_warning,
            for_real_order=for_real_order,
        )

    def _is_real_order_path(self) -> bool:
        return self.settings.order_execution_enabled and not self.settings.trading_dry_run


def _snapshot(
    *,
    issues: list[DataQualityIssue],
    market_stream_connected: bool | None,
    user_stream_connected: bool | None,
    last_kline_time: datetime | None,
    last_user_event_time: datetime | None,
    data_delay_seconds: float | None,
    kline_staleness_seconds: float | None,
    indicator_nan_count: int,
    exchange_filters_available: bool | None,
    account_state_status: str,
    position_state_status: str,
    block_order_on_warning: bool,
    for_real_order: bool,
) -> DataQualitySnapshot:
    highest = _highest_severity(issues)
    safe_strategy = not any(issue.blocks_strategy_planner for issue in issues)
    safe_signal = not any(issue.blocks_signal_review for issue in issues)
    safe_order = not any(issue.blocks_order for issue in issues)
    if block_order_on_warning and highest in {
        DataQualitySeverity.WARNING,
        DataQualitySeverity.DEGRADED,
        DataQualitySeverity.CRITICAL,
    }:
        safe_order = False
    safe_real = (
        safe_order
        and for_real_order
        and exchange_filters_available is True
        and account_state_status == "ok"
        and position_state_status == "ok"
        and user_stream_connected is True
    )
    action = _action(issues, block_order_on_warning)
    return DataQualitySnapshot(
        created_at=datetime.now(UTC),
        overall_status=highest,
        action=action,
        issues=issues,
        market_stream_connected=market_stream_connected,
        user_stream_connected=user_stream_connected,
        last_kline_time=last_kline_time,
        last_user_event_time=last_user_event_time,
        data_delay_seconds=data_delay_seconds,
        kline_staleness_seconds=kline_staleness_seconds,
        indicator_nan_count=indicator_nan_count,
        exchange_filters_available=exchange_filters_available,
        account_state_status=_state_status(account_state_status),
        position_state_status=_state_status(position_state_status),
        safe_for_strategy_planner=safe_strategy,
        safe_for_signal_review=safe_signal,
        safe_for_order=safe_order,
        safe_for_real_testnet_order=safe_real,
        reason_codes=[_reason_code(issue) for issue in issues],
    )


def _issue(
    severity: DataQualitySeverity,
    category: DataQualityCategory,
    title: str,
    evidence: list[str],
    recommended_action: str,
    *,
    strategy: bool,
    signal: bool,
    order: bool,
) -> DataQualityIssue:
    return DataQualityIssue(
        severity=severity,
        category=category,
        title=title,
        evidence=evidence,
        recommended_action=recommended_action,
        blocks_strategy_planner=strategy,
        blocks_signal_review=signal,
        blocks_order=order,
        requires_human_review=severity
        in {DataQualitySeverity.DEGRADED, DataQualitySeverity.CRITICAL},
    )


def _highest_severity(issues: list[DataQualityIssue]) -> DataQualitySeverity:
    if not issues:
        return DataQualitySeverity.OK
    return max((issue.severity for issue in issues), key=lambda item: SEVERITY_RANK[item])


def _action(issues: list[DataQualityIssue], block_order_on_warning: bool) -> DataQualityAction:
    highest = _highest_severity(issues)
    if any(issue.blocks_order for issue in issues) or (
        block_order_on_warning
        and highest in {
            DataQualitySeverity.WARNING,
            DataQualitySeverity.DEGRADED,
            DataQualitySeverity.CRITICAL,
        }
    ):
        return DataQualityAction.BLOCK_ORDER
    if any(issue.blocks_signal_review for issue in issues):
        return DataQualityAction.BLOCK_SIGNAL_REVIEW
    if any(issue.blocks_strategy_planner for issue in issues):
        return DataQualityAction.BLOCK_STRATEGY_PLANNER
    if highest != DataQualitySeverity.OK:
        return DataQualityAction.WARN
    return DataQualityAction.ALLOW


def _reason_code(issue: DataQualityIssue) -> str:
    return f"{issue.category.value}:{issue.title.upper().replace(' ', '_')[:60]}"


def _strategy_plan_issues(plan: dict[str, Any]) -> list[DataQualityIssue]:
    issues: list[DataQualityIssue] = []
    expires_at = _coerce_datetime(plan.get("expires_at"))
    if expires_at is not None and expires_at <= datetime.now(UTC):
        issues.append(
            _issue(
                DataQualitySeverity.DEGRADED,
                DataQualityCategory.STRATEGY_PLAN,
                "Active StrategyPlan is expired",
                [f"expires_at={expires_at.isoformat()}"],
                "Refresh the StrategyPlan or require human review before trading.",
                strategy=False,
                signal=True,
                order=True,
            )
        )
    if plan.get("requires_human_review") is True:
        issues.append(
            _issue(
                DataQualitySeverity.DEGRADED,
                DataQualityCategory.STRATEGY_PLAN,
                "StrategyPlan requires human review",
                ["requires_human_review=true"],
                "Complete human review before allowing order creation.",
                strategy=False,
                signal=False,
                order=True,
            )
        )
    if plan.get("risk_mode") == "no_trade" or plan.get("trade_bias") == "no_trade":
        issues.append(
            _issue(
                DataQualitySeverity.WARNING,
                DataQualityCategory.STRATEGY_PLAN,
                "StrategyPlan is no-trade",
                ["risk_mode=no_trade or trade_bias=no_trade"],
                "Do not create orders while the active strategy plan is no-trade.",
                strategy=False,
                signal=False,
                order=True,
            )
        )
    return issues


def _indicator_nan_count(snapshot: dict[str, Any]) -> int:
    keys = (
        "ema_fast_5m",
        "ema_slow_5m",
        "ema_fast_1h",
        "ema_slow_1h",
        "rsi14_5m",
        "atr14_5m",
        "volume_ratio_5m",
    )
    count = 0
    for key in keys:
        value = snapshot.get(key)
        if value is None:
            count += 1
            continue
        try:
            if math.isnan(float(value)):
                count += 1
        except (TypeError, ValueError):
            count += 1
    return count


def _min_frame_count(*frames: pd.DataFrame | None) -> int | None:
    counts = [len(frame) for frame in frames if frame is not None]
    return min(counts) if counts else None


def _latest_frame_time(frame: pd.DataFrame | None) -> datetime | None:
    if frame is None or frame.empty:
        return None
    for column in ("close_time", "open_time"):
        if column not in frame.columns:
            continue
        value = frame[column].iloc[-1]
        if isinstance(value, pd.Timestamp):
            if value.tzinfo is None:
                return value.to_pydatetime().replace(tzinfo=UTC)
            return value.to_pydatetime().astimezone(UTC)
        return _coerce_datetime(value)
    return None


def _first_bool(*values: Any) -> bool | None:
    for value in values:
        if isinstance(value, bool):
            return value
    return None


def _coerce_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, str) and value:
        try:
            normalized = value.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized)
            return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            return None
    return None


def _coerce_float(*values: Any) -> float | None:
    for value in values:
        result = _as_float(value)
        if result is not None:
            return result
    return None


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _staleness_seconds(value: datetime | None, now: datetime) -> float | None:
    if value is None:
        return None
    return max((now - value).total_seconds(), 0.0)


def _state_status(value: str) -> str:
    normalized = str(value or "unknown").lower()
    if normalized in {"ok", "unknown", "simulated_default", "error"}:
        return normalized
    return "unknown"
