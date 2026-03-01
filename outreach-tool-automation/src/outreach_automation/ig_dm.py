from __future__ import annotations

import asyncio
import contextlib
import random
from pathlib import Path
from typing import Any

from outreach_automation.dm_format import normalize_dm_text
from outreach_automation.models import Account, ChannelResult, Platform
from outreach_automation.selectors import (
    INSTAGRAM_DM_INPUTS,
    INSTAGRAM_INBOX_SEARCH_INPUTS,
    INSTAGRAM_THREAD_ROWS,
)
from outreach_automation.session_manager import SessionManager


class InstagramDmSender:
    def __init__(self, session_manager: SessionManager) -> None:
        self._session_manager = session_manager

    def send(self, ig_handle: str | None, dm_text: str, account: Account | None, *, dry_run: bool) -> ChannelResult:
        if not ig_handle:
            return ChannelResult(status="skipped", error_code="missing_ig_handle")
        if account is None:
            return ChannelResult(status="pending_tomorrow", error_code="no_ig_account")
        if dry_run:
            return ChannelResult(status="sent")
        profile_dir = self._session_manager.profile_dir_for(Platform.INSTAGRAM, account.handle)
        if not profile_dir.exists():
            return ChannelResult(status="failed", error_code="missing_ig_session")
        try:
            asyncio.run(
                self._send_async(
                    ig_handle=ig_handle,
                    dm_text=dm_text,
                    profile_dir=profile_dir,
                )
            )
            return ChannelResult(status="sent")
        except Exception as exc:
            message = str(exc).lower()
            if "no matching selector found" in message:
                return ChannelResult(status="skipped", error_code="ig_dm_unavailable")
            if "blocked" in message or "rate" in message:
                return ChannelResult(
                    status="failed",
                    error_code="ig_blocked",
                    error_message=str(exc),
                )
            return ChannelResult(status="failed", error_code="ig_send_failed", error_message=str(exc))

    async def _send_async(self, ig_handle: str, dm_text: str, profile_dir: Path) -> None:
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("playwright not installed") from exc

        async with async_playwright() as p:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                channel="chrome",
                headless=False,
            )
            page = await context.new_page()
            opened = await _open_thread_via_inbox_search(page, ig_handle)
            if not opened:
                raise RuntimeError("No matching selector found: instagram thread row")

            message_text = normalize_dm_text(dm_text)
            if not message_text:
                raise RuntimeError("Empty DM text after normalization")

            input_locator = await _find_first(page, INSTAGRAM_DM_INPUTS)
            await input_locator.click()
            await page.keyboard.insert_text(message_text)
            await page.keyboard.press("Enter")

            await page.wait_for_timeout(random.randint(2000, 5000))
            await context.close()


async def _find_first(page: Any, selectors: list[str]) -> Any:
    for selector in selectors:
        loc = page.locator(selector)
        if await loc.count() > 0:
            return loc.first
    raise RuntimeError("No matching selector found")


async def _open_thread_via_inbox_search(page: Any, ig_handle: str) -> bool:
    await page.goto("https://www.instagram.com/direct/inbox/", wait_until="domcontentloaded")
    await page.wait_for_timeout(random.randint(1200, 2500))
    await _dismiss_instagram_popups(page)

    try:
        search = await _find_first(page, INSTAGRAM_INBOX_SEARCH_INPUTS)
    except RuntimeError:
        await _dismiss_instagram_popups(page)
        search = None
        with contextlib.suppress(RuntimeError):
            search = await _find_first(page, INSTAGRAM_INBOX_SEARCH_INPUTS)
        if search is None:
            return False

    await search.click()
    await search.fill("")
    await search.type(ig_handle, delay=random.randint(20, 60))
    await page.wait_for_timeout(random.randint(1200, 2400))

    rows = await _find_all(page, INSTAGRAM_THREAD_ROWS)
    target = ig_handle.strip().lower().lstrip("@")
    for row in rows:
        text = (await row.inner_text()).strip().lower()
        if not text:
            continue
        if target in text:
            await row.click()
            await page.wait_for_timeout(random.randint(1000, 2200))
            return True
    return False


async def _find_all(page: Any, selectors: list[str]) -> list[Any]:
    out: list[Any] = []
    for selector in selectors:
        loc = page.locator(selector)
        count = await loc.count()
        if count == 0:
            continue
        for idx in range(count):
            out.append(loc.nth(idx))
        if out:
            return out
    return out


async def _dismiss_instagram_popups(page: Any) -> None:
    # Common modal that blocks inbox interactions: "Turn on Notifications".
    candidates = [
        page.get_by_role("button", name="Not Now"),
        page.locator("button:has-text('Not Now')"),
        page.get_by_role("button", name="Not now"),
    ]
    for locator in candidates:
        with contextlib.suppress(Exception):
            if await locator.count() > 0:
                await locator.first.click()
                await page.wait_for_timeout(random.randint(300, 900))
