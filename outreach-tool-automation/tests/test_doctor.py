from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

from outreach_automation.doctor import (
    _check_account_readiness_matrix,
    _check_tiktok_attach,
    _check_tiktok_mode,
)
from outreach_automation.models import Account, AccountStatus, Platform


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


def test_check_tiktok_mode_invalid_is_blocking() -> None:
    settings = SimpleNamespace(tiktok_cycling_mode="weird", tiktok_attach_mode=False)
    result = _check_tiktok_mode(settings)  # type: ignore[arg-type]
    assert result.ok is False
    assert result.blocking is True


def test_check_tiktok_mode_attach_requires_attach_flag() -> None:
    settings = SimpleNamespace(tiktok_cycling_mode="attach_single_browser", tiktok_attach_mode=False)
    result = _check_tiktok_mode(settings)  # type: ignore[arg-type]
    assert result.ok is False
    assert result.blocking is True


def test_check_tiktok_mode_attach_per_account_requires_attach_flag() -> None:
    settings = SimpleNamespace(tiktok_cycling_mode="attach_per_account_browser", tiktok_attach_mode=False)
    result = _check_tiktok_mode(settings)  # type: ignore[arg-type]
    assert result.ok is False
    assert result.blocking is True


def test_check_tiktok_attach_per_account_missing_map_is_blocking() -> None:
    settings = SimpleNamespace(
        tiktok_attach_mode=True,
        tiktok_cycling_mode="attach_per_account_browser",
        tiktok_attach_account_cdp_urls={},
        tiktok_attach_auto_start=True,
    )
    result = _check_tiktok_attach(settings)  # type: ignore[arg-type]
    assert result.ok is False
    assert result.blocking is True


class _FakeFirestore:
    def list_active_accounts(self, platform: Platform) -> list[Account]:
        if platform == Platform.EMAIL:
            return [
                Account(
                    id="e1",
                    platform=Platform.EMAIL,
                    handle="ethan@a17.so",
                    status=AccountStatus.ACTIVE,
                    daily_sent=0,
                    daily_limit=100,
                )
            ]
        if platform == Platform.INSTAGRAM:
            return [
                Account(
                    id="i1",
                    platform=Platform.INSTAGRAM,
                    handle="@ethan",
                    status=AccountStatus.ACTIVE,
                    daily_sent=0,
                    daily_limit=100,
                )
            ]
        return [
            Account(
                id="t1",
                platform=Platform.TIKTOK,
                handle="@ethan",
                status=AccountStatus.ACTIVE,
                daily_sent=0,
                daily_limit=100,
            )
        ]


def test_readiness_matrix_includes_accounts(tmp_path: Any) -> None:
    settings = SimpleNamespace(
        gmail_accounts=(SimpleNamespace(email="ethan@a17.so"),),
        ig_profile_dir=tmp_path / "ig",
        tiktok_profile_dir=tmp_path / "tt",
        tiktok_attach_mode=False,
        tiktok_cycling_mode="per_account_session",
        tiktok_attach_auto_start=False,
        tiktok_sender_handle="@ethan",
        tiktok_cdp_url=None,
    )
    result = _check_account_readiness_matrix(settings, _FakeFirestore())  # type: ignore[arg-type]
    assert result.ok is True
    payload = json.loads(result.detail)
    assert payload["total_accounts"] == 3
    assert any(item["platform"] == "email" for item in payload["matrix"])
