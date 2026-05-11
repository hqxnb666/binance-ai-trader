from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from dashboard.web import dashboard_html


def test_dashboard_page_returns_local_operations_html() -> None:
    with TestClient(app) as client:
        response = client.get("/dashboard")

    assert response.status_code == 200
    html = response.text
    assert "Binance AI Trader Local Operations Dashboard" in html
    assert "Runtime" in html
    assert "DataQualityGate" in html
    assert "Shadow Mode" in html
    assert "RiskEngine" in html
    assert "Review Workspace" in html


def test_dashboard_html_contains_safety_boundaries() -> None:
    html = dashboard_html()

    assert "No real order button" in html
    assert "No Live switch" in html
    assert "No disable-dry-run button" in html
    assert "No order execution enable button" in html
    assert "/runtime/testnet/start-dry-run" in html
    assert "/control/kill-switch/off" in html


def test_dashboard_route_does_not_break_health_or_status() -> None:
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/status").status_code == 200
