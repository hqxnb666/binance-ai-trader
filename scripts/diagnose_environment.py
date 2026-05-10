from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from diagnostics.report import run_diagnostics, save_diagnostics_report  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="Print JSON only.")
    parser.add_argument("--save-report", action="store_true", help="Save JSON report.")
    parser.add_argument("--skip-openai", action="store_true", help="Skip OpenAI API check.")
    return parser.parse_args()


def _print_human(report: dict[str, object]) -> None:
    print("Environment diagnostics")
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))


def main() -> int:
    args = parse_args()
    report = asyncio.run(run_diagnostics(include_openai=not args.skip_openai))
    if args.save_report:
        path = save_diagnostics_report(report)
        report["report_path"] = str(path)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    else:
        _print_human(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

