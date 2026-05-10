from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from journal.database import init_db  # noqa: E402

if __name__ == "__main__":
    init_db()
    print("Database initialized.")

