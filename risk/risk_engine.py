from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from ai.schemas import SignalReview, signal_review_trade_gate
from binance_client.exchange_info import SymbolFilters
from config.settings import RiskConfig, Settings
from risk.order_filter_validator import OrderFilterValidator
from strategies.base import StrategySignalPayload


class AccountState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    equity_usdt: Decimal
    daily_loss_pct: float = 0
    consecutive_losses: int = 0
    total_position_pct: float = 0


class PositionState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    quantity: Decimal = Decimal("0")
    position_pct: float = 0
    side: Literal["LONG", "FLAT"] = "FLAT"
    last_loss_at: datetime | None = None


class MarketHealth(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ws_connected: bool = True
    market_stream_connected: bool = True
    user_stream_connected: bool = True
    data_delay_seconds: float = 0
    account_stream_ok: bool = True
    reconnecting: bool = False
    last_error: str | None = None


class RiskDecisionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    approved: bool
    reason: str
    risk_state_json: dict[str, Any]


@dataclass
class RiskEngine:
    settings: Settings
    order_timestamps: list[datetime] = field(default_factory=list)
    seen_client_order_ids: set[str] = field(default_factory=set)

    def evaluate(
        self,
        *,
        signal: StrategySignalPayload,
        ai_review: SignalReview | None,
        ai_schema_valid: bool,
        account: AccountState,
        position: PositionState,
        market_health: MarketHealth,
        symbol_filters: SymbolFilters,
        order_price: Decimal,
        order_quantity: Decimal,
        trading_mode: Literal["testnet", "live"],
        client_order_id: str | None = None,
    ) -> RiskDecisionPayload:
        risk = self.settings.risk_config
        checks = {
            "trading_mode": trading_mode,
            "signal_side": signal.side,
            "ai_schema_valid": ai_schema_valid,
            "market_health": market_health.model_dump(mode="json"),
            "account": account.model_dump(mode="json"),
            "position": position.model_dump(mode="json"),
        }
        rejection = self._first_rejection(
            risk=risk,
            signal=signal,
            ai_review=ai_review,
            ai_schema_valid=ai_schema_valid,
            account=account,
            position=position,
            market_health=market_health,
            symbol_filters=symbol_filters,
            order_price=order_price,
            order_quantity=order_quantity,
            trading_mode=trading_mode,
            client_order_id=client_order_id,
        )
        if rejection:
            return RiskDecisionPayload(
                symbol=signal.symbol,
                approved=False,
                reason=rejection,
                risk_state_json=checks,
            )
        if client_order_id:
            self.seen_client_order_ids.add(client_order_id)
        self.order_timestamps.append(datetime.now(UTC))
        return RiskDecisionPayload(
            symbol=signal.symbol,
            approved=True,
            reason="approved",
            risk_state_json=checks,
        )

    def _first_rejection(
        self,
        *,
        risk: RiskConfig,
        signal: StrategySignalPayload,
        ai_review: SignalReview | None,
        ai_schema_valid: bool,
        account: AccountState,
        position: PositionState,
        market_health: MarketHealth,
        symbol_filters: SymbolFilters,
        order_price: Decimal,
        order_quantity: Decimal,
        trading_mode: Literal["testnet", "live"],
        client_order_id: str | None,
    ) -> str | None:
        if trading_mode not in {"testnet", "live"}:
            return "invalid trading mode"
        if trading_mode == "live" and (
            not self.settings.live_trading_enabled or not self.settings.live_trading.enabled
        ):
            return "live trading disabled"
        if risk.kill_switch_enabled:
            return "kill switch enabled"
        if account.daily_loss_pct <= -abs(risk.max_daily_loss_pct):
            return "daily loss limit exceeded"
        if account.consecutive_losses >= risk.max_consecutive_losses:
            return "consecutive loss limit exceeded"
        if position.position_pct >= risk.max_position_pct_per_symbol and signal.side == "BUY":
            return "symbol position limit exceeded"
        if account.total_position_pct >= risk.max_total_position_pct and signal.side == "BUY":
            return "total position limit exceeded"
        if position.last_loss_at is not None:
            cooldown_until = position.last_loss_at + timedelta(
                minutes=risk.cooldown_minutes_per_symbol
            )
            if datetime.now(UTC) < cooldown_until:
                return "symbol cooldown active"
        if risk.block_on_ws_disconnect and (
            not market_health.ws_connected
            or not market_health.market_stream_connected
            or not market_health.user_stream_connected
        ):
            return "websocket disconnected"
        if market_health.reconnecting:
            return "websocket reconnecting"
        if not market_health.account_stream_ok:
            return "account stream unhealthy"
        if market_health.data_delay_seconds > risk.block_on_data_delay_seconds:
            return "market data delay too high"
        if risk.block_on_ai_schema_error and not ai_schema_valid:
            return "AI schema invalid"
        if ai_review is None:
            return "AI review missing"
        ai_allowed, ai_reason = signal_review_trade_gate(ai_review)
        if not ai_allowed:
            return ai_reason
        if signal.side == "SELL" and position.quantity <= 0:
            return "spot short selling is forbidden"
        if signal.side == "BUY" and position.side not in {"FLAT", "LONG"}:
            return "invalid spot position state"
        if client_order_id and client_order_id in self.seen_client_order_ids:
            return "duplicate client_order_id"
        if self._orders_last_minute() >= risk.max_orders_per_minute:
            return "order frequency limit exceeded"
        validator = OrderFilterValidator(symbol_filters)
        filter_result = validator.validate_order(price=order_price, quantity=order_quantity)
        if not filter_result.valid:
            return filter_result.reason
        return None

    def _orders_last_minute(self) -> int:
        cutoff = datetime.now(UTC) - timedelta(minutes=1)
        self.order_timestamps = [item for item in self.order_timestamps if item >= cutoff]
        return len(self.order_timestamps)
