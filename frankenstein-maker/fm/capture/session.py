"""Playwright capture session runner."""
from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List

from playwright.async_api import BrowserContext, Page, async_playwright

from fm.capture.hotkeys import HOTKEY_SCRIPT
from fm.capture.navigation import account_reels_url, normalize_accounts
from fm.capture.store import append_jsonl, read_jsonl
from fm.utils.paths import ensure_dir
from fm.utils.time import now_iso

logger = logging.getLogger(__name__)


class CaptureState:
    def __init__(self, output_path: Path, screenshots_dir: Path, target: int) -> None:
        self.output_path = output_path
        self.screenshots_dir = screenshots_dir
        self.target = target
        existing = read_jsonl(output_path)
        self.count = len(existing)
        self.done = asyncio.Event()


def _read_seed_accounts(seed_file: Path) -> List[str]:
    if not seed_file.exists():
        return []
    lines = [line.strip() for line in seed_file.read_text(encoding="utf-8").splitlines()]
    lines = [line for line in lines if line and not line.startswith("#")]
    return normalize_accounts(lines)


async def _install_bindings(page: Page, state: CaptureState, seed_account: str | None = None) -> None:
    async def capture_binding(source: Any, payload: Dict[str, Any]) -> None:
        capture_id = str(uuid.uuid4())
        ts = now_iso()
        screenshot_path = state.screenshots_dir / f"{capture_id}.jpg"

        try:
            await page.screenshot(path=str(screenshot_path), full_page=False)
        except Exception:
            screenshot_path = Path("")

        row = {
            "capture_id": capture_id,
            "captured_at": ts,
            "platform": "instagram",
            "url": str(payload.get("url") or page.url),
            "seed_account": seed_account or "",
            "notes": "",
            "raw_metrics_text": str(payload.get("metrics_text") or ""),
            "screenshot_path": str(screenshot_path) if screenshot_path else "",
            "page_title": str(payload.get("title") or ""),
        }
        append_jsonl(state.output_path, row)
        state.count += 1
        logger.info("Captured %d/%d: %s", state.count, state.target, row["url"])

        if state.count >= state.target:
            logger.info("Session target reached (%d).", state.target)
            state.done.set()

    async def stop_binding(source: Any, payload: Dict[str, Any]) -> None:
        logger.info("Stop requested from browser hotkey: %s", payload)
        state.done.set()

    try:
        await page.expose_binding("fmCapture", capture_binding)
    except Exception:
        pass
    try:
        await page.expose_binding("fmStopCapture", stop_binding)
    except Exception:
        pass

    await page.add_init_script(HOTKEY_SCRIPT)
    try:
        await page.evaluate(HOTKEY_SCRIPT)
    except Exception:
        pass


async def _open_seed_tabs(context: BrowserContext, state: CaptureState, accounts: List[str]) -> None:
    for idx, account in enumerate(accounts):
        page = await context.new_page()
        await _install_bindings(page, state, seed_account=account)
        url = account_reels_url(account)
        try:
            await page.goto(url, wait_until="domcontentloaded")
        except Exception:
            logger.warning("Could not open %s", url)

        if idx >= 4:
            break


async def run_capture_session(seed_file: Path, output_path: Path, target: int) -> int:
    accounts = _read_seed_accounts(seed_file)
    screenshots_dir = output_path.parent / "screenshots"
    ensure_dir(screenshots_dir)

    state = CaptureState(output_path=output_path, screenshots_dir=screenshots_dir, target=target)
    logger.info("Starting capture session at %d/%d existing captures.", state.count, state.target)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()

        context.on("page", lambda pg: asyncio.create_task(_install_bindings(pg, state)))

        await _open_seed_tabs(context, state, accounts)

        if not accounts:
            page = await context.new_page()
            await _install_bindings(page, state)
            await page.goto("https://www.instagram.com/explore/", wait_until="domcontentloaded")

        logger.info("Press 'c' in the browser to capture current reel, 'q' to stop.")
        await state.done.wait()

        await context.close()
        await browser.close()

    return state.count
