from __future__ import annotations

import json
import subprocess
import sys


def test_data_quality_check_json_runs_without_secrets() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/data_quality_check.py", "--json"],
        capture_output=True,
        check=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    rendered = json.dumps(payload)
    assert payload["schema_version"] == "data_quality_snapshot_v1"
    assert "API_KEY" not in rendered
    assert "SECRET" not in rendered


def test_data_quality_check_save_report(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_QUALITY_REPORT_DIR", str(tmp_path))
    result = subprocess.run(
        [sys.executable, "scripts/data_quality_check.py", "--save-report"],
        capture_output=True,
        check=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert payload["report_path"].endswith(".json")
    assert list(tmp_path.glob("data-quality-*.json"))
