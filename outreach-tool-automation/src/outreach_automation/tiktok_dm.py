from __future__ import annotations

import asyncio
import random
import re
from pathlib import Path
from typing import Any

from outreach_automation.dm_format import normalize_dm_text
from outreach_automation.models import Account, ChannelResult, Platform
from outreach_automation.selectors import TIKTOK_DM_INPUTS, TIKTOK_MESSAGE_BUTTONS
from outreach_automation.session_manager import SessionManager


class TiktokDmSender:
    def __init__(self, session_manager: SessionManager) -> None:
        self._session_manager = session_manager

    def send(self, creator_url: str, dm_text: str, account: Account | None, *, dry_run: bool) -> ChannelResult:
        handle = _extract_handle(creator_url)
        if not handle:
            return ChannelResult(status="skipped", error_code="missing_tiktok_handle")
        if account is None:
            return ChannelResult(status="pending_tomorrow", error_code="no_tiktok_account")
        if dry_run:
            return ChannelResult(status="sent")
        profile_dir = self._session_manager.profile_dir_for(Platform.TIKTOK, account.handle)
        if not profile_dir.exists():
            return ChannelResult(status="failed", error_code="missing_tiktok_session")
        try:
            asyncio.run(self._send_async(handle=handle, dm_text=dm_text, profile_dir=profile_dir))
            return ChannelResult(status="sent")
        except Exception as exc:
            message = str(exc).lower()
            if "no matching selector found" in message:
                return ChannelResult(status="skipped", error_code="tiktok_dm_unavailable")
            if "blocked" in message or "rate" in message:
                return ChannelResult(
                    status="failed",
                    error_code="tiktok_blocked",
                    error_message=str(exc),
                )
            return ChannelResult(status="failed", error_code="tiktok_send_failed", error_message=str(exc))

    async def _send_async(self, handle: str, dm_text: str, profile_dir: Path) -> None:
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
            await page.goto(f"https://www.tiktok.com/@{handle}", wait_until="domcontentloaded")
            await page.wait_for_timeout(random.randint(1500, 4000))

            await _click_first(page, TIKTOK_MESSAGE_BUTTONS)
            await page.wait_for_timeout(random.randint(1000, 3000))

            message_text = normalize_dm_text(dm_text)
            if not message_text:
                raise RuntimeError("Empty DM text after normalization")

            input_locator = await _find_first(page, TIKTOK_DM_INPUTS)
            await input_locator.click()
            await _type_multiline_message(page=page, input_locator=input_locator, text=message_text)
            await page.keyboard.press("Enter")

            await page.wait_for_timeout(random.randint(2000, 5000))
            await context.close()


async def _find_first(page: Any, selectors: list[str]) -> Any:
    for selector in selectors:
        loc = page.locator(selector)
        if await loc.count() > 0:
            return loc.first
    raise RuntimeError("No matching selector found")


async def _click_first(page: Any, selectors: list[str]) -> None:
    loc = await _find_first(page, selectors)
    await loc.click()


async def _type_multiline_message(page: Any, input_locator: Any, text: str) -> None:
    lines = text.split("\n")
    for idx, line in enumerate(lines):
        if line:
            await input_locator.type(line, delay=random.randint(25, 80))
        if idx < len(lines) - 1:
            await page.keyboard.down("Shift")
            await page.keyboard.press("Enter")
            await page.keyboard.up("Shift")


def _extract_handle(url: str) -> str | None:
    match = re.search(r"tiktok\.com/@([A-Za-z0-9_.]+)", url)
    if not match:
        return None
    return match.group(1)
