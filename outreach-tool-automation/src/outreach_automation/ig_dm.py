from __future__ import annotations

import asyncio
import random
from typing import Any

from outreach_automation.models import Account, ChannelResult, Platform
from outreach_automation.selectors import INSTAGRAM_DM_INPUTS, INSTAGRAM_MESSAGE_BUTTONS
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
        try:
            asyncio.run(self._send_async(ig_handle=ig_handle, dm_text=dm_text, account=account))
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

    async def _send_async(self, ig_handle: str, dm_text: str, account: Account) -> None:
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("playwright not installed") from exc

        session_path = self._session_manager.path_for(Platform.INSTAGRAM, account.handle)
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context_kwargs: dict[str, Any] = {}
            if session_path.exists():
                context_kwargs["storage_state"] = str(session_path)
            context = await browser.new_context(**context_kwargs)
            page = await context.new_page()
            await page.goto(f"https://www.instagram.com/{ig_handle}", wait_until="domcontentloaded")
            await page.wait_for_timeout(random.randint(1500, 4000))

            await _click_first(page, INSTAGRAM_MESSAGE_BUTTONS)
            await page.wait_for_timeout(random.randint(1000, 3000))

            input_locator = await _find_first(page, INSTAGRAM_DM_INPUTS)
            await input_locator.click()
            await input_locator.type(dm_text, delay=random.randint(25, 80))
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
