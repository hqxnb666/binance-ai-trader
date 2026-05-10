from __future__ import annotations

import json
import subprocess
import sys


def test_run_system_audit_deep_disabled_refuses() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_system_audit.py",
            "--deep",
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "DEEP_AUDITOR_DISABLED"
