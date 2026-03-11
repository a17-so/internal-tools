from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from outreach_automation.models import Account, AccountStatus, Platform
from outreach_automation.run_once import _build_account_readiness_checker, _validate_tiktok_mode
from outreach_automation.session_manager import SessionManager


def _account(platform: Platform, handle: str) -> Account:
    return Account(
        id=f"{platform.value}-{handle}",
        platform=platform,
        handle=handle,
        status=AccountStatus.ACTIVE,
        daily_sent=0,
        daily_limit=10,
    )


def test_validate_tiktok_mode_rejects_invalid_combo() -> None:
    settings = SimpleNamespace(tiktok_cycling_mode="per_account_session", tiktok_attach_mode=True)
    with pytest.raises(ValueError):
        _validate_tiktok_mode(settings)  # type: ignore[arg-type]


def test_validate_tiktok_mode_accepts_attach_combo() -> None:
    settings = SimpleNamespace(tiktok_cycling_mode="attach_single_browser", tiktok_attach_mode=True)
    _validate_tiktok_mode(settings)  # type: ignore[arg-type]


def test_validate_tiktok_mode_accepts_attach_per_account_combo() -> None:
    settings = SimpleNamespace(tiktok_cycling_mode="attach_per_account_browser", tiktok_attach_mode=True)
    _validate_tiktok_mode(settings)  # type: ignore[arg-type]


def test_readiness_email_requires_refresh_token(tmp_path: Path) -> None:
    settings = SimpleNamespace(
        gmail_accounts=(SimpleNamespace(email="ethan@a17.so"),),
        tiktok_attach_mode=False,
        tiktok_sender_handle=None,
        tiktok_attach_auto_start=False,
        tiktok_cdp_url=None,
    )
    checker = _build_account_readiness_checker(
        settings=settings,  # type: ignore[arg-type]
        session_manager=SessionManager(tmp_path / "ig", tmp_path / "tt"),
    )
    ok, reason = checker(Platform.EMAIL, _account(Platform.EMAIL, "other@a17.so"))
    assert ok is False
    assert reason == "missing_refresh_token"


def test_readiness_instagram_requires_profile_dir(tmp_path: Path) -> None:
    ig_root = tmp_path / "ig"
    tt_root = tmp_path / "tt"
    settings = SimpleNamespace(
        gmail_accounts=(),
        tiktok_attach_mode=False,
        tiktok_sender_handle=None,
        tiktok_attach_auto_start=False,
        tiktok_cdp_url=None,
    )
    session = SessionManager(ig_root, tt_root)
    checker = _build_account_readiness_checker(settings=settings, session_manager=session)  # type: ignore[arg-type]
    account = _account(Platform.INSTAGRAM, "@ethan")
    ok, reason = checker(Platform.INSTAGRAM, account)
    assert ok is False
    assert reason == "missing_session"
    session.profile_dir_for(Platform.INSTAGRAM, account.handle).mkdir(parents=True, exist_ok=True)
    ok2, reason2 = checker(Platform.INSTAGRAM, account)
    assert ok2 is True
    assert reason2 is None


def test_readiness_tiktok_attach_requires_pinned_handle_and_cdp(monkeypatch: Any, tmp_path: Path) -> None:
    settings = SimpleNamespace(
        gmail_accounts=(),
        tiktok_attach_mode=True,
        tiktok_cycling_mode="attach_single_browser",
        tiktok_sender_handle="@regen.app",
        tiktok_attach_auto_start=False,
        tiktok_cdp_url="http://127.0.0.1:9222",
    )
    monkeypatch.setattr("outreach_automation.run_once._is_cdp_reachable", lambda host, port: False)
    checker = _build_account_readiness_checker(
        settings=settings,  # type: ignore[arg-type]
        session_manager=SessionManager(tmp_path / "ig", tmp_path / "tt"),
    )
    ok, reason = checker(Platform.TIKTOK, _account(Platform.TIKTOK, "@other"))
    assert ok is False
    assert reason == "attach_single_account_mismatch"
    ok2, reason2 = checker(Platform.TIKTOK, _account(Platform.TIKTOK, "@regen.app"))
    assert ok2 is False
    assert reason2 == "cdp_unreachable"
