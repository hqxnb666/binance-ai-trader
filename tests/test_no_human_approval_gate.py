from __future__ import annotations

from pathlib import Path


def test_no_human_approval_gate_was_added() -> None:
    root = Path(__file__).resolve().parents[1]
    paths = [path for path in root.rglob("*.py") if ".venv" not in path.parts]
    rendered = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    assert ("class " + "HumanApprovalGate") not in rendered
    assert ("PendingOrder" + "Intent") not in rendered
    assert ("approve_order" + "_intent") not in rendered
    assert not (root / "approval").exists()
