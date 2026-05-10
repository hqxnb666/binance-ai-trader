from __future__ import annotations

import hashlib
import hmac
from decimal import Decimal

from binance_client.signing import (
    build_signed_params,
    canonical_query_string,
    clean_params,
    sign_query_string,
)


def test_canonical_query_string_stable_sort_and_drops_none() -> None:
    query = canonical_query_string({"b": "2", "a": "1", "skip": None})
    assert query == "a=1&b=2"


def test_decimal_uses_plain_string_not_scientific_notation() -> None:
    cleaned = clean_params({"quantity": Decimal("0.00000100"), "price": Decimal("123.4500")})
    assert cleaned["quantity"] == "0.00000100"
    assert cleaned["price"] == "123.4500"
    assert "quantity=0.00000100" in canonical_query_string(cleaned)


def test_build_signed_params_includes_timestamp_recv_window_before_signature() -> None:
    secret = "test-secret"
    params = {
        "symbol": "BTCUSDT",
        "side": "BUY",
        "type": "LIMIT",
        "quantity": Decimal("0.0100"),
        "price": Decimal("1.2300"),
        "newClientOrderId": "diag-order_1",
    }
    signed = build_signed_params(
        params,
        secret,
        timestamp_ms=1_700_000_000_000,
        recv_window=5000,
    )
    unsigned_query = canonical_query_string(
        {key: value for key, value in signed.items() if key != "signature"}
    )
    expected = hmac.new(
        secret.encode("utf-8"),
        unsigned_query.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    assert signed["timestamp"] == "1700000000000"
    assert signed["recvWindow"] == "5000"
    assert signed["signature"] == expected


def test_signed_params_order_matches_signed_query_string_and_signature_last() -> None:
    signed = build_signed_params(
        {"symbol": "ETHUSDT", "newClientOrderId": "abc-123"},
        "secret",
        timestamp_ms=123,
        recv_window=6000,
    )
    assert list(signed) == ["newClientOrderId", "recvWindow", "symbol", "timestamp", "signature"]
    query = canonical_query_string(
        {key: value for key, value in signed.items() if key != "signature"}
    )
    assert signed["signature"] == sign_query_string(query, "secret")


def test_signed_params_do_not_leak_secret() -> None:
    signed = build_signed_params(
        {"symbol": "BTCUSDT"}, "super-secret", timestamp_ms=1, recv_window=1
    )
    rendered = str(signed)
    assert "super-secret" not in rendered
