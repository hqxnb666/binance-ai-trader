from __future__ import annotations

import os

PROXY_ENV_NAMES = [
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "no_proxy",
]

PROXY_WARNING = (
    "Python process may be using explicit proxy environment variables. Clash rule-based DIRECT "
    "may not behave as expected if traffic is forced through a proxy endpoint first; verify Clash "
    "rule mode and runtime proxy settings."
)


def detect_proxy_env() -> dict[str, str]:
    return {name: "present" if os.getenv(name) else "absent" for name in PROXY_ENV_NAMES}


def proxy_env_present(proxy_env: dict[str, str] | None = None) -> bool:
    values = proxy_env or detect_proxy_env()
    proxy_keys = {
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    }
    return any(values.get(key) == "present" for key in proxy_keys)


def proxy_warning(proxy_env: dict[str, str] | None = None) -> str | None:
    return PROXY_WARNING if proxy_env_present(proxy_env) else None
