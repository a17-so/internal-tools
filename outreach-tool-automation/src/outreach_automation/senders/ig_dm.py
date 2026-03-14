from __future__ import annotations

import asyncio
import contextlib
import logging
import random
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, ClassVar

from outreach_automation.dm_format import normalize_dm_text
from outreach_automation.models import Account, ChannelResult, Platform
from outreach_automation.selectors import (
    INSTAGRAM_DM_INPUTS,
    INSTAGRAM_INBOX_SEARCH_INPUTS,
    INSTAGRAM_MESSAGE_BUTTONS,
    INSTAGRAM_THREAD_ROWS,
)
from outreach_automation.node_runtime import suppress_node_deprecation_warnings
from outreach_automation.session_manager import SessionManager

_LOG = logging.getLogger(__name__)


class InstagramDmSender:
    _last_send_ts_by_account: ClassVar[dict[str, float]] = {}

    def __init__(
        self,
        session_manager: SessionManager,
        *,
        attach_mode: bool = False,
        cdp_url: str | None = None,
        cdp_url_resolver: Callable[[str], str | None] | None = None,
        min_seconds_between_sends: int = 2,
        send_jitter_seconds: float = 1.5,
    ) -> None:
        self._session_manager = session_manager
        self._attach_mode = attach_mode
        self._cdp_url = cdp_url
        self._cdp_url_resolver = cdp_url_resolver
        self._min_seconds_between_sends = max(0, min_seconds_between_sends)
        self._send_jitter_seconds = max(0.0, send_jitter_seconds)

    def send(self, ig_handle: str | None, dm_text: str, account: Account | None, *, dry_run: bool) -> ChannelResult:
        if not ig_handle:
            return ChannelResult(status="skipped", error_code="missing_ig_handle")
        if account is None:
            return ChannelResult(status="pending_tomorrow", error_code="no_ig_account")
        if dry_run:
            return ChannelResult(status="sent")
        self._enforce_send_spacing(account.handle)

        profile_dir: Path | None = None
        selected_cdp_url = self._cdp_url
        if self._attach_mode:
            if self._cdp_url_resolver is not None:
                selected_cdp_url = self._cdp_url_resolver(account.handle)
            if not selected_cdp_url:
                return ChannelResult(status="failed", error_code="missing_ig_cdp_url")
        else:
            profile_dir = self._session_manager.profile_dir_for(Platform.INSTAGRAM, account.handle)
            if not profile_dir.exists():
                return ChannelResult(status="failed", error_code="missing_ig_session")
        try:
            asyncio.run(
                self._send_async(
                    ig_handle=ig_handle,
                    dm_text=dm_text,
                    profile_dir=profile_dir,
                    attach_mode=self._attach_mode,
                    cdp_url=selected_cdp_url,
                )
            )
            return ChannelResult(status="sent")
        except Exception as exc:
            message = str(exc).lower()
            if "missing ig auth" in message:
                return ChannelResult(status="failed", error_code="missing_ig_auth", error_message=str(exc))
            if "no matching selector found" in message:
                return ChannelResult(status="skipped", error_code="ig_dm_unavailable")
            if "blocked" in message or "rate" in message:
                return ChannelResult(
                    status="failed",
                    error_code="ig_blocked",
                    error_message=str(exc),
                )
            return ChannelResult(status="failed", error_code="ig_send_failed", error_message=str(exc))

    def _enforce_send_spacing(self, account_handle: str) -> None:
        target_spacing = self._min_seconds_between_sends + random.uniform(0.0, self._send_jitter_seconds)
        if target_spacing <= 0:
            return
        now = time.time()
        last_sent = self._last_send_ts_by_account.get(account_handle, 0.0)
        remaining = target_spacing - (now - last_sent)
        if remaining > 0:
            time.sleep(remaining)
        self._last_send_ts_by_account[account_handle] = time.time()

    async def _send_async(
        self,
        ig_handle: str,
        dm_text: str,
        profile_dir: Path | None,
        *,
        attach_mode: bool,
        cdp_url: str | None,
    ) -> None:
        suppress_node_deprecation_warnings()
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("playwright not installed") from exc

        async with async_playwright() as p:
            page = None
            if attach_mode:
                if not cdp_url:
                    raise RuntimeError("missing ig cdp url")
                _LOG.info("instagram attach mode using cdp", extra={"cdp_url": cdp_url})
                browser = await p.chromium.connect_over_cdp(cdp_url)
                contexts = browser.contexts
                if not contexts:
                    raise RuntimeError("No browser contexts found in attached Chrome session")
                context = contexts[0]
                page = await context.new_page()
                close_context = False
            else:
                if profile_dir is None:
                    raise RuntimeError("missing ig profile dir")
                context = await p.chromium.launch_persistent_context(
                    user_data_dir=str(profile_dir),
                    channel="chrome",
                    headless=False,
                )
                page = context.pages[0] if context.pages else await context.new_page()
                # Some Chrome profiles spawn an extra about:blank tab; close extras to avoid tab buildup.
                for extra in context.pages:
                    if extra == page:
                        continue
                    with contextlib.suppress(Exception):
                        if (await extra.title()).strip().lower() == "about:blank":
                            await extra.close()
                close_context = True

            try:
                opened = await _open_thread(page, ig_handle)
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
            finally:
                if page is not None:
                    with contextlib.suppress(Exception):
                        await page.close()
                if close_context:
                    with contextlib.suppress(Exception):
                        await context.close()


async def _find_first(page: Any, selectors: list[str]) -> Any:
    for selector in selectors:
        loc = page.locator(selector)
        if await loc.count() > 0:
            return loc.first
    raise RuntimeError("No matching selector found")


async def _open_thread(page: Any, ig_handle: str) -> bool:
    if await _needs_login(page):
        raise RuntimeError("missing ig auth")
    opened = await _open_thread_via_profile_message(page, ig_handle)
    if opened:
        _LOG.info("instagram thread opened via profile message CTA", extra={"ig_handle": ig_handle})
        return True
    _LOG.info("instagram profile CTA path unavailable, trying inbox search", extra={"ig_handle": ig_handle})
    opened = await _open_thread_via_inbox_search(page, ig_handle)
    if not opened and await _needs_login(page):
        raise RuntimeError("missing ig auth")
    if opened:
        _LOG.info("instagram thread opened via inbox search", extra={"ig_handle": ig_handle})
    else:
        _LOG.info("instagram thread not found in inbox search", extra={"ig_handle": ig_handle})
    return opened


async def _open_thread_via_profile_message(page: Any, ig_handle: str) -> bool:
    handle = ig_handle.strip().lstrip("@")
    if not handle:
        return False
    await page.goto(f"https://www.instagram.com/{handle}/", wait_until="domcontentloaded")
    await page.wait_for_timeout(random.randint(1200, 2400))
    await _dismiss_instagram_popups(page)
    try:
        button = await _find_first(page, INSTAGRAM_MESSAGE_BUTTONS)
    except RuntimeError:
        _LOG.info("instagram profile message CTA missing", extra={"ig_handle": ig_handle})
        return False
    await button.click()
    await page.wait_for_timeout(random.randint(1200, 2600))
    await _dismiss_instagram_popups(page)
    # Some profiles show a Message CTA but do not open a writable composer.
    # Treat that as a miss and fallback to inbox search flow.
    has_input = await _has_dm_input(page)
    if not has_input:
        _LOG.info("instagram profile CTA click did not open writable composer", extra={"ig_handle": ig_handle})
    return has_input


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
            _LOG.info("instagram inbox search input not found", extra={"ig_handle": ig_handle})
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
            await _dismiss_instagram_popups(page)
            if await _has_dm_input(page):
                return True
            # Continue scanning if this row did not open a writable thread.
            continue
    _LOG.info("instagram inbox search found no matching thread row", extra={"ig_handle": ig_handle})
    return False


async def _needs_login(page: Any) -> bool:
    try:
        url = (page.url or "").lower()
    except Exception:
        url = ""
    if "instagram.com/accounts/login" in url:
        return True
    with contextlib.suppress(Exception):
        if await page.locator("input[name='username']").count() > 0:
            return True
    with contextlib.suppress(Exception):
        if await page.get_by_role("button", name="Log in").count() > 0:
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


async def _has_dm_input(page: Any) -> bool:
    for selector in INSTAGRAM_DM_INPUTS:
        with contextlib.suppress(Exception):
            if await page.locator(selector).count() > 0:
                return True
    return False


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
