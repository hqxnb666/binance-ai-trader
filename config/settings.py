from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, SecretStr, field_validator

BASE_DIR = Path(__file__).resolve().parents[1]


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_secret(name: str) -> SecretStr | None:
    value = os.getenv(name)
    value = value.strip() if value else value
    if not value or value.startswith("your_"):
        return None
    return SecretStr(value)


def _env_str(name: str, default: str, *, allow_empty: bool = False) -> str:
    value = os.getenv(name)
    if value is None:
        return default
    if not value.strip():
        return "" if allow_empty else default
    return value.strip()


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return int(value)


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return float(value)


def _env_csv(name: str, default: list[str]) -> list[str]:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        msg = f"YAML file must contain an object: {path}"
        raise ValueError(msg)
    return data


class SymbolConfig(BaseModel):
    symbol: str
    enabled: bool = True
    base_asset: str
    quote_asset: str

    @field_validator("symbol", "base_asset", "quote_asset")
    @classmethod
    def uppercase(cls, value: str) -> str:
        return value.upper()


class TimeframeConfig(BaseModel):
    entry: str = "5m"
    trend: str = "1h"


class SymbolsFileConfig(BaseModel):
    symbols: list[SymbolConfig]
    timeframes: TimeframeConfig

    @property
    def enabled_symbols(self) -> list[str]:
        return [item.symbol for item in self.symbols if item.enabled]


class RiskConfig(BaseModel):
    max_single_trade_risk_pct: float = 0.5
    max_daily_loss_pct: float = 2.0
    max_position_pct_per_symbol: float = 10.0
    max_total_position_pct: float = 30.0
    max_consecutive_losses: int = 3
    cooldown_minutes_per_symbol: int = 10
    block_on_ws_disconnect: bool = True
    block_on_ai_schema_error: bool = True
    block_on_data_delay_seconds: float = 3.0
    allow_market_orders: bool = False
    allow_limit_orders: bool = True
    kill_switch_enabled: bool = False
    max_orders_per_minute: int = 6


class LiveTradingConfig(BaseModel):
    enabled: bool = False
    require_manual_enable: bool = True
    require_env_live_enabled: bool = True


class RiskFileConfig(BaseModel):
    risk: RiskConfig
    live_trading: LiveTradingConfig


class EmaTrendConfig(BaseModel):
    enabled: bool = True
    entry_timeframe: str = "5m"
    trend_timeframe: str = "1h"
    ema_fast: int = 20
    ema_slow: int = 60
    rsi_period: int = 14
    rsi_min: float = 45.0
    rsi_max: float = 70.0
    atr_period: int = 14
    volume_ratio_min: float = 1.1
    take_profit_r_multiple: float = 2.0
    stop_loss_atr_multiple: float = 1.5


class StrategyFileConfig(BaseModel):
    ema_trend: EmaTrendConfig


class Settings(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    app_env: str = "development"
    log_level: str = "INFO"
    trading_mode: Literal["testnet", "live"] = "testnet"
    live_trading_enabled: bool = False
    trading_dry_run: bool = True
    order_execution_enabled: bool = False

    binance_testnet_api_key: SecretStr | None = None
    binance_testnet_api_secret: SecretStr | None = None
    binance_live_api_key: SecretStr | None = None
    binance_live_api_secret: SecretStr | None = None

    openai_api_key: SecretStr | None = None
    openai_model: str = ""
    openai_default_model: str = "gpt-5.4-nano"
    openai_diagnostic_model: str = "gpt-5.4-nano"
    openai_strategy_model: str = "gpt-5.5"
    openai_signal_model: str = "gpt-5.4-mini"
    openai_trade_review_model: str = "gpt-5.4-mini"
    openai_daily_report_model: str = "gpt-5.4-nano"
    openai_system_auditor_model: str = "gpt-5.4-mini"
    openai_deep_auditor_model: str = "gpt-5.5"
    openai_strategy_interval_minutes: int = 60
    openai_strategy_max_output_tokens: int = 900
    openai_signal_max_output_tokens: int = 450
    openai_trade_review_max_output_tokens: int = 600
    openai_daily_report_max_output_tokens: int = 900
    openai_diagnostic_max_output_tokens: int = 120
    openai_system_auditor_max_output_tokens: int = 1600
    openai_deep_auditor_max_output_tokens: int = 2000
    openai_enable_model_fallback: bool = False
    openai_fallback_models: list[str] = ["gpt-5.4-mini", "gpt-5.4"]
    enable_strategy_planner: bool = True
    enable_system_auditor: bool = True
    enable_deep_auditor: bool = False
    system_audit_interval_minutes: int = 120
    system_audit_lookback_hours: int = 6
    system_audit_min_severity_to_health_warn: str = "HIGH"
    system_auditor_auto_fix_allowed: bool = False
    system_auditor_can_call_codex: bool = False
    system_auditor_can_modify_config: bool = False
    system_auditor_can_modify_strategy: bool = False
    system_auditor_can_place_order: bool = False
    system_auditor_max_issues: int = 5
    system_auditor_max_evidence_per_issue: int = 3
    system_auditor_max_text_chars: int = 600
    enable_data_quality_gate: bool = True
    data_quality_max_market_delay_seconds: float = 15.0
    data_quality_max_user_stream_delay_seconds: float = 60.0
    data_quality_max_kline_staleness_seconds: float = 600.0
    data_quality_require_market_stream_for_daemon: bool = True
    data_quality_require_user_stream_for_real_order: bool = True
    data_quality_allow_user_stream_missing_in_dry_run: bool = True
    data_quality_block_strategy_planner_on_critical: bool = True
    data_quality_block_signal_review_on_critical: bool = True
    data_quality_block_order_on_warning: bool = False
    data_quality_block_order_on_critical: bool = True
    data_quality_max_nan_indicators: int = 0
    data_quality_min_required_klines: int = 50
    data_quality_require_exchange_filters: bool = True
    data_quality_require_account_state_for_real_order: bool = True
    data_quality_require_position_state_for_real_order: bool = True
    data_quality_report_dir: str = "reports/data_quality"
    enable_shadow_mode: bool = True
    shadow_mode_record_rejected_signals: bool = True
    shadow_mode_record_approved_only: bool = False
    shadow_mode_simulated_hold_minutes: int = 60
    shadow_mode_evaluation_interval_minutes: int = 5
    shadow_mode_max_open_shadow_trades: int = 50
    shadow_mode_report_dir: str = "reports/shadow"
    shadow_mode_default_exit_policy: str = "time_based"
    shadow_mode_track_mfe_mae: bool = True
    shadow_mode_allow_when_dry_run: bool = True
    shadow_mode_disable_when_real_order_enabled: bool = True
    openai_daily_budget_usd: float = 1.0
    openai_monthly_budget_usd: float = 20.0
    openai_strategy_daily_call_limit: int = 24
    openai_signal_daily_call_limit: int = 1000
    openai_fail_closed_on_budget_exceeded: bool = True
    enable_openai_usage_ledger: bool = True
    enable_budget_guard: bool = True
    ai_context_recent_signal_reviews_limit: int = 20
    ai_context_recent_risk_decisions_limit: int = 20
    ai_context_recent_orders_limit: int = 20
    ai_context_recent_trade_reviews_limit: int = 10
    ai_context_max_json_chars: int = 24000

    database_url: str = "sqlite:///./trading_bot.db"

    binance_spot_testnet_rest_base: str = "https://testnet.binance.vision/api"
    binance_spot_testnet_stream_base: str = "wss://stream.testnet.binance.vision/ws"
    binance_spot_testnet_ws_api_base: str = "wss://ws-api.testnet.binance.vision/ws-api/v3"

    binance_spot_live_rest_base: str = "https://api.binance.com/api"
    binance_spot_live_stream_base: str = "wss://stream.binance.com:9443/ws"
    binance_spot_live_ws_api_base: str = "wss://ws-api.binance.com:443/ws-api/v3"

    ai_analysis_enabled: bool = True
    ai_can_propose_trade: bool = True
    ai_can_place_order_directly: bool = False

    symbols: SymbolsFileConfig
    risk_config: RiskConfig
    live_trading: LiveTradingConfig
    strategy: StrategyFileConfig

    def safe_config(self) -> dict[str, Any]:
        return {
            "app_env": self.app_env,
            "log_level": self.log_level,
            "trading_mode": self.trading_mode,
            "live_trading_enabled": self.live_trading_enabled,
            "trading_dry_run": self.trading_dry_run,
            "order_execution_enabled": self.order_execution_enabled,
            "database_url": self.database_url,
            "binance": {
                "testnet_rest_base": self.binance_spot_testnet_rest_base,
                "testnet_stream_base": self.binance_spot_testnet_stream_base,
                "testnet_ws_api_base": self.binance_spot_testnet_ws_api_base,
                "live_rest_base": self.binance_spot_live_rest_base,
                "live_stream_base": self.binance_spot_live_stream_base,
                "live_ws_api_base": self.binance_spot_live_ws_api_base,
                "has_testnet_key": self.binance_testnet_api_key is not None,
                "has_live_key": self.binance_live_api_key is not None,
            },
            "openai": {
                "legacy_model": self.openai_model,
                "default_model": self.openai_default_model,
                "diagnostic_model": self.openai_diagnostic_model,
                "strategy_model": self.openai_strategy_model,
                "signal_model": self.openai_signal_model,
                "trade_review_model": self.openai_trade_review_model,
                "daily_report_model": self.openai_daily_report_model,
                "system_auditor_model": self.openai_system_auditor_model,
                "deep_auditor_model": self.openai_deep_auditor_model,
                "strategy_interval_minutes": self.openai_strategy_interval_minutes,
                "enable_model_fallback": self.openai_enable_model_fallback,
                "fallback_models": self.openai_fallback_models,
                "enable_strategy_planner": self.enable_strategy_planner,
                "enable_system_auditor": self.enable_system_auditor,
                "enable_deep_auditor": self.enable_deep_auditor,
                "system_audit_interval_minutes": self.system_audit_interval_minutes,
                "system_audit_lookback_hours": self.system_audit_lookback_hours,
                "system_auditor_auto_fix_allowed": self.system_auditor_auto_fix_allowed,
                "system_auditor_can_call_codex": self.system_auditor_can_call_codex,
                "system_auditor_can_modify_config": self.system_auditor_can_modify_config,
                "system_auditor_can_modify_strategy": self.system_auditor_can_modify_strategy,
                "system_auditor_can_place_order": self.system_auditor_can_place_order,
                "system_auditor_max_issues": self.system_auditor_max_issues,
                "system_auditor_max_evidence_per_issue": self.system_auditor_max_evidence_per_issue,
                "system_auditor_max_text_chars": self.system_auditor_max_text_chars,
                "daily_budget_usd": self.openai_daily_budget_usd,
                "monthly_budget_usd": self.openai_monthly_budget_usd,
                "strategy_daily_call_limit": self.openai_strategy_daily_call_limit,
                "signal_daily_call_limit": self.openai_signal_daily_call_limit,
                "fail_closed_on_budget_exceeded": self.openai_fail_closed_on_budget_exceeded,
                "usage_ledger_enabled": self.enable_openai_usage_ledger,
                "budget_guard_enabled": self.enable_budget_guard,
                "context_max_json_chars": self.ai_context_max_json_chars,
                "analysis_enabled": self.ai_analysis_enabled,
                "can_propose_trade": self.ai_can_propose_trade,
                "can_place_order_directly": self.ai_can_place_order_directly,
                "has_api_key": self.openai_api_key is not None,
            },
            "data_quality": {
                "enabled": self.enable_data_quality_gate,
                "max_market_delay_seconds": self.data_quality_max_market_delay_seconds,
                "max_user_stream_delay_seconds": self.data_quality_max_user_stream_delay_seconds,
                "max_kline_staleness_seconds": self.data_quality_max_kline_staleness_seconds,
                "require_market_stream_for_daemon": (
                    self.data_quality_require_market_stream_for_daemon
                ),
                "require_user_stream_for_real_order": (
                    self.data_quality_require_user_stream_for_real_order
                ),
                "allow_user_stream_missing_in_dry_run": (
                    self.data_quality_allow_user_stream_missing_in_dry_run
                ),
                "block_strategy_planner_on_critical": (
                    self.data_quality_block_strategy_planner_on_critical
                ),
                "block_signal_review_on_critical": (
                    self.data_quality_block_signal_review_on_critical
                ),
                "block_order_on_warning": self.data_quality_block_order_on_warning,
                "block_order_on_critical": self.data_quality_block_order_on_critical,
                "max_nan_indicators": self.data_quality_max_nan_indicators,
                "min_required_klines": self.data_quality_min_required_klines,
                "require_exchange_filters": self.data_quality_require_exchange_filters,
                "require_account_state_for_real_order": (
                    self.data_quality_require_account_state_for_real_order
                ),
                "require_position_state_for_real_order": (
                    self.data_quality_require_position_state_for_real_order
                ),
                "report_dir": self.data_quality_report_dir,
            },
            "shadow_mode": {
                "enabled": self.enable_shadow_mode,
                "record_rejected_signals": self.shadow_mode_record_rejected_signals,
                "record_approved_only": self.shadow_mode_record_approved_only,
                "simulated_hold_minutes": self.shadow_mode_simulated_hold_minutes,
                "evaluation_interval_minutes": self.shadow_mode_evaluation_interval_minutes,
                "max_open_shadow_trades": self.shadow_mode_max_open_shadow_trades,
                "report_dir": self.shadow_mode_report_dir,
                "default_exit_policy": self.shadow_mode_default_exit_policy,
                "track_mfe_mae": self.shadow_mode_track_mfe_mae,
                "allow_when_dry_run": self.shadow_mode_allow_when_dry_run,
                "disable_when_real_order_enabled": (
                    self.shadow_mode_disable_when_real_order_enabled
                ),
            },
            "symbols": self.symbols.model_dump(),
            "risk": self.risk_config.model_dump(),
            "live_trading": self.live_trading.model_dump(),
            "strategy": self.strategy.model_dump(),
        }


def load_settings(base_dir: Path = BASE_DIR) -> Settings:
    load_dotenv(base_dir / ".env", override=False)
    risk_file = RiskFileConfig.model_validate(_load_yaml(base_dir / "config" / "risk.yaml"))
    symbols = SymbolsFileConfig.model_validate(_load_yaml(base_dir / "config" / "symbols.yaml"))
    strategy = StrategyFileConfig.model_validate(_load_yaml(base_dir / "config" / "strategy.yaml"))
    return Settings(
        app_env=os.getenv("APP_ENV", "development"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        trading_mode=os.getenv("TRADING_MODE", "testnet").lower(),
        live_trading_enabled=_env_bool("LIVE_TRADING_ENABLED", False),
        trading_dry_run=_env_bool("TRADING_DRY_RUN", True),
        order_execution_enabled=_env_bool("ORDER_EXECUTION_ENABLED", False),
        binance_testnet_api_key=_env_secret("BINANCE_TESTNET_API_KEY"),
        binance_testnet_api_secret=_env_secret("BINANCE_TESTNET_API_SECRET"),
        binance_live_api_key=_env_secret("BINANCE_LIVE_API_KEY"),
        binance_live_api_secret=_env_secret("BINANCE_LIVE_API_SECRET"),
        openai_api_key=_env_secret("OPENAI_API_KEY"),
        openai_model=_env_str("OPENAI_MODEL", "", allow_empty=True),
        openai_default_model=_env_str(
            "OPENAI_DEFAULT_MODEL", "gpt-5.4-nano", allow_empty=True
        ),
        openai_diagnostic_model=_env_str(
            "OPENAI_DIAGNOSTIC_MODEL", "gpt-5.4-nano", allow_empty=True
        ),
        openai_strategy_model=_env_str("OPENAI_STRATEGY_MODEL", "gpt-5.5", allow_empty=True),
        openai_signal_model=_env_str("OPENAI_SIGNAL_MODEL", "gpt-5.4-mini", allow_empty=True),
        openai_trade_review_model=_env_str(
            "OPENAI_TRADE_REVIEW_MODEL", "gpt-5.4-mini", allow_empty=True
        ),
        openai_daily_report_model=_env_str(
            "OPENAI_DAILY_REPORT_MODEL", "gpt-5.4-nano", allow_empty=True
        ),
        openai_system_auditor_model=_env_str(
            "OPENAI_SYSTEM_AUDITOR_MODEL", "gpt-5.4-mini", allow_empty=True
        ),
        openai_deep_auditor_model=_env_str(
            "OPENAI_DEEP_AUDITOR_MODEL", "gpt-5.5", allow_empty=True
        ),
        openai_strategy_interval_minutes=_env_int("OPENAI_STRATEGY_INTERVAL_MINUTES", 60),
        openai_strategy_max_output_tokens=_env_int("OPENAI_STRATEGY_MAX_OUTPUT_TOKENS", 900),
        openai_signal_max_output_tokens=_env_int("OPENAI_SIGNAL_MAX_OUTPUT_TOKENS", 450),
        openai_trade_review_max_output_tokens=_env_int(
            "OPENAI_TRADE_REVIEW_MAX_OUTPUT_TOKENS", 600
        ),
        openai_daily_report_max_output_tokens=_env_int(
            "OPENAI_DAILY_REPORT_MAX_OUTPUT_TOKENS", 900
        ),
        openai_diagnostic_max_output_tokens=_env_int("OPENAI_DIAGNOSTIC_MAX_OUTPUT_TOKENS", 120),
        openai_system_auditor_max_output_tokens=_env_int(
            "OPENAI_SYSTEM_AUDITOR_MAX_OUTPUT_TOKENS", 1600
        ),
        openai_deep_auditor_max_output_tokens=_env_int(
            "OPENAI_DEEP_AUDITOR_MAX_OUTPUT_TOKENS", 2000
        ),
        openai_enable_model_fallback=_env_bool("OPENAI_ENABLE_MODEL_FALLBACK", False),
        openai_fallback_models=_env_csv("OPENAI_FALLBACK_MODELS", ["gpt-5.4-mini", "gpt-5.4"]),
        enable_strategy_planner=_env_bool("ENABLE_STRATEGY_PLANNER", True),
        enable_system_auditor=_env_bool("ENABLE_SYSTEM_AUDITOR", True),
        enable_deep_auditor=_env_bool("ENABLE_DEEP_AUDITOR", False),
        system_audit_interval_minutes=_env_int("SYSTEM_AUDIT_INTERVAL_MINUTES", 120),
        system_audit_lookback_hours=_env_int("SYSTEM_AUDIT_LOOKBACK_HOURS", 6),
        system_audit_min_severity_to_health_warn=_env_str(
            "SYSTEM_AUDIT_MIN_SEVERITY_TO_HEALTH_WARN", "HIGH"
        ).upper(),
        system_auditor_auto_fix_allowed=False,
        system_auditor_can_call_codex=False,
        system_auditor_can_modify_config=False,
        system_auditor_can_modify_strategy=False,
        system_auditor_can_place_order=False,
        system_auditor_max_issues=_env_int("SYSTEM_AUDITOR_MAX_ISSUES", 5),
        system_auditor_max_evidence_per_issue=_env_int(
            "SYSTEM_AUDITOR_MAX_EVIDENCE_PER_ISSUE", 3
        ),
        system_auditor_max_text_chars=_env_int("SYSTEM_AUDITOR_MAX_TEXT_CHARS", 600),
        enable_data_quality_gate=_env_bool("ENABLE_DATA_QUALITY_GATE", True),
        data_quality_max_market_delay_seconds=_env_float(
            "DATA_QUALITY_MAX_MARKET_DELAY_SECONDS", 15.0
        ),
        data_quality_max_user_stream_delay_seconds=_env_float(
            "DATA_QUALITY_MAX_USER_STREAM_DELAY_SECONDS", 60.0
        ),
        data_quality_max_kline_staleness_seconds=_env_float(
            "DATA_QUALITY_MAX_KLINE_STALENESS_SECONDS", 600.0
        ),
        data_quality_require_market_stream_for_daemon=_env_bool(
            "DATA_QUALITY_REQUIRE_MARKET_STREAM_FOR_DAEMON", True
        ),
        data_quality_require_user_stream_for_real_order=_env_bool(
            "DATA_QUALITY_REQUIRE_USER_STREAM_FOR_REAL_ORDER", True
        ),
        data_quality_allow_user_stream_missing_in_dry_run=_env_bool(
            "DATA_QUALITY_ALLOW_USER_STREAM_MISSING_IN_DRY_RUN", True
        ),
        data_quality_block_strategy_planner_on_critical=_env_bool(
            "DATA_QUALITY_BLOCK_STRATEGY_PLANNER_ON_CRITICAL", True
        ),
        data_quality_block_signal_review_on_critical=_env_bool(
            "DATA_QUALITY_BLOCK_SIGNAL_REVIEW_ON_CRITICAL", True
        ),
        data_quality_block_order_on_warning=_env_bool(
            "DATA_QUALITY_BLOCK_ORDER_ON_WARNING", False
        ),
        data_quality_block_order_on_critical=_env_bool(
            "DATA_QUALITY_BLOCK_ORDER_ON_CRITICAL", True
        ),
        data_quality_max_nan_indicators=_env_int("DATA_QUALITY_MAX_NAN_INDICATORS", 0),
        data_quality_min_required_klines=_env_int("DATA_QUALITY_MIN_REQUIRED_KLINES", 50),
        data_quality_require_exchange_filters=_env_bool(
            "DATA_QUALITY_REQUIRE_EXCHANGE_FILTERS", True
        ),
        data_quality_require_account_state_for_real_order=_env_bool(
            "DATA_QUALITY_REQUIRE_ACCOUNT_STATE_FOR_REAL_ORDER", True
        ),
        data_quality_require_position_state_for_real_order=_env_bool(
            "DATA_QUALITY_REQUIRE_POSITION_STATE_FOR_REAL_ORDER", True
        ),
        data_quality_report_dir=_env_str("DATA_QUALITY_REPORT_DIR", "reports/data_quality"),
        enable_shadow_mode=_env_bool("ENABLE_SHADOW_MODE", True),
        shadow_mode_record_rejected_signals=_env_bool(
            "SHADOW_MODE_RECORD_REJECTED_SIGNALS", True
        ),
        shadow_mode_record_approved_only=_env_bool("SHADOW_MODE_RECORD_APPROVED_ONLY", False),
        shadow_mode_simulated_hold_minutes=_env_int("SHADOW_MODE_SIMULATED_HOLD_MINUTES", 60),
        shadow_mode_evaluation_interval_minutes=_env_int(
            "SHADOW_MODE_EVALUATION_INTERVAL_MINUTES", 5
        ),
        shadow_mode_max_open_shadow_trades=_env_int("SHADOW_MODE_MAX_OPEN_SHADOW_TRADES", 50),
        shadow_mode_report_dir=_env_str("SHADOW_MODE_REPORT_DIR", "reports/shadow"),
        shadow_mode_default_exit_policy=_env_str(
            "SHADOW_MODE_DEFAULT_EXIT_POLICY", "time_based"
        ),
        shadow_mode_track_mfe_mae=_env_bool("SHADOW_MODE_TRACK_MFE_MAE", True),
        shadow_mode_allow_when_dry_run=_env_bool("SHADOW_MODE_ALLOW_WHEN_DRY_RUN", True),
        shadow_mode_disable_when_real_order_enabled=_env_bool(
            "SHADOW_MODE_DISABLE_WHEN_REAL_ORDER_ENABLED", True
        ),
        openai_daily_budget_usd=_env_float("OPENAI_DAILY_BUDGET_USD", 1.0),
        openai_monthly_budget_usd=_env_float("OPENAI_MONTHLY_BUDGET_USD", 20.0),
        openai_strategy_daily_call_limit=_env_int("OPENAI_STRATEGY_DAILY_CALL_LIMIT", 24),
        openai_signal_daily_call_limit=_env_int("OPENAI_SIGNAL_DAILY_CALL_LIMIT", 1000),
        openai_fail_closed_on_budget_exceeded=_env_bool(
            "OPENAI_FAIL_CLOSED_ON_BUDGET_EXCEEDED", True
        ),
        enable_openai_usage_ledger=_env_bool("ENABLE_OPENAI_USAGE_LEDGER", True),
        enable_budget_guard=_env_bool("ENABLE_BUDGET_GUARD", True),
        ai_context_recent_signal_reviews_limit=_env_int(
            "AI_CONTEXT_RECENT_SIGNAL_REVIEWS_LIMIT", 20
        ),
        ai_context_recent_risk_decisions_limit=_env_int(
            "AI_CONTEXT_RECENT_RISK_DECISIONS_LIMIT", 20
        ),
        ai_context_recent_orders_limit=_env_int("AI_CONTEXT_RECENT_ORDERS_LIMIT", 20),
        ai_context_recent_trade_reviews_limit=_env_int(
            "AI_CONTEXT_RECENT_TRADE_REVIEWS_LIMIT", 10
        ),
        ai_context_max_json_chars=_env_int("AI_CONTEXT_MAX_JSON_CHARS", 24000),
        database_url=os.getenv("DATABASE_URL", "sqlite:///./trading_bot.db"),
        binance_spot_testnet_rest_base=os.getenv(
            "BINANCE_SPOT_TESTNET_REST_BASE", "https://testnet.binance.vision/api"
        ),
        binance_spot_testnet_stream_base=os.getenv(
            "BINANCE_SPOT_TESTNET_STREAM_BASE", "wss://stream.testnet.binance.vision/ws"
        ),
        binance_spot_testnet_ws_api_base=os.getenv(
            "BINANCE_SPOT_TESTNET_WS_API_BASE",
            "wss://ws-api.testnet.binance.vision/ws-api/v3",
        ),
        binance_spot_live_rest_base=os.getenv(
            "BINANCE_SPOT_LIVE_REST_BASE", "https://api.binance.com/api"
        ),
        binance_spot_live_stream_base=os.getenv(
            "BINANCE_SPOT_LIVE_STREAM_BASE", "wss://stream.binance.com:9443/ws"
        ),
        binance_spot_live_ws_api_base=os.getenv(
            "BINANCE_SPOT_LIVE_WS_API_BASE", "wss://ws-api.binance.com:443/ws-api/v3"
        ),
        ai_analysis_enabled=_env_bool("AI_ANALYSIS_ENABLED", True),
        ai_can_propose_trade=_env_bool("AI_CAN_PROPOSE_TRADE", True),
        ai_can_place_order_directly=_env_bool("AI_CAN_PLACE_ORDER_DIRECTLY", False),
        symbols=symbols,
        risk_config=risk_file.risk,
        live_trading=risk_file.live_trading,
        strategy=strategy,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()
