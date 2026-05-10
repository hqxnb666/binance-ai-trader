from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from config.settings import BASE_DIR, Settings
from data_quality.schemas import DataQualitySnapshot


def data_quality_report_dir(settings: Settings) -> Path:
    path = Path(settings.data_quality_report_dir)
    if not path.is_absolute():
        path = BASE_DIR / path
    return path


def save_data_quality_report(snapshot: DataQualitySnapshot, settings: Settings) -> Path:
    path = data_quality_report_dir(settings)
    path.mkdir(parents=True, exist_ok=True)
    report_path = path / f"data-quality-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    report_path.write_text(
        json.dumps(snapshot.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return report_path


def latest_data_quality_report(settings: Settings) -> dict[str, Any] | None:
    path = data_quality_report_dir(settings)
    if not path.exists():
        return None
    candidates = sorted(path.glob("data-quality-*.json"), key=lambda item: item.stat().st_mtime)
    if not candidates:
        return None
    return json.loads(candidates[-1].read_text(encoding="utf-8"))


def summarize_data_quality_report(report: dict[str, Any] | None) -> dict[str, Any]:
    if not report:
        return {
            "overall_status": "UNKNOWN",
            "safe_for_signal_review": None,
            "safe_for_order": None,
            "issue_count": 0,
            "latest_created_at": None,
        }
    return {
        "overall_status": report.get("overall_status", "UNKNOWN"),
        "safe_for_signal_review": report.get("safe_for_signal_review"),
        "safe_for_order": report.get("safe_for_order"),
        "issue_count": len(report.get("issues", [])),
        "latest_created_at": report.get("created_at"),
    }
