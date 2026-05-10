from __future__ import annotations

from typing import Any


class DailyReporter:
    def summarize(self, metrics: dict[str, Any]) -> dict[str, Any]:
        return {
            "ai_summary": "Daily reporter MVP summary. Review manually before changing strategy.",
            "improvement_candidates": metrics.get("improvement_candidates", []),
        }

