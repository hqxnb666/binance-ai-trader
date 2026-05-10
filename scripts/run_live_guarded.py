from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker.binance_spot_live import require_live_enabled  # noqa: E402
from config.settings import get_settings  # noqa: E402

if __name__ == "__main__":
    settings = get_settings()
    require_live_enabled(settings)
    print("Live guard passed. No live worker is started automatically in MVP.")

