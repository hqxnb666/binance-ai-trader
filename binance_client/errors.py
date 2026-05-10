from __future__ import annotations


class BinanceClientError(Exception):
    """Base Binance client error."""


class BinanceAPIError(BinanceClientError):
    def __init__(
        self,
        code: int,
        message: str,
        *,
        status_code: int | None = None,
        retry_after: int | None = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retry_after = retry_after
        super().__init__(f"Binance API error {code}: {message}")


class BinanceRateLimitError(BinanceAPIError):
    """Raised for 418/429 responses."""


class BinanceNetworkError(BinanceClientError):
    """Raised for network or timeout errors."""


class LiveTradingDisabledError(BinanceClientError):
    """Raised when live trading is attempted without explicit enablement."""


class OrderValidationError(BinanceClientError):
    """Raised when an order fails exchange filter validation."""


class RiskRejectedError(BinanceClientError):
    """Raised when risk rejects an order request."""

