from __future__ import annotations

import asyncio
import contextlib
import random
import re
from pathlib import Path
from typing import Any

from outreach_automation.dm_format import normalize_dm_text
from outreach_automation.models import Account, ChannelResult, Platform
from outreach_automation.selectors import TIKTOK_DM_INPUTS
from outreach_automation.session_manager import SessionManager


class TiktokDmSender:
    def __init__(
        self,
        session_manager: SessionManager,
        *,
        attach_mode: bool = False,
        cdp_url: str | None = None,
    ) -> None:
        self._session_manager = session_manager
        self._attach_mode = attach_mode
        self._cdp_url = cdp_url

    def send(self, creator_url: str, dm_text: str, account: Account | None, *, dry_run: bool) -> ChannelResult:
        handle = _extract_handle(creator_url)
        if not handle:
            return ChannelResult(status="skipped", error_code="missing_tiktok_handle")
        if account is None:
            return ChannelResult(status="pending_tomorrow", error_code="no_tiktok_account")
        if dry_run:
            return ChannelResult(status="sent")

        profile_dir: Path | None = None
        if self._attach_mode:
            if not self._cdp_url:
                return ChannelResult(status="failed", error_code="missing_tiktok_cdp_url")
        else:
            profile_dir = self._session_manager.profile_dir_for(Platform.TIKTOK, account.handle)
            if not profile_dir.exists():
                return ChannelResult(status="failed", error_code="missing_tiktok_session")

        try:
            asyncio.run(
                self._send_async(
                    handle=handle,
                    dm_text=dm_text,
                    profile_dir=profile_dir,
                    attach_mode=self._attach_mode,
                    cdp_url=self._cdp_url,
                )
            )
            return ChannelResult(status="sent")
        except Exception as exc:
            message = str(exc).lower()
            if "missing tiktok auth" in message:
                return ChannelResult(status="failed", error_code="missing_tiktok_auth")
            if "missing tiktok target thread" in message:
                return ChannelResult(status="failed", error_code="tiktok_target_thread_not_found")
            if "no matching selector found" in message:
                return ChannelResult(status="skipped", error_code="tiktok_dm_unavailable")
            if "blocked" in message or "rate" in message:
                return ChannelResult(
                    status="failed",
                    error_code="tiktok_blocked",
                    error_message=str(exc),
                )
            return ChannelResult(status="failed", error_code="tiktok_send_failed", error_message=str(exc))

    async def _send_async(
        self,
        handle: str,
        dm_text: str,
        profile_dir: Path | None,
        *,
        attach_mode: bool,
        cdp_url: str | None,
    ) -> None:
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("playwright not installed") from exc

        async with async_playwright() as p:
            if attach_mode:
                if not cdp_url:
                    raise RuntimeError("missing tiktok cdp url")
                browser = await p.chromium.connect_over_cdp(cdp_url)
                contexts = browser.contexts
                if not contexts:
                    raise RuntimeError("No browser contexts found in attached Chrome session")
                context = contexts[0]
                page = await context.new_page()
                close_context = False
            else:
                if profile_dir is None:
                    raise RuntimeError("missing profile dir")
                context = await p.chromium.launch_persistent_context(
                    user_data_dir=str(profile_dir),
                    channel="chrome",
                    headless=False,
                )
                page = await context.new_page()
                close_context = True
            await page.goto(f"https://www.tiktok.com/@{handle}", wait_until="domcontentloaded")
            await _slow_settle(page)
            if await _needs_login(page):
                raise RuntimeError("missing tiktok auth")

            opened_target_thread = await _open_profile_message_thread(page)
            if not opened_target_thread:
                raise RuntimeError("missing tiktok target thread")
            await _slow_settle(page)

            message_text = normalize_dm_text(dm_text)
            if not message_text:
                raise RuntimeError("Empty DM text after normalization")

            input_locator = await _find_first(page, TIKTOK_DM_INPUTS)
            await input_locator.click()
            await page.keyboard.insert_text(message_text)
            await page.keyboard.press("Enter")

            await page.wait_for_timeout(random.randint(2000, 5000))
            await page.close()
            if close_context:
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


async def _open_profile_message_thread(page: Any) -> bool:
    # Prefer the profile CTA link with a user-specific conversation id.
    link_candidates = page.locator("a[href*='/messages?'][href*='u=']")
    link_count = await link_candidates.count()
    for idx in range(link_count):
        candidate = link_candidates.nth(idx)
        text = (await candidate.inner_text()).strip().lower()
        href = (await candidate.get_attribute("href") or "").lower()
        if text == "message" and "u=" in href:
            await candidate.click()
            return True

    # Fallback: click exact-text "Message" control near top profile header.
    generic_candidates = page.locator("button:has-text('Message'), a:has-text('Message')")
    generic_count = await generic_candidates.count()
    for idx in range(generic_count):
        candidate = generic_candidates.nth(idx)
        text = (await candidate.inner_text()).strip().lower()
        if text != "message":
            continue
        bbox = await candidate.bounding_box()
        if bbox is not None and float(bbox.get("y", 9999.0)) > 220.0:
            continue
        await candidate.click()
        return True
    return False


async def _slow_settle(page: Any) -> None:
    with contextlib.suppress(Exception):
        await page.wait_for_load_state("networkidle", timeout=12000)
    await page.wait_for_timeout(random.randint(4500, 8500))


async def _needs_login(page: Any) -> bool:
    login_button = page.locator("button:has-text('Log in')")
    count = int(await login_button.count())
    return count > 0


def _extract_handle(url: str) -> str | None:
    match = re.search(r"tiktok\.com/@([A-Za-z0-9_.]+)", url)
    if not match:
        return None
    return match.group(1)
