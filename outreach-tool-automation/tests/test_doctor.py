from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from outreach_automation.doctor import _check_tiktok_attach


def test_check_tiktok_attach_disabled_is_ok() -> None:
    settings = SimpleNamespace(
        tiktok_attach_mode=False,
        tiktok_cdp_url=None,
        tiktok_attach_auto_start=True,
    )
    result = _check_tiktok_attach(settings)  # type: ignore[arg-type]
    assert result.ok is True
    assert result.blocking is False


def test_check_tiktok_attach_missing_url_is_blocking() -> None:
    settings = SimpleNamespace(
        tiktok_attach_mode=True,
        tiktok_cdp_url=None,
        tiktok_attach_auto_start=True,
    )
    result = _check_tiktok_attach(settings)  # type: ignore[arg-type]
    assert result.ok is False
    assert result.blocking is True


def test_check_tiktok_attach_unreachable_not_blocking_when_autostart(monkeypatch: Any) -> None:
    settings = SimpleNamespace(
        tiktok_attach_mode=True,
        tiktok_cdp_url="http://127.0.0.1:9222",
        tiktok_attach_auto_start=True,
    )
    monkeypatch.setattr("outreach_automation.doctor._is_socket_reachable", lambda host, port: False)
    result = _check_tiktok_attach(settings)  # type: ignore[arg-type]
    assert result.ok is False
    assert result.blocking is False


def test_check_tiktok_attach_unreachable_blocking_when_no_autostart(monkeypatch: Any) -> None:
    settings = SimpleNamespace(
        tiktok_attach_mode=True,
        tiktok_cdp_url="http://127.0.0.1:9222",
        tiktok_attach_auto_start=False,
    )
    monkeypatch.setattr("outreach_automation.doctor._is_socket_reachable", lambda host, port: False)
    result = _check_tiktok_attach(settings)  # type: ignore[arg-type]
    assert result.ok is False
    assert result.blocking is True
