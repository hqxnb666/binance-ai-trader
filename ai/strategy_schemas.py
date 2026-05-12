from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

FORBIDDEN_ORDER_FIELDS = {
    "broker",
    "client_order_id",
    "execute_order",
    "new_order",
    "order",
    "order_id",
    "order_side",
    "order_type",
    "place_order",
    "price",
    "quantity",
    "stop_loss",
    "stop_price",
    "take_profit",
}
FORBIDDEN_ORDER_TEXT_TERMS = FORBIDDEN_ORDER_FIELDS - {"order"}
REQUIRED_BLOCKED_ACTIONS = {"MARTINGALE", "LEVERAGE", "SHORT"}


class StrategyPlanningMode(StrEnum):
    FULL_REPLAN = "FULL_REPLAN"
    REFRESH = "REFRESH"
    INCIDENT_REVIEW = "INCIDENT_REVIEW"
    CLOSE_OF_DAY_REVIEW = "CLOSE_OF_DAY_REVIEW"


class StrategyPlanAction(StrEnum):
    CREATE = "CREATE"
    KEEP = "KEEP"
    ADJUST = "ADJUST"
    EXPIRE = "EXPIRE"
    NO_TRADE = "NO_TRADE"


class MarketRegime(StrEnum):
    TREND_UP = "trend_up"
    TREND_DOWN = "trend_down"
    RANGE = "range"
    HIGH_VOLATILITY = "high_volatility"
    UNCERTAIN = "uncertain"


class TradeBias(StrEnum):
    LONG_ONLY = "long_only"
    SHORT_ONLY = "short_only"
    NEUTRAL = "neutral"
    NO_TRADE = "no_trade"


class RiskMode(StrEnum):
    CONSERVATIVE = "conservative"
    NORMAL = "normal"
    REDUCED_RISK = "reduced_risk"
    NO_TRADE = "no_trade"


class SymbolPermission(StrEnum):
    ALLOW = "allow"
    OBSERVE_ONLY = "observe_only"
    BLOCKED = "blocked"


class EntryQuality(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class SymbolPermissionRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    permission: SymbolPermission
    reason: str | None = Field(...)

    @field_validator("symbol")
    @classmethod
    def uppercase_symbol(cls, value: str) -> str:
        return value.upper()

    @field_validator("permission", mode="before")
    @classmethod
    def normalize_permission(cls, value: object) -> object:
        if isinstance(value, str) and value.strip().lower() == "observe":
            return "observe_only"
        return value


class StrategyPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["strategy_plan_v1"]
    plan_action: Literal["CREATE"]
    planning_mode: Literal["FULL_REPLAN"]
    symbol_scope: list[str]
    market_regime: MarketRegime
    trade_bias: TradeBias
    allowed_actions: list[str]
    blocked_actions: list[str]
    risk_mode: RiskMode
    max_position_pct: float = Field(ge=0, le=5)
    symbol_permissions: list[SymbolPermissionRule]
    entry_quality_required: EntryQuality
    invalidation_conditions: list[str]
    expires_at: datetime
    confidence: float = Field(ge=0, le=1)
    requires_human_review: bool
    reason_codes: list[str]
    explanation: str

    @field_validator("symbol_scope")
    @classmethod
    def symbols_upper(cls, value: list[str]) -> list[str]:
        return [item.upper() for item in value]

    @field_validator("allowed_actions", "blocked_actions", mode="before")
    @classmethod
    def normalize_action_terms(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        normalized: list[object] = []
        for item in value:
            if isinstance(item, str):
                lowered = item.strip().lower()
                if lowered == "hold_only":
                    normalized.append("HOLD")
                    continue
            normalized.append(item)
        return normalized

    @model_validator(mode="after")
    def validate_plan(self) -> StrategyPlan:
        _validate_no_order_fields(self.model_dump(mode="json"))
        _validate_blocked_actions(self.blocked_actions)
        _validate_confidence(self.confidence, self.requires_human_review)
        _validate_no_trade_actions(self.risk_mode, self.allowed_actions)
        _validate_uncertain_bias(self.market_regime, self.trade_bias)
        _validate_expiration(self.expires_at)
        return self


class StrategyPlanChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    old_value: str | None = Field(...)
    new_value: str | None = Field(...)
    reason: str


class StrategyPlanUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["strategy_plan_update_v1"]
    plan_action: Literal["KEEP", "ADJUST", "EXPIRE", "NO_TRADE"]
    planning_mode: Literal["REFRESH", "INCIDENT_REVIEW", "CLOSE_OF_DAY_REVIEW"]
    previous_plan_id: str | None = Field(...)
    is_previous_plan_still_valid: bool
    changes: list[StrategyPlanChange]
    new_expiration_time: datetime | None = Field(...)
    confidence: float = Field(ge=0, le=1)
    requires_human_review: bool
    reason_codes: list[str]
    explanation: str

    @model_validator(mode="after")
    def validate_update(self) -> StrategyPlanUpdate:
        _validate_no_order_fields(self.model_dump(mode="json"))
        _validate_confidence(self.confidence, self.requires_human_review)
        if self.new_expiration_time is not None:
            _validate_expiration(self.new_expiration_time)
        return self


def _validate_no_order_fields(payload: dict[str, object]) -> None:
    _validate_no_order_fields_recursive(payload)


def _validate_no_order_fields_recursive(payload: object) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_name = str(key).lower()
            if key_name in FORBIDDEN_ORDER_FIELDS:
                msg = f"Strategy plan must not contain order field: {key_name}"
                raise ValueError(msg)
            _validate_no_order_fields_recursive(value)
        return
    if isinstance(payload, list):
        for item in payload:
            _validate_no_order_fields_recursive(item)
        return
    if isinstance(payload, str):
        rendered = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).lower()
        for field_name in FORBIDDEN_ORDER_TEXT_TERMS:
            if field_name in rendered:
                msg = f"Strategy plan must not contain order field: {field_name}"
                raise ValueError(msg)


def _validate_blocked_actions(blocked_actions: list[str]) -> None:
    blocked = {item.upper() for item in blocked_actions}
    missing = REQUIRED_BLOCKED_ACTIONS - blocked
    if missing:
        msg = f"blocked_actions missing required actions: {sorted(missing)}"
        raise ValueError(msg)


def _validate_confidence(confidence: float, requires_human_review: bool) -> None:
    if confidence < 0.6 and not requires_human_review:
        msg = "confidence < 0.6 requires human review"
        raise ValueError(msg)


def _validate_no_trade_actions(risk_mode: RiskMode, allowed_actions: list[str]) -> None:
    if risk_mode == RiskMode.NO_TRADE:
        allowed = {item.upper() for item in allowed_actions}
        if allowed - {"HOLD"}:
            msg = "risk_mode=no_trade allows only HOLD or an empty allowed_actions list"
            raise ValueError(msg)


def _validate_uncertain_bias(market_regime: MarketRegime, trade_bias: TradeBias) -> None:
    if market_regime == MarketRegime.UNCERTAIN and trade_bias not in {
        TradeBias.NEUTRAL,
        TradeBias.NO_TRADE,
    }:
        msg = "uncertain market regime requires neutral or no_trade bias"
        raise ValueError(msg)


def _validate_expiration(expires_at: datetime) -> None:
    expires = expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if expires <= datetime.now(UTC):
        msg = "expires_at must be in the future"
        raise ValueError(msg)
