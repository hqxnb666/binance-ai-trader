from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    side: Literal["BUY", "SELL"]
    order_type: Literal["LIMIT", "MARKET"] = Field(default="LIMIT")
    quantity: Decimal
    price: Decimal | None = None
    time_in_force: str = "GTC"
    client_order_id: str | None = None

    @field_validator("symbol")
    @classmethod
    def uppercase_symbol(cls, value: str) -> str:
        return value.upper()

    @field_validator("quantity")
    @classmethod
    def positive_quantity(cls, value: Decimal) -> Decimal:
        if value <= 0:
            msg = "quantity must be positive"
            raise ValueError(msg)
        return value


class OrderResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    symbol: str
    order_id: str | int | None = None
    client_order_id: str
    status: str
    side: str
    order_type: str
    price: Decimal | None = None
    quantity: Decimal
    raw: dict[str, Any]


class Broker(ABC):
    @abstractmethod
    async def get_account(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def get_exchange_info(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def get_klines(self, symbol: str, interval: str, limit: int) -> list[list[Any]]:
        raise NotImplementedError

    @abstractmethod
    async def place_order(self, order_request: OrderRequest) -> OrderResult:
        raise NotImplementedError

    async def test_order(self, order_request: OrderRequest) -> dict[str, Any]:
        raise NotImplementedError("Broker does not implement test_order")

    @abstractmethod
    async def cancel_order(self, symbol: str, order_id: int | str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def get_order(self, symbol: str, order_id: int | str) -> dict[str, Any]:
        raise NotImplementedError
