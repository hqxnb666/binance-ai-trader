from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.settings import get_settings  # noqa: E402
from journal.database import SessionLocal, init_db  # noqa: E402
from shadow.evaluator import ShadowModeEvaluator  # noqa: E402
from shadow.store import build_shadow_report, save_shadow_report  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--save-report", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    del args.once
    settings = get_settings()
    init_db()
    with SessionLocal() as session:
        evaluations = ShadowModeEvaluator(settings).evaluate_open_decisions(session)
        report = build_shadow_report(session, hours=24)
        session.commit()
    payload: dict[str, object] = {
        "report_type": "shadow_evaluation",
        "evaluated": len(evaluations),
        "evaluations": evaluations,
        "report": report.model_dump(mode="json"),
    }
    if args.save_report:
        payload["report_path"] = str(save_shadow_report(report, settings))
    if args.json or args.save_report:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"Evaluated {len(evaluations)} open shadow decisions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
