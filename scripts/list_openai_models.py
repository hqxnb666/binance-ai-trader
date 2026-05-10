from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.settings import get_settings  # noqa: E402
from diagnostics.network import safe_details  # noqa: E402

REPORT_DIR = ROOT / "reports" / "diagnostics"


def list_openai_models(*, show_all: bool = False) -> dict[str, object]:
    settings = get_settings()
    if settings.openai_api_key is None:
        return {"status": "MISSING_KEY", "details": "OPENAI_API_KEY missing", "models": []}
    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key.get_secret_value())
        response = client.models.list()
        model_ids = sorted(item.id for item in response.data)
        if not show_all:
            model_ids = [
                model
                for model in model_ids
                if any(token in model for token in ("gpt-5", "gpt-5.4", "gpt-5.5", "mini", "nano"))
            ]
        return {
            "status": "OK",
            "created_at": datetime.now(UTC).isoformat(),
            "models": model_ids,
            "count": len(model_ids),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "API_ERROR",
            "details": safe_details(str(exc)),
            "models": [],
        }


def save_report(report: dict[str, object]) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"openai-models-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="Show all models.")
    parser.add_argument("--save-report", action="store_true")
    args = parser.parse_args()
    report = list_openai_models(show_all=args.all)
    if args.save_report:
        report["report_path"] = str(save_report(report))
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] != "API_ERROR" else 1


if __name__ == "__main__":
    raise SystemExit(main())

