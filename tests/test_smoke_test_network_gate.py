from __future__ import annotations

import pytest

import scripts.smoke_test_testnet as smoke


@pytest.mark.asyncio
async def test_smoke_stops_when_testnet_rest_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(smoke, "_config_error", lambda summary, require_openai: None)
    monkeypatch.setattr(
        smoke,
        "run_diagnostics",
        lambda include_openai=False: _async(_diagnostics(rest="NETWORK_ERROR", openai="OK")),
    )
    report = await smoke.smoke_test()
    assert report["status"] == "DIAGNOSTICS_FAILED"
    assert "Binance Testnet REST unavailable" in report["error"]


@pytest.mark.asyncio
async def test_smoke_with_ai_requires_openai_ok(monkeypatch) -> None:
    monkeypatch.setattr(smoke, "_config_error", lambda summary, require_openai: None)
    monkeypatch.setattr(
        smoke,
        "run_diagnostics",
        lambda include_openai=False: _async(_diagnostics(rest="OK", openai="MISSING_KEY")),
    )
    report = await smoke.smoke_test(with_ai=True)
    assert report["status"] == "DIAGNOSTICS_FAILED"
    assert "OpenAI API unavailable" in report["error"]


@pytest.mark.asyncio
async def test_smoke_no_ai_allows_openai_missing_until_later_stages(monkeypatch) -> None:
    called_stage1 = False

    async def fake_stage1(*args, **kwargs):
        nonlocal called_stage1
        called_stage1 = True
        raise RuntimeError("stop after gate")

    monkeypatch.setattr(smoke, "_config_error", lambda summary, require_openai: None)
    monkeypatch.setattr(
        smoke,
        "run_diagnostics",
        lambda include_openai=False: _async(_diagnostics(rest="OK", openai="MISSING_KEY")),
    )
    monkeypatch.setattr(smoke, "_stage1_rest", fake_stage1)
    report = await smoke.smoke_test(with_ai=False)
    assert called_stage1 is True
    assert report["status"] == "FAILED"


def _diagnostics(*, rest: str, openai: str) -> dict[str, object]:
    return {
        "environment": {"proxy_env": {"HTTP_PROXY": "absent"}},
        "connectivity": {
            "binance_testnet_rest": {"status": rest},
            "binance_testnet_ws": {"status": "OK"},
            "openai_api": {"status": openai},
        },
        "recommended_next_action": [],
    }


def _async(value):
    async def inner(*args, **kwargs):
        return value

    return inner()

