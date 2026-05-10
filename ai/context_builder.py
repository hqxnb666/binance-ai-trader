from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from config.settings import Settings
from journal.models import StrategyPlanRecord

SENSITIVE_MARKERS = ("API_KEY", "SECRET", "TOKEN", "PASSWORD", "PRIVATE")
RAW_PAYLOAD_MARKERS = ("RAW_PROMPT", "RAW_RESPONSE", "FULL_PROMPT", "FULL_RESPONSE")
AUDIT_RECENT_SIGNAL_LIMIT = 10
AUDIT_RECENT_RISK_LIMIT = 10
AUDIT_RECENT_ORDER_LIMIT = 10
AUDIT_RECENT_TRADE_REVIEW_LIMIT = 5


def build_strategy_context(
    settings: Settings,
    symbols: list[str],
    market_snapshots: dict[str, dict[str, Any]],
    active_strategy_plan: StrategyPlanRecord | dict[str, Any] | None,
    recent_summary: dict[str, Any] | None = None,
    *,
    account_state: dict[str, Any] | None = None,
    positions: list[dict[str, Any]] | None = None,
    budget_status: dict[str, Any] | None = None,
    data_quality_summary: dict[str, Any] | None = None,
    kill_switch_state: dict[str, Any] | None = None,
    active_cooldowns: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    recent = recent_summary or {}
    context = {
        "schema_version": "strategy_context_v2",
        "created_at": datetime.now().astimezone().isoformat(),
        "run_mode": {
            "trading_mode": settings.trading_mode,
            "dry_run": settings.trading_dry_run,
            "order_execution_enabled": settings.order_execution_enabled,
            "live_enabled": settings.live_trading_enabled and settings.live_trading.enabled,
        },
        "symbols": [symbol.upper() for symbol in symbols],
        "planning_mode": None,
        "account_state": account_state or _unknown_account_state(),
        "positions": positions if positions is not None else [_unknown_position()],
        "market_context": {
            "latest_snapshots": _truncate_mapping(market_snapshots, max_items=10),
            "indicator_summary": _indicator_summary(market_snapshots),
            "trend_summary": _trend_summary(market_snapshots),
            "volatility_summary": _volatility_summary(market_snapshots),
        },
        "active_strategy_plan": summarize_strategy_plan(active_strategy_plan),
        "recent_signal_reviews": _truncate_list(
            recent.get("signal_reviews", []),
            settings.ai_context_recent_signal_reviews_limit,
        ),
        "recent_risk_decisions": _truncate_list(
            recent.get("risk_decisions", []),
            settings.ai_context_recent_risk_decisions_limit,
        ),
        "recent_orders": _truncate_list(
            recent.get("orders", []),
            settings.ai_context_recent_orders_limit,
        ),
        "recent_trade_reviews": _truncate_list(
            recent.get("trade_reviews", []),
            settings.ai_context_recent_trade_reviews_limit,
        ),
        "data_quality_summary": data_quality_summary
        or recent.get("data_quality_summary")
        or {"status": "unknown"},
        "budget_status": budget_status or recent.get("budget_status") or {"status": "unknown"},
        "kill_switch_state": kill_switch_state or {"status": "unknown"},
        "active_cooldowns": _truncate_list(active_cooldowns or [], 20),
        "truncated": False,
    }
    return _finalize_context(settings, context)


def build_signal_review_context(
    current_snapshot: dict[str, Any],
    candidate_signal: dict[str, Any] | None,
    active_strategy_plan: StrategyPlanRecord | dict[str, Any] | None,
    position_state: dict[str, Any] | None = None,
    risk_state: dict[str, Any] | None = None,
    *,
    settings: Settings | None = None,
    account_state_summary: dict[str, Any] | None = None,
    recent_rejections_summary: dict[str, Any] | None = None,
    data_quality_flags: list[str] | None = None,
    budget_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context = {
        "schema_version": "signal_review_context_v2",
        "current_market_snapshot": current_snapshot,
        "market_snapshot": current_snapshot,
        "candidate_signal": candidate_signal,
        "active_strategy_plan": summarize_strategy_plan(active_strategy_plan),
        "account_state_summary": account_state_summary or {"status": "unknown"},
        "position_state": position_state or {"status": "unknown"},
        "risk_state": risk_state or {"status": "unknown"},
        "recent_rejections_summary": recent_rejections_summary or {"status": "unknown"},
        "data_quality_flags": data_quality_flags or [],
        "budget_status": budget_status or {"status": "unknown"},
    }
    payload = {**current_snapshot, "signal_review_context": context, "truncated": False}
    return _finalize_context(settings, payload) if settings else _sanitize_json(payload)


def build_trade_review_context(
    *,
    settings: Settings,
    order_summary: dict[str, Any],
    fills_summary: list[dict[str, Any]],
    strategy_plan_at_entry: dict[str, Any] | None = None,
    signal_review_at_entry: dict[str, Any] | None = None,
    risk_decision_at_entry: dict[str, Any] | None = None,
    market_before_entry: dict[str, Any] | None = None,
    market_after_entry: dict[str, Any] | None = None,
    pnl_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _finalize_context(
        settings,
        {
            "schema_version": "trade_review_context_v1",
            "order_summary": order_summary,
            "fills_summary": _truncate_list(fills_summary, 50),
            "strategy_plan_at_entry": strategy_plan_at_entry,
            "signal_review_at_entry": signal_review_at_entry,
            "risk_decision_at_entry": risk_decision_at_entry,
            "market_before_entry": market_before_entry,
            "market_after_entry": market_after_entry,
            "pnl_summary": pnl_summary or {"status": "unknown"},
            "truncated": False,
        },
    )


def build_daily_report_context(
    *,
    settings: Settings,
    daily_signal_counts: dict[str, Any],
    ai_review_counts: dict[str, Any],
    risk_rejection_counts: dict[str, Any],
    order_lifecycle_summary: dict[str, Any],
    openai_usage_summary: dict[str, Any],
    data_quality_incidents: list[dict[str, Any]],
    active_strategy_plans: list[dict[str, Any]],
    known_warnings: list[str],
) -> dict[str, Any]:
    return _finalize_context(
        settings,
        {
            "schema_version": "daily_report_context_v1",
            "daily_signal_counts": daily_signal_counts,
            "ai_review_counts": ai_review_counts,
            "risk_rejection_counts": risk_rejection_counts,
            "order_lifecycle_summary": order_lifecycle_summary,
            "openai_usage_summary": openai_usage_summary,
            "data_quality_incidents": _truncate_list(data_quality_incidents, 50),
            "active_strategy_plans": _truncate_list(active_strategy_plans, 20),
            "known_warnings": _truncate_list(known_warnings, 50),
            "truncated": False,
        },
    )


def build_audit_context(
    *,
    settings: Settings,
    runtime_health: dict[str, Any] | None,
    budget_status: dict[str, Any] | None,
    active_strategy_plan: StrategyPlanRecord | dict[str, Any] | None = None,
    recent_strategy_plans: list[dict[str, Any]] | None = None,
    recent_signal_reviews: list[dict[str, Any]] | None = None,
    recent_risk_decisions: list[dict[str, Any]] | None = None,
    recent_orders: list[dict[str, Any]] | None = None,
    recent_trade_reviews: list[dict[str, Any]] | None = None,
    openai_usage_summary: dict[str, Any] | None = None,
    data_quality_summary: dict[str, Any] | None = None,
    latest_data_quality_snapshot: dict[str, Any] | None = None,
    account_position_snapshot: dict[str, Any] | None = None,
    kill_switch_state: dict[str, Any] | None = None,
    risk_engine_runtime_state: dict[str, Any] | None = None,
    shadow_summary: dict[str, Any] | None = None,
    account_state: dict[str, Any] | None = None,
    position_state: dict[str, Any] | None = None,
    diagnostics_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    health = runtime_health or {}
    return _finalize_context(
        settings,
        {
            "schema_version": "audit_context_v1",
            "created_at": datetime.now().astimezone().isoformat(),
            "run_mode": {
                "trading_mode": settings.trading_mode,
                "dry_run": settings.trading_dry_run,
                "order_execution_enabled": settings.order_execution_enabled,
                "live_enabled": settings.live_trading_enabled and settings.live_trading.enabled,
            },
            "runtime_health": {
                "state": health.get("state", "unknown"),
                "market_stream_connected": health.get("market_stream_connected", "unknown"),
                "user_stream_connected": health.get("user_stream_connected", "unknown"),
                "data_delay_seconds": health.get("data_delay_seconds", "unknown"),
                "last_error": health.get("last_error"),
                "reconnecting": health.get("reconnecting", "unknown"),
            },
            "budget_status": budget_status or health.get("budget_status") or {"status": "unknown"},
            "active_strategy_plan": summarize_strategy_plan(active_strategy_plan),
            "recent_strategy_plans": _truncate_list(
                recent_strategy_plans or [], AUDIT_RECENT_SIGNAL_LIMIT
            ),
            "recent_signal_reviews": _truncate_list(
                recent_signal_reviews or [],
                min(settings.ai_context_recent_signal_reviews_limit, AUDIT_RECENT_SIGNAL_LIMIT),
            ),
            "recent_risk_decisions": _truncate_list(
                recent_risk_decisions or [],
                min(settings.ai_context_recent_risk_decisions_limit, AUDIT_RECENT_RISK_LIMIT),
            ),
            "recent_orders": _truncate_list(
                recent_orders or [],
                min(settings.ai_context_recent_orders_limit, AUDIT_RECENT_ORDER_LIMIT),
            ),
            "recent_trade_reviews": _truncate_list(
                recent_trade_reviews or [],
                min(
                    settings.ai_context_recent_trade_reviews_limit,
                    AUDIT_RECENT_TRADE_REVIEW_LIMIT,
                ),
            ),
            "openai_usage_summary": _compact_openai_usage_summary(openai_usage_summary),
            "data_quality_summary": data_quality_summary or {"status": "unknown"},
            "latest_data_quality_snapshot": _compact_data_quality_snapshot(
                latest_data_quality_snapshot
            ),
            "account_position_snapshot": _compact_account_position_snapshot(
                account_position_snapshot
            ),
            "account_state": account_state or _unknown_account_state(),
            "position_state": position_state or _unknown_position(),
            "kill_switch_state": kill_switch_state or {"status": "unknown"},
            "risk_engine_runtime_state": risk_engine_runtime_state or {"status": "unknown"},
            "shadow_summary": _compact_shadow_summary(shadow_summary),
            "security_guardrails": {
                "live_trading_enabled": (
                    settings.live_trading_enabled and settings.live_trading.enabled
                ),
                "order_execution_enabled": settings.order_execution_enabled,
                "dry_run": settings.trading_dry_run,
                "ai_can_place_order_directly": settings.ai_can_place_order_directly,
                "auditor_auto_fix_allowed": False,
                "auditor_can_call_codex": False,
                "auditor_can_modify_config": False,
                "auditor_can_modify_strategy": False,
                "auditor_can_place_order": False,
            },
            "diagnostics_summary": _compact_diagnostics_summary(diagnostics_summary),
            "truncated": False,
        },
    )


def summarize_strategy_plan(
    plan: StrategyPlanRecord | dict[str, Any] | None,
) -> dict[str, Any] | None:
    if plan is None:
        return None
    if isinstance(plan, dict):
        raw = plan
        action = raw.get("plan_action")
        no_trade_update = action in {"NO_TRADE", "EXPIRE"}
        return _sanitize_json(
            {
                "id": raw.get("id"),
                "status": raw.get("status"),
                "plan_action": action,
                "risk_mode": raw.get("risk_mode") or ("no_trade" if no_trade_update else None),
                "trade_bias": raw.get("trade_bias") or ("no_trade" if no_trade_update else None),
                "symbol_permissions": _permission_rules_to_dict(
                    raw.get("symbol_permissions") or raw.get("symbol_permissions_json", {})
                ),
                "allowed_actions": raw.get("allowed_actions")
                or raw.get("allowed_actions_json", []),
                "blocked_actions": raw.get("blocked_actions")
                or raw.get("blocked_actions_json", []),
                "max_position_pct": raw.get("max_position_pct"),
                "confidence": raw.get("confidence"),
                "requires_human_review": raw.get("requires_human_review"),
            }
        )
    no_trade_update = plan.plan_action in {"NO_TRADE", "EXPIRE"}
    return _sanitize_json(
        {
            "id": plan.id,
            "status": plan.status,
            "plan_action": plan.plan_action,
            "risk_mode": plan.risk_mode or ("no_trade" if no_trade_update else None),
            "trade_bias": plan.trade_bias or ("no_trade" if no_trade_update else None),
            "symbol_permissions": plan.symbol_permissions_json,
            "allowed_actions": plan.allowed_actions_json,
            "blocked_actions": plan.blocked_actions_json,
            "max_position_pct": float(plan.max_position_pct or 0),
            "confidence": float(plan.confidence),
            "requires_human_review": plan.requires_human_review,
        }
    )


def _unknown_account_state() -> dict[str, Any]:
    return {
        "status": "unknown",
        "source": "not_synced",
        "equity_usdt": "unknown",
        "available_usdt": "unknown",
        "daily_realized_pnl": "unknown",
        "daily_unrealized_pnl": "unknown",
        "daily_loss_remaining": "unknown",
    }


def _unknown_position() -> dict[str, Any]:
    return {
        "status": "unknown",
        "source": "not_synced",
        "symbol": "unknown",
        "side": "unknown",
        "quantity": "unknown",
        "entry_price": "unknown",
        "unrealized_pnl": "unknown",
        "position_pct": "unknown",
    }


def _indicator_summary(market_snapshots: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        symbol: {
            "rsi14_5m": snapshot.get("rsi14_5m"),
            "atr14_5m": snapshot.get("atr14_5m"),
            "volume_ratio_5m": snapshot.get("volume_ratio_5m"),
        }
        for symbol, snapshot in market_snapshots.items()
    }


def _trend_summary(market_snapshots: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        symbol: {
            "trend_1h": snapshot.get("trend_1h"),
            "ema_fast_5m": snapshot.get("ema_fast_5m"),
            "ema_slow_5m": snapshot.get("ema_slow_5m"),
            "ema_fast_1h": snapshot.get("ema_fast_1h"),
            "ema_slow_1h": snapshot.get("ema_slow_1h"),
        }
        for symbol, snapshot in market_snapshots.items()
    }


def _volatility_summary(market_snapshots: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        symbol: {
            "atr14_5m": snapshot.get("atr14_5m"),
            "data_delay_seconds": snapshot.get("data_delay_seconds"),
            "ws_health": snapshot.get("ws_health"),
        }
        for symbol, snapshot in market_snapshots.items()
    }


def _finalize_context(settings: Settings | None, context: dict[str, Any]) -> dict[str, Any]:
    sanitized = _sanitize_json(context)
    if settings is None:
        return sanitized
    max_chars = max(settings.ai_context_max_json_chars, 1000)
    rendered = json.dumps(sanitized, default=str, ensure_ascii=False, separators=(",", ":"))
    if len(rendered) <= max_chars:
        return sanitized
    compressed = _compress_context(sanitized)
    compressed["truncated"] = True
    compressed["truncation_reason"] = f"context exceeded {max_chars} JSON chars"
    rendered = json.dumps(compressed, default=str, ensure_ascii=False, separators=(",", ":"))
    if len(rendered) <= max_chars:
        return compressed
    return {
        "schema_version": sanitized.get("schema_version", "context"),
        "truncated": True,
        "truncation_reason": f"context exceeded {max_chars} JSON chars after compression",
        "run_mode": sanitized.get("run_mode"),
        "active_strategy_plan": sanitized.get("active_strategy_plan"),
        "budget_status": sanitized.get("budget_status"),
        "data_quality_summary": sanitized.get("data_quality_summary"),
    }


def _compress_context(value: Any) -> Any:
    if isinstance(value, dict):
        compressed: dict[str, Any] = {}
        for key, item in value.items():
            if key.startswith("recent_") and isinstance(item, list):
                compressed[key] = item[-3:]
            elif key in {"latest_snapshots", "current_market_snapshot"}:
                compressed[key] = _shallow_snapshot(item)
            else:
                compressed[key] = _compress_context(item)
        return compressed
    if isinstance(value, list):
        return [_compress_context(item) for item in value[-10:]]
    return value


def _shallow_snapshot(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: item
            for key, item in value.items()
            if key
            in {
                "symbol",
                "price",
                "trend_1h",
                "rsi14_5m",
                "atr14_5m",
                "volume_ratio_5m",
                "ws_health",
                "data_delay_seconds",
            }
        }
    return value


def _sanitize_json(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            key_upper = str(key).upper()
            if any(marker in key_upper for marker in SENSITIVE_MARKERS + RAW_PAYLOAD_MARKERS):
                sanitized[str(key)] = "[REDACTED]"
            else:
                sanitized[str(key)] = _sanitize_json(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_json(item) for item in value]
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, tuple | set):
        return [_sanitize_json(item) for item in value]
    if isinstance(value, str) and len(value) > 1000:
        return value[:988].rstrip() + " [truncated]"
    return value


def _truncate_list(items: list[Any], limit: int) -> list[Any]:
    return [_sanitize_json(item) for item in items[-max(limit, 0) :]]


def _truncate_mapping(items: dict[str, Any], max_items: int) -> dict[str, Any]:
    return {
        str(key): _sanitize_json(value)
        for key, value in list(items.items())[-max(max_items, 0) :]
    }


def _permission_rules_to_dict(value: Any) -> dict[str, str]:
    if isinstance(value, dict):
        return {str(symbol).upper(): str(permission) for symbol, permission in value.items()}
    if isinstance(value, list):
        result: dict[str, str] = {}
        for item in value:
            if not isinstance(item, dict):
                continue
            symbol = item.get("symbol")
            permission = item.get("permission")
            if symbol and permission:
                result[str(symbol).upper()] = str(permission)
        return result
    return {}


def _compact_openai_usage_summary(summary: dict[str, Any] | None) -> dict[str, Any]:
    if not summary:
        return {"status": "unknown"}
    return _sanitize_json(
        {
            "days": summary.get("days"),
            "total_calls": summary.get("total_calls"),
            "estimated_cost_usd": summary.get("estimated_cost_usd"),
            "by_role": summary.get("by_role", {}),
            "by_model": summary.get("by_model", {}),
        }
    )


def _compact_diagnostics_summary(summary: dict[str, Any] | None) -> dict[str, Any]:
    if not summary:
        return {"status": "unknown"}
    compact: dict[str, Any] = {}
    for key, value in summary.items():
        if isinstance(value, dict):
            compact[str(key)] = {
                str(inner_key): _sanitize_json(inner_value)
                for inner_key, inner_value in value.items()
                if str(inner_key)
                in {
                    "status",
                    "state",
                    "latency_ms",
                    "proxy_env_present",
                    "last_diagnostics_at",
                    "can_run_testnet_smoke",
                    "can_run_with_ai",
                    "can_place_testnet_order_if_enabled",
                }
                or str(inner_key).endswith("_status")
            }
        elif str(key) in {"status", "state", "last_diagnostics_at", "proxy_env_present"}:
            compact[str(key)] = _sanitize_json(value)
    return compact or {"status": "unknown"}


def _compact_data_quality_snapshot(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    if not snapshot:
        return {"status": "unknown"}
    issues = snapshot.get("issues", [])
    compact_issues = []
    if isinstance(issues, list):
        for issue in issues[:10]:
            if not isinstance(issue, dict):
                continue
            compact_issues.append(
                {
                    "severity": issue.get("severity"),
                    "category": issue.get("category"),
                    "title": issue.get("title"),
                    "blocks_signal_review": issue.get("blocks_signal_review"),
                    "blocks_order": issue.get("blocks_order"),
                }
            )
    return _sanitize_json(
        {
            "schema_version": snapshot.get("schema_version"),
            "created_at": snapshot.get("created_at"),
            "overall_status": snapshot.get("overall_status"),
            "action": snapshot.get("action"),
            "safe_for_strategy_planner": snapshot.get("safe_for_strategy_planner"),
            "safe_for_signal_review": snapshot.get("safe_for_signal_review"),
            "safe_for_order": snapshot.get("safe_for_order"),
            "safe_for_real_testnet_order": snapshot.get("safe_for_real_testnet_order"),
            "reason_codes": snapshot.get("reason_codes", [])[:20],
            "issues": compact_issues,
        }
    )


def _compact_account_position_snapshot(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    if not snapshot:
        return {"status": "unknown"}
    account = snapshot.get("account", {}) if isinstance(snapshot.get("account"), dict) else {}
    positions = snapshot.get("positions", [])
    compact_positions = []
    if isinstance(positions, list):
        for position in positions[:10]:
            if not isinstance(position, dict):
                continue
            compact_positions.append(
                {
                    "symbol": position.get("symbol"),
                    "status": position.get("status"),
                    "source": position.get("source"),
                    "side": position.get("side"),
                    "position_pct": position.get("position_pct"),
                    "is_safe_for_real_order": position.get("is_safe_for_real_order"),
                }
            )
    return _sanitize_json(
        {
            "schema_version": snapshot.get("schema_version"),
            "created_at": snapshot.get("created_at"),
            "source": snapshot.get("source"),
            "safe_for_real_order": snapshot.get("safe_for_real_order"),
            "reason_codes": snapshot.get("reason_codes", [])[:20],
            "account": {
                "status": account.get("status"),
                "source": account.get("source"),
                "equity_usdt": account.get("equity_usdt"),
                "available_usdt": account.get("available_usdt"),
                "is_safe_for_real_order": account.get("is_safe_for_real_order"),
            },
            "positions": compact_positions,
        }
    )


def _compact_shadow_summary(summary: dict[str, Any] | None) -> dict[str, Any]:
    if not summary:
        return {"status": "unknown"}
    return _sanitize_json(
        {
            "total_decisions": summary.get("total_decisions"),
            "would_place_order_count": summary.get("would_place_order_count"),
            "risk_rejected_count": summary.get("risk_rejected_count"),
            "ai_rejected_count": summary.get("ai_rejected_count"),
            "data_quality_blocked_count": summary.get("data_quality_blocked_count"),
            "simulated_total_pnl_usdt": summary.get("simulated_total_pnl_usdt"),
            "simulated_win_rate": summary.get("simulated_win_rate"),
            "top_rejection_reasons": _truncate_list(
                list(summary.get("top_rejection_reasons", [])),
                10,
            ),
        }
    )
