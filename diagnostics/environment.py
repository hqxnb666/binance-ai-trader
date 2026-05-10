from __future__ import annotations

import os
import platform
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from diagnostics.proxy_detection import detect_proxy_env, proxy_warning

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_ENV = [
    "BINANCE_TESTNET_API_KEY",
    "BINANCE_TESTNET_API_SECRET",
    "OPENAI_API_KEY",
]


def collect_environment() -> dict[str, Any]:
    proxy_env = detect_proxy_env()
    env = {
        "python_version": sys.version.split()[0],
        "os": f"{platform.system()} {platform.release()}",
        "timezone": datetime.now().astimezone().tzname(),
        "system_time": datetime.now().astimezone().isoformat(),
        "env_file_exists": (ROOT / ".env").exists(),
        "required_env": {name: _env_presence(name) for name in REQUIRED_ENV},
        "proxy_env": proxy_env,
    }
    warning = proxy_warning(proxy_env)
    if warning:
        env["proxy_warning"] = warning
    return env


def _env_presence(name: str) -> str:
    value = os.getenv(name)
    return "present" if value and not value.startswith("your_") else "missing"
