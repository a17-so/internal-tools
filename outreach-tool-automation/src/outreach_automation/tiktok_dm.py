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
        session_path = self._session_manager.path_for(Platform.TIKTOK, account.handle)
        if not session_path.exists():
            return ChannelResult(status="failed", error_code="missing_tiktok_session")
        try:
            asyncio.run(self._send_async(handle=handle, dm_text=dm_text, session_path=session_path))
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

    async def _send_async(self, handle: str, dm_text: str, session_path: Path) -> None:
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("playwright not installed") from exc

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context_kwargs: dict[str, Any] = {}
            if session_path.exists():
                context_kwargs["storage_state"] = str(session_path)
            context = await browser.new_context(**context_kwargs)
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
            await input_locator.type(message_text, delay=random.randint(25, 80))
            await page.keyboard.press("Enter")

            await context.storage_state(path=str(session_path))
            await page.wait_for_timeout(random.randint(2000, 5000))
            await context.close()
            await browser.close()


async def _find_first(page: Any, selectors: list[str]) -> Any:
    for selector in selectors:
        loc = page.locator(selector)
        if await loc.count() > 0:
            return loc.first
    raise RuntimeError("No matching selector found")


async def _click_first(page: Any, selectors: list[str]) -> None:
    loc = await _find_first(page, selectors)
    await loc.click()


def _extract_handle(url: str) -> str | None:
    match = re.search(r"tiktok\.com/@([A-Za-z0-9_.]+)", url)
    if not match:
        return None
    return match.group(1)
