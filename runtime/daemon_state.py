from __future__ import annotations

from collections import deque
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict


class DaemonState(StrEnum):
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    ERROR = "ERROR"


class RuntimeLogEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    time: str
    event: str
    level: str = "INFO"
    payload: dict[str, Any] = {}


class RuntimeLogBuffer:
    def __init__(self, maxlen: int = 500):
        self._items: deque[RuntimeLogEntry] = deque(maxlen=maxlen)

    def append(self, event: str, *, level: str = "INFO", **payload: Any) -> RuntimeLogEntry:
        entry = RuntimeLogEntry(
            time=datetime.now(UTC).isoformat(),
            event=event,
            level=level,
            payload=payload,
        )
        self._items.append(entry)
        return entry

    def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        return [item.model_dump() for item in list(self._items)[-limit:]]

