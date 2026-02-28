from __future__ import annotations

import argparse

from outreach_automation.firestore_client import FirestoreClient
from outreach_automation.models import Account, Platform
from outreach_automation.session_manager import SessionManager
from outreach_automation.settings import load_settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap and persist Playwright login sessions")
    parser.add_argument(
        "--platform",
        choices=["all", "instagram", "tiktok"],
        default="all",
        help="Which platform sessions to bootstrap",
    )
    parser.add_argument(
        "--account-handle",
        action="append",
        default=None,
        help="Optional account handle filter. Repeat flag to include multiple handles.",
    )
    parser.add_argument("--dotenv-path", type=str, default=None)
    args = parser.parse_args()

    settings = load_settings(dotenv_path=args.dotenv_path)
    firestore_client = FirestoreClient(
        service_account_path=settings.google_service_account_json,
        project_id=settings.firestore_project_id,
    )
    session_manager = SessionManager(settings.ig_session_dir, settings.tiktok_session_dir)

    platforms: list[Platform]
    if args.platform == "all":
        platforms = [Platform.INSTAGRAM, Platform.TIKTOK]
    elif args.platform == "instagram":
        platforms = [Platform.INSTAGRAM]
    else:
        platforms = [Platform.TIKTOK]

    requested_handles = {h.strip().lower() for h in (args.account_handle or []) if h.strip()}

    bootstrapped = 0
    for platform in platforms:
        accounts = firestore_client.list_active_accounts(platform)
        if requested_handles:
            accounts = [acc for acc in accounts if acc.handle.strip().lower() in requested_handles]
        for account in accounts:
            _bootstrap_account(platform=platform, account=account, session_manager=session_manager)
            bootstrapped += 1

    print(f"bootstrapped_sessions={bootstrapped}")
    return 0


def _bootstrap_account(platform: Platform, account: Account, session_manager: SessionManager) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("playwright not installed") from exc

    session_path = session_manager.path_for(platform, account.handle)
    start_url = _start_url(platform, account.handle)
    print(f"\n[bootstrap] platform={platform.value} handle={account.handle}")
    print(f"[bootstrap] opening {start_url}")
    print(f"[bootstrap] session_file={session_path}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        if session_path.exists():
            context = browser.new_context(storage_state=str(session_path))
        else:
            context = browser.new_context()
        page = context.new_page()
        page.goto(start_url, wait_until="domcontentloaded")
        input("Complete login + 2FA in the opened browser, then press Enter here to save session: ")
        session_path.parent.mkdir(parents=True, exist_ok=True)
        context.storage_state(path=str(session_path))
        context.close()
        browser.close()


def _start_url(platform: Platform, handle: str) -> str:
    clean_handle = handle.strip().lstrip("@")
    if platform is Platform.INSTAGRAM:
        return f"https://www.instagram.com/{clean_handle}/"
    if platform is Platform.TIKTOK:
        return f"https://www.tiktok.com/@{clean_handle}"
    raise ValueError(f"Unsupported platform: {platform.value}")


if __name__ == "__main__":
    raise SystemExit(main())
