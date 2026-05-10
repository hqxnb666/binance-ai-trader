from __future__ import annotations

import json
import os
import subprocess
import sys


def test_shadow_report_json_runs(tmp_path) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{tmp_path / 'shadow.db'}"
    result = subprocess.run(
        [sys.executable, "scripts/shadow_report.py", "--hours", "24", "--json"],
        capture_output=True,
        check=True,
        env=env,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "shadow_report_v1"
    assert "API_KEY" not in json.dumps(payload)


def test_evaluate_shadow_mode_save_report(tmp_path) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{tmp_path / 'shadow.db'}"
    env["SHADOW_MODE_REPORT_DIR"] = str(tmp_path / "reports")
    result = subprocess.run(
        [sys.executable, "scripts/evaluate_shadow_mode.py", "--once", "--save-report"],
        capture_output=True,
        check=True,
        env=env,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert payload["evaluated"] == 0
    assert list((tmp_path / "reports").glob("shadow-report-*.json"))
