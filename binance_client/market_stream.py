from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import websockets


@dataclass
class StreamHealth:
    connected: bool = False
    last_message_time: datetime | None = None
    last_event_at: datetime | None = None
    last_error: str | None = None
    reconnect_count: int = 0
    reconnects: int = 0
    reconnecting: bool = False
    stop_requested: bool = False
    unhealthy_after_seconds: float = 30.0

    @property
    def status(self) -> str:
        return "ok" if self.is_healthy() else "disconnected"

    def mark_message(self) -> None:
        now = datetime.now(UTC)
        self.connected = True
        self.reconnecting = False
        self.last_message_time = now
        self.last_event_at = now

    def mark_reconnect(self, error: str) -> None:
        self.connected = False
        self.reconnecting = True
        self.last_error = error
        self.reconnect_count += 1
        self.reconnects = self.reconnect_count

    def data_delay_seconds(self) -> float:
        if self.last_message_time is None:
            return float("inf")
        return max((datetime.now(UTC) - self.last_message_time).total_seconds(), 0.0)

    def is_healthy(self, unhealthy_after_seconds: float | None = None) -> bool:
        threshold = unhealthy_after_seconds or self.unhealthy_after_seconds
        return self.connected and self.data_delay_seconds() <= threshold and not self.reconnecting

    def as_dict(self) -> dict[str, object]:
        return {
            "connected": self.connected,
            "last_message_time": self.last_message_time.isoformat()
            if self.last_message_time
            else None,
            "last_error": self.last_error,
            "reconnect_count": self.reconnect_count,
            "reconnecting": self.reconnecting,
            "stop_requested": self.stop_requested,
            "data_delay_seconds": self.data_delay_seconds(),
            "status": self.status,
        }


@dataclass
class KlineStream:
    stream_base: str
    symbols: list[str]
    interval: str
    reconnect_delay_seconds: float = 2.0
    health: StreamHealth = field(default_factory=StreamHealth)

    def stream_url(self) -> str:
        streams = "/".join(f"{symbol.lower()}@kline_{self.interval}" for symbol in self.symbols)
        base = self.stream_base.rstrip("/")
        if base.endswith("/ws"):
            base = base[: -len("/ws")]
        return f"{base}/stream?streams={streams}"

    async def messages(
        self, stop_event: asyncio.Event | None = None
    ) -> AsyncIterator[dict[str, Any]]:
        stop_event = stop_event or asyncio.Event()
        self.health.stop_requested = False
        while not stop_event.is_set():
            try:
                async with websockets.connect(self.stream_url(), ping_interval=20) as websocket:
                    self.health.connected = True
                    self.health.reconnecting = False
                    self.health.last_error = None
                    while not stop_event.is_set():
                        try:
                            raw = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                        except TimeoutError:
                            continue
                        self.health.mark_message()
                        payload = json.loads(raw)
                        data = payload.get("data", payload)
                        if data.get("e") == "serverShutdown":
                            raise RuntimeError("Binance stream serverShutdown event")
                        yield data
            except asyncio.CancelledError:
                self.health.connected = False
                self.health.stop_requested = True
                raise
            except Exception as exc:  # noqa: BLE001 - stream must keep reconnecting
                self.health.mark_reconnect(str(exc))
                if not stop_event.is_set():
                    await asyncio.sleep(self.reconnect_delay_seconds)
        self.health.connected = False
        self.health.reconnecting = False
        self.health.stop_requested = True
