from __future__ import annotations

from diagnostics.proxy_detection import detect_proxy_env, proxy_env_present, proxy_warning


def test_proxy_detection_only_reports_presence(monkeypatch) -> None:
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:7890")
    report = detect_proxy_env()
    assert report["HTTP_PROXY"] == "present"
    assert "127.0.0.1" not in str(report)
    assert proxy_env_present(report) is True
    assert "explicit proxy environment variables" in (proxy_warning(report) or "")

