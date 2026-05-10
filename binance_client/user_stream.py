from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import websockets
from pydantic import SecretStr

from binance_client.market_stream import StreamHealth
from binance_client.signing import current_timestamp_ms, sign_hmac_sha256


@dataclass
class UserDataStreamClient:
    ws_api_base: str
    api_key: SecretStr | str
    api_secret: SecretStr | str
    recv_window: int = 5000
    reconnect_delay_seconds: float = 2.0
    health: StreamHealth = field(default_factory=StreamHealth)

    @property
    def _api_key_value(self) -> str:
        if isinstance(self.api_key, SecretStr):
            return self.api_key.get_secret_value()
        return self.api_key

    @property
    def _api_secret_value(self) -> str:
        if isinstance(self.api_secret, SecretStr):
            return self.api_secret.get_secret_value()
        return self.api_secret

    def _subscription_request(self) -> dict[str, Any]:
        params: dict[str, Any] = {
            "apiKey": self._api_key_value,
            "recvWindow": self.recv_window,
            "timestamp": current_timestamp_ms(),
        }
        params["signature"] = sign_hmac_sha256(params, self._api_secret_value)
        return {
            "id": str(uuid.uuid4()),
            "method": "userDataStream.subscribe.signature",
            "params": params,
        }

    async def events(
        self, stop_event: asyncio.Event | None = None
    ) -> AsyncIterator[dict[str, Any]]:
        stop_event = stop_event or asyncio.Event()
        self.health.stop_requested = False
        while not stop_event.is_set():
            try:
                async with websockets.connect(self.ws_api_base, ping_interval=20) as websocket:
                    await websocket.send(json.dumps(self._subscription_request()))
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
                        if "event" in payload:
                            event = dict(payload["event"])
                            if event.get("e") == "serverShutdown":
                                raise RuntimeError("Binance user stream serverShutdown event")
                            yield event
                        elif payload.get("status", 200) >= 400:
                            raise RuntimeError(payload.get("error", payload))
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
