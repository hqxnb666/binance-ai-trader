from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrategySignalPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    strategy_name: str
    strategy_version: str
    timeframe: str
    side: Literal["BUY", "SELL", "HOLD"]
    signal_type: str
    confidence: float = Field(ge=0, le=1)
    reason: str
    raw_payload_json: dict[str, Any]

    @field_validator("symbol")
    @classmethod
    def uppercase_symbol(cls, value: str) -> str:
        return value.upper()


class Strategy(ABC):
    name: str
    version: str

    @abstractmethod
    def generate_signal(self, *args: Any, **kwargs: Any) -> StrategySignalPayload | None:
        raise NotImplementedError

