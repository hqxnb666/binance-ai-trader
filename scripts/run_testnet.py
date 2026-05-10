from __future__ import annotations

import asyncio
import signal
import sys
from contextlib import suppress
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.settings import get_settings  # noqa: E402
from journal.database import SessionLocal, init_db  # noqa: E402
from runtime.trading_daemon import TestnetTradingDaemon  # noqa: E402


async def main() -> None:
    settings = get_settings()
    init_db()
    daemon = TestnetTradingDaemon(settings=settings, session_factory=SessionLocal)
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop_event.set)
    await daemon.start()
    print("Testnet daemon started. Press Ctrl+C to stop.")
    try:
        await stop_event.wait()
    finally:
        await daemon.stop()
        print("Testnet daemon stopped.")


if __name__ == "__main__":
    asyncio.run(main())
