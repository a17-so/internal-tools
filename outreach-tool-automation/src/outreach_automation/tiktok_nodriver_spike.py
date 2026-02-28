from __future__ import annotations

import argparse
import re
from typing import Any

from outreach_automation.models import Platform
from outreach_automation.session_manager import SessionManager
from outreach_automation.settings import load_settings

TIKTOK_MESSAGE_BUTTON_TEXTS = ("Message", "Send message")
TIKTOK_INPUT_SELECTORS = (
    "div[contenteditable='true'][role='textbox']",
    "div[contenteditable='true']",
    "textarea",
)
TIKTOK_SEND_BUTTON_SELECTORS = (
    "button[type='submit']",
    "button[data-e2e='dm-send']",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Experimental TikTok sender using Nodriver")
    sub = parser.add_subparsers(dest="command", required=True)

    bootstrap = sub.add_parser("bootstrap", help="Open persistent profile and complete manual login")
    bootstrap.add_argument("--account-handle", required=True)
    bootstrap.add_argument("--dotenv-path", type=str, default=None)

    send = sub.add_parser("send-test", help="Send one TikTok DM using existing profile")
    send.add_argument("--account-handle", required=True)
    send.add_argument("--creator-url", required=True)
    send.add_argument("--message", required=True)
    send.add_argument("--dotenv-path", type=str, default=None)

    args = parser.parse_args()
    settings = load_settings(dotenv_path=getattr(args, "dotenv_path", None))
    manager = SessionManager(settings.ig_profile_dir, settings.tiktok_profile_dir)

    if args.command == "bootstrap":
        return _run_bootstrap(account_handle=args.account_handle, session_manager=manager)
    return _run_send_test(
        account_handle=args.account_handle,
        creator_url=args.creator_url,
        message=args.message,
        session_manager=manager,
    )


def _run_bootstrap(account_handle: str, session_manager: SessionManager) -> int:
    profile_dir = session_manager.profile_dir_for(Platform.TIKTOK, account_handle)
    profile_dir.mkdir(parents=True, exist_ok=True)
    start_url = f"https://www.tiktok.com/{_normalize_tiktok_path(account_handle)}"

    print(f"[nodriver-spike] bootstrap handle={account_handle}")
    print(f"[nodriver-spike] profile_dir={profile_dir}")
    print(f"[nodriver-spike] opening={start_url}")

    uc: Any = _import_nodriver()

    async def _main() -> None:
        browser = await uc.start(headless=False, user_data_dir=str(profile_dir))
        tab = await browser.get(start_url)
        await tab
        input("Complete TikTok login + 2FA, then press Enter to close this bootstrap session: ")
        await browser.stop()

    uc.loop().run_until_complete(_main())
    return 0


def _run_send_test(
    *,
    account_handle: str,
    creator_url: str,
    message: str,
    session_manager: SessionManager,
) -> int:
    profile_dir = session_manager.profile_dir_for(Platform.TIKTOK, account_handle)
    if not profile_dir.exists():
        raise RuntimeError(
            f"Missing TikTok profile dir for {account_handle}: {profile_dir}. "
            "Run bootstrap first."
        )

    target_handle = _extract_tiktok_handle(creator_url)
    if not target_handle:
        raise ValueError(f"Invalid TikTok creator URL: {creator_url}")
    target_url = f"https://www.tiktok.com/@{target_handle}"

    print(f"[nodriver-spike] send-test account={account_handle} target={target_url}")
    print(f"[nodriver-spike] profile_dir={profile_dir}")

    uc: Any = _import_nodriver()

    async def _main() -> None:
        browser = await uc.start(headless=False, user_data_dir=str(profile_dir))
        tab = await browser.get(target_url)
        await tab.sleep(2)

        await _click_message_button(tab)
        await tab.sleep(2)
        input_element = await _find_dm_input(tab)
        await input_element.click()
        await input_element.send_keys(message)

        send_button = await _find_send_button(tab)
        if send_button is not None:
            await send_button.click()
        else:
            # Fallback: Enter key via input.
            await input_element.send_keys("\n")

        await tab.sleep(2)
        print("[nodriver-spike] send attempt completed")
        await browser.stop()

    uc.loop().run_until_complete(_main())
    return 0


async def _click_message_button(tab: Any) -> None:
    for text in TIKTOK_MESSAGE_BUTTON_TEXTS:
        element = await _find_by_text(tab, text)
        if element is not None:
            await element.click()
            return
    raise RuntimeError("Could not find TikTok Message button")


async def _find_dm_input(tab: Any) -> Any:
    for selector in TIKTOK_INPUT_SELECTORS:
        element = await _select(tab, selector)
        if element is not None:
            return element
    raise RuntimeError("Could not find TikTok DM input")


async def _find_send_button(tab: Any) -> Any | None:
    for selector in TIKTOK_SEND_BUTTON_SELECTORS:
        element = await _select(tab, selector)
        if element is not None:
            return element
    text_match = await _find_by_text(tab, "Send")
    return text_match


async def _find_by_text(tab: Any, text: str) -> Any | None:
    try:
        return await tab.find(text, best_match=True, timeout=5)
    except Exception:
        return None


async def _select(tab: Any, selector: str) -> Any | None:
    try:
        return await tab.select(selector, timeout=5)
    except Exception:
        return None


def _extract_tiktok_handle(url: str) -> str | None:
    match = re.search(r"tiktok\.com/@([A-Za-z0-9_.]+)", url)
    if not match:
        return None
    return match.group(1)


def _normalize_tiktok_path(handle_or_path: str) -> str:
    cleaned = handle_or_path.strip()
    if cleaned.startswith("@"):
        return cleaned
    if cleaned.startswith("https://") or cleaned.startswith("http://"):
        handle = _extract_tiktok_handle(cleaned)
        if not handle:
            raise ValueError(f"Could not parse TikTok handle from {cleaned}")
        return f"@{handle}"
    return f"@{cleaned.lstrip('@')}"


def _import_nodriver() -> Any:
    try:
        import nodriver as uc  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "nodriver is not installed. Install with: pip install nodriver"
        ) from exc
    return uc


if __name__ == "__main__":
    raise SystemExit(main())
