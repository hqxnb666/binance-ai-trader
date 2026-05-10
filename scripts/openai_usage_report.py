from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from journal.database import session_scope  # noqa: E402
from journal.openai_usage_store import (  # noqa: E402
    list_recent_openai_usage,
    summarize_openai_usage,
)

REPORT_DIR = ROOT / "reports" / "diagnostics"


def build_report(*, days: int) -> dict[str, object]:
    with session_scope() as session:
        summary = summarize_openai_usage(session, days=days)
        recent = list_recent_openai_usage(session, limit=20)
        return {
            "created_at": datetime.now(UTC).isoformat(),
            "summary": summary,
            "recent": [
                {
                    "created_at": row.created_at.isoformat(),
                    "role": row.role,
                    "model": row.model,
                    "operation_name": row.operation_name,
                    "status": row.status,
                    "input_tokens": row.input_tokens,
                    "output_tokens": row.output_tokens,
                    "cached_tokens": row.cached_tokens,
                    "total_tokens": row.total_tokens,
                    "estimated_cost_usd": float(row.estimated_cost_usd or 0),
                    "latency_ms": row.latency_ms,
                    "error_type": row.error_type,
                }
                for row in recent
            ],
        }


def save_report(report: dict[str, object]) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"openai-usage-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=1)
    parser.add_argument("--json", action="store_true", dest="json_output")
    parser.add_argument("--save-report", action="store_true")
    args = parser.parse_args()

    report = build_report(days=max(args.days, 1))
    if args.save_report:
        report["report_path"] = str(save_report(report))
    if args.json_output:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        summary = report["summary"]
        print(f"OpenAI usage for last {summary['days']} day(s)")
        print(f"Total calls: {summary['total_calls']}")
        print(f"Estimated cost USD: {summary['estimated_cost_usd']:.8f}")
        print("By role:")
        for role, bucket in summary["by_role"].items():
            print(f"  {role}: {bucket['calls']} calls, ${bucket['estimated_cost_usd']:.8f}")
        print("By model:")
        for model, bucket in summary["by_model"].items():
            print(f"  {model}: {bucket['calls']} calls, ${bucket['estimated_cost_usd']:.8f}")
        if args.save_report:
            print(f"Report: {report['report_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
