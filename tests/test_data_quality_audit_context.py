from __future__ import annotations

import json
from datetime import UTC, datetime

from ai.context_builder import build_audit_context
from config.settings import load_settings


def test_audit_context_contains_latest_data_quality_snapshot_without_secrets() -> None:
    context = build_audit_context(
        settings=load_settings(),
        runtime_health={"state": "RUNNING"},
        budget_status={"status": "ok"},
        latest_data_quality_snapshot={
            "schema_version": "data_quality_snapshot_v1",
            "created_at": datetime.now(UTC).isoformat(),
            "overall_status": "CRITICAL",
            "action": "BLOCK_ORDER",
            "safe_for_strategy_planner": False,
            "safe_for_signal_review": False,
            "safe_for_order": False,
            "safe_for_real_testnet_order": False,
            "reason_codes": ["API_KEY_SHOULD_REDACT"],
            "issues": [
                {
                    "severity": "CRITICAL",
                    "category": "MARKET_STREAM",
                    "title": "bad",
                    "raw_response": "secret",
                    "blocks_signal_review": True,
                    "blocks_order": True,
                }
            ],
        },
        account_state={"status": "unknown", "BINANCE_SECRET": "secret-value"},
    )
    rendered = json.dumps(context)
    assert "secret-value" not in rendered
    assert "raw_response" not in rendered.lower()
    assert context["latest_data_quality_snapshot"]["overall_status"] == "CRITICAL"
