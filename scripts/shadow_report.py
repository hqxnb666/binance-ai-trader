from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.settings import get_settings  # noqa: E402
from journal.database import SessionLocal, init_db  # noqa: E402
from shadow.store import (  # noqa: E402
    build_shadow_report,
    list_open_shadow_decisions,
    save_shadow_report,
    shadow_decision_to_dict,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--save-report", action="store_true")
    parser.add_argument("--open", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = get_settings()
    init_db()
    with SessionLocal() as session:
        if args.open:
            payload: dict[str, object] = {
                "report_type": "open_shadow_decisions",
                "decisions": [
                    shadow_decision_to_dict(record)
                    for record in list_open_shadow_decisions(session, limit=100)
                ],
            }
        else:
            report = build_shadow_report(session, hours=args.hours)
            payload = report.model_dump(mode="json")
            if args.save_report:
                payload["report_path"] = str(save_shadow_report(report, settings))
    if args.json or args.save_report or args.open:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(
            "Shadow decisions="
            f"{payload['total_decisions']} simulated_pnl_usdt="
            f"{payload['simulated_total_pnl_usdt']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
