from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from config.settings import BASE_DIR

STRATEGY_PATH = BASE_DIR / "config" / "strategy.yaml"
RISK_PATH = BASE_DIR / "config" / "risk.yaml"
STRATEGY_BACKUP_DIR = BASE_DIR / "reports" / "config_backups"

ALLOWED_STRATEGY_TOP_LEVEL_KEYS = {"ema_trend"}
ALLOWED_EMA_TREND_FIELDS = {
    "enabled",
    "entry_timeframe",
    "trend_timeframe",
    "ema_fast",
    "ema_slow",
    "rsi_period",
    "rsi_min",
    "rsi_max",
    "atr_period",
    "volume_ratio_min",
    "take_profit_r_multiple",
    "stop_loss_atr_multiple",
}
ALLOWED_INTERVALS = {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "1d"}

PARAMETER_DESCRIPTIONS = {
    "ema_fast": "Short EMA. Smaller values react faster and create more noisy signals.",
    "ema_slow": "Long EMA. Larger values are steadier but lag more.",
    "rsi_min": "Lower RSI momentum filter. Narrow ranges reduce trade frequency.",
    "rsi_max": "Upper RSI momentum filter. Wider ranges allow weaker signals.",
    "volume_ratio_min": "Volume filter. Higher values are more conservative.",
    "take_profit_r_multiple": "Take-profit R multiple. Higher targets may reduce hit rate.",
    "stop_loss_atr_multiple": "ATR stop multiplier. Wider stops can increase single-trade loss.",
    "entry_timeframe": "Entry timeframe used for the 5m-style candidate signal.",
    "trend_timeframe": "Trend filter timeframe used for higher timeframe confirmation.",
}


class EmaTrendDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    entry_timeframe: str
    trend_timeframe: str
    ema_fast: int = Field(ge=2, le=200)
    ema_slow: int = Field(ge=3, le=400)
    rsi_period: int = Field(ge=2, le=100)
    rsi_min: float = Field(ge=0, le=100)
    rsi_max: float = Field(ge=0, le=100)
    atr_period: int = Field(ge=2, le=100)
    volume_ratio_min: float = Field(ge=0, le=10)
    take_profit_r_multiple: float = Field(ge=0.1, le=20)
    stop_loss_atr_multiple: float = Field(ge=0.1, le=20)

    @model_validator(mode="after")
    def validate_relationships(self) -> EmaTrendDraft:
        errors: list[str] = []
        if self.entry_timeframe not in ALLOWED_INTERVALS:
            errors.append(f"entry_timeframe must be one of {sorted(ALLOWED_INTERVALS)}")
        if self.trend_timeframe not in ALLOWED_INTERVALS:
            errors.append(f"trend_timeframe must be one of {sorted(ALLOWED_INTERVALS)}")
        if self.ema_fast >= self.ema_slow:
            errors.append("ema_fast must be smaller than ema_slow")
        if self.rsi_min >= self.rsi_max:
            errors.append("rsi_min must be smaller than rsi_max")
        if errors:
            raise ValueError("; ".join(errors))
        return self


class StrategyDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ema_trend: EmaTrendDraft


def load_strategy_config() -> dict[str, Any]:
    return _load_yaml(STRATEGY_PATH)


def load_risk_config() -> dict[str, Any]:
    return _load_yaml(RISK_PATH)


def strategy_config_response() -> dict[str, Any]:
    config = load_strategy_config()
    return {
        "config": config,
        "editable_top_level": sorted(ALLOWED_STRATEGY_TOP_LEVEL_KEYS),
        "editable_fields": sorted(ALLOWED_EMA_TREND_FIELDS),
        "allowed_intervals": sorted(ALLOWED_INTERVALS),
        "parameter_descriptions": PARAMETER_DESCRIPTIONS,
        "pending_restart": False,
        "safety_note": (
            "Saving strategy config only writes config/strategy.yaml. It does not hot reload, "
            "restart runtime, place orders, or change risk/live/order-execution settings."
        ),
    }


def validate_strategy_config(payload: dict[str, Any]) -> dict[str, Any]:
    current = load_strategy_config()
    errors = _static_payload_errors(payload)
    draft: StrategyDraft | None = None
    if not errors:
        try:
            draft = StrategyDraft.model_validate(payload)
        except ValidationError as exc:
            errors = _validation_errors(exc)
        except ValueError as exc:
            errors = [str(exc)]
    draft_dict = draft.model_dump() if draft else None
    return {
        "valid": not errors,
        "errors": errors,
        "diff": _diff_strategy(current, draft_dict) if draft_dict else [],
        "draft": draft_dict,
        "editable_fields": sorted(ALLOWED_EMA_TREND_FIELDS),
        "pending_restart": False,
    }


def save_strategy_config(payload: dict[str, Any]) -> dict[str, Any]:
    validation = validate_strategy_config(payload)
    if not validation["valid"] or validation["draft"] is None:
        return {
            "saved": False,
            "valid": False,
            "errors": validation["errors"],
            "diff": validation["diff"],
            "backup_path": None,
            "pending_restart": False,
            "message": "Strategy config was not saved because validation failed.",
        }
    current = load_strategy_config()
    backup_path = _backup_strategy_file()
    updated = {**current, "ema_trend": validation["draft"]["ema_trend"]}
    _write_yaml(STRATEGY_PATH, updated)
    return {
        "saved": True,
        "valid": True,
        "errors": [],
        "diff": validation["diff"],
        "backup_path": str(backup_path),
        "pending_restart": True,
        "message": (
            "Saved config/strategy.yaml. The running process still uses startup config; "
            "restart FastAPI/runtime and validate with backtest plus Shadow Mode."
        ),
    }


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        msg = f"Expected YAML object in {path}"
        raise ValueError(msg)
    return data


def _write_yaml(path: Path, payload: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False, allow_unicode=True)


def _backup_strategy_file() -> Path:
    STRATEGY_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = STRATEGY_BACKUP_DIR / f"strategy-{stamp}.yaml"
    path.write_text(STRATEGY_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    return path


def _static_payload_errors(payload: dict[str, Any]) -> list[str]:
    if not isinstance(payload, dict):
        return ["Payload must be a JSON object."]
    top_unknown = sorted(set(payload) - ALLOWED_STRATEGY_TOP_LEVEL_KEYS)
    if top_unknown:
        return [f"Unknown top-level strategy keys are not allowed: {top_unknown}"]
    if "ema_trend" not in payload:
        return ["Missing ema_trend section."]
    ema = payload["ema_trend"]
    if not isinstance(ema, dict):
        return ["ema_trend must be an object."]
    unknown_fields = sorted(set(ema) - ALLOWED_EMA_TREND_FIELDS)
    if unknown_fields:
        return [f"Unknown ema_trend fields are not allowed: {unknown_fields}"]
    return []


def _validation_errors(exc: ValidationError) -> list[str]:
    return [
        f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
        for error in exc.errors()
    ]


def _diff_strategy(current: dict[str, Any], draft: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not draft:
        return []
    current_ema = current.get("ema_trend", {})
    draft_ema = draft.get("ema_trend", {})
    diff: list[dict[str, Any]] = []
    for field in sorted(ALLOWED_EMA_TREND_FIELDS):
        old = current_ema.get(field)
        new = draft_ema.get(field)
        if old != new:
            diff.append({"field": f"ema_trend.{field}", "old": old, "new": new})
    return diff
