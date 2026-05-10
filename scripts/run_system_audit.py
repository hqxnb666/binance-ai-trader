from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ai.audit_schemas import TradingIssueReport  # noqa: E402
from config.settings import get_settings  # noqa: E402
from journal.audit_store import (  # noqa: E402
    get_latest_trading_issue_report,
    save_audit_report_file,
)
from journal.database import SessionLocal, init_db, session_scope  # noqa: E402
from runtime.task_manager import RuntimeTaskManager  # noqa: E402


async def run_audit(*, lookback_hours: int, deep: bool, save_report: bool) -> dict[str, object]:
    settings = get_settings()
    if deep and not settings.enable_deep_auditor:
        return {
            "status": "DEEP_AUDITOR_DISABLED",
            "error": "ENABLE_DEEP_AUDITOR=false; refusing --deep audit.",
        }
    init_db()
    manager = RuntimeTaskManager(settings=settings, session_factory=SessionLocal)
    result = await manager.run_system_audit(lookback_hours=lookback_hours, deep=deep)
    if save_report and "report" in result:
        report = TradingIssueReport.model_validate(result["report"])
        path = save_audit_report_file(report)
        result["report_path"] = str(path)
        with session_scope() as session:
            latest = get_latest_trading_issue_report(session)
            if latest is not None:
                latest.report_path = str(path)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lookback-hours", type=int, default=6)
    parser.add_argument("--deep", action="store_true")
    parser.add_argument("--json", action="store_true", dest="json_output")
    parser.add_argument("--save-report", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = asyncio.run(
        run_audit(
            lookback_hours=max(args.lookback_hours, 1),
            deep=args.deep,
            save_report=args.save_report,
        )
    )
    if args.json_output or args.save_report:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    else:
        report = result.get("report", {})
        print(f"status={result.get('overall_status') or report.get('overall_status')}")
        print(f"highest_severity={result.get('highest_severity')}")
        print(f"issue_count={result.get('issue_count')}")
        print(f"summary={result.get('summary')}")
    return 1 if result.get("status") == "DEEP_AUDITOR_DISABLED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
