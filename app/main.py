from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI  # noqa: E402
from fastapi.responses import HTMLResponse  # noqa: E402

from config.settings import get_settings  # noqa: E402
from dashboard.api import router  # noqa: E402
from dashboard.web import dashboard_html  # noqa: E402
from journal.database import SessionLocal, init_db  # noqa: E402
from runtime.task_manager import RuntimeTaskManager  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    app.state.runtime_manager = RuntimeTaskManager(
        settings=get_settings(),
        session_factory=SessionLocal,
    )
    try:
        yield
    finally:
        await app.state.runtime_manager.stop_testnet()


app = FastAPI(title="Binance AI Trader MVP", version="0.3.0", lifespan=lifespan)
app.include_router(router)


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return """
    <html>
      <head><title>Binance AI Trader MVP</title></head>
      <body>
        <h1>Binance AI Trader MVP</h1>
        <ul>
          <li><a href="/dashboard">Local Operations Dashboard</a></li>
          <li><a href="/health">Health</a></li>
          <li><a href="/status">Status</a></li>
          <li><a href="/config/safe">Safe Config</a></li>
          <li><a href="/orders/recent">Recent Orders</a></li>
        </ul>
      </body>
    </html>
    """


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard() -> str:
    return dashboard_html()
