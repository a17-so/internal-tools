from __future__ import annotations

import argparse
import socket
from datetime import UTC, datetime

from outreach_automation.account_router import AccountRouter
from outreach_automation.email_sender import EmailSender
from outreach_automation.firestore_client import FirestoreClient
from outreach_automation.ig_dm import InstagramDmSender
from outreach_automation.local_scraper_client import LocalScrapeClient, LocalScrapeSettings
from outreach_automation.logger import setup_logging
from outreach_automation.models import Account, Platform
from outreach_automation.orchestrator import Orchestrator
from outreach_automation.session_manager import SessionManager
from outreach_automation.settings import Settings, load_settings
from outreach_automation.sheets_client import SheetsClient
from outreach_automation.tiktok_dm import TiktokDmSender


def main() -> int:
    parser = argparse.ArgumentParser(description="Run outreach orchestration once")
    parser.add_argument("--dry-run", action="store_true", help="Do not send messages/emails")
    parser.add_argument("--live", action="store_true", help="Force live mode even if DRY_RUN=true")
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--max-leads", type=int, default=None)
    parser.add_argument("--lead-row-index", type=int, default=None)
    parser.add_argument(
        "--channels",
        type=str,
        default="email,instagram,tiktok",
        help="Comma-separated channels to run: email,instagram,tiktok",
    )
    parser.add_argument(
        "--ignore-dedupe",
        action="store_true",
        help="Process lead even if URL was already completed before (testing only)",
    )
    parser.add_argument("--dotenv-path", type=str, default=None)
    args = parser.parse_args()

    settings = load_settings(dotenv_path=args.dotenv_path)
    setup_logging(settings.log_level)

    effective_batch = args.batch_size or args.max_leads or settings.batch_size
    dry_run = False if args.live else args.dry_run or settings.dry_run
    enabled_channels = _parse_channels(args.channels)

    sheets_client = SheetsClient(
        service_account_path=settings.google_service_account_json,
        sheet_id=settings.google_sheets_id,
        worksheet_name=settings.raw_leads_sheet_name,
        url_column_name=settings.raw_leads_url_column,
        tier_column_name=settings.raw_leads_tier_column,
        status_column_name=settings.raw_leads_status_column,
    )
    firestore_client = FirestoreClient(
        service_account_path=settings.google_service_account_json,
        project_id=settings.firestore_project_id,
    )
    _run_startup_preflight(
        settings=settings,
        firestore_client=firestore_client,
        enabled_channels=enabled_channels,
        dry_run=dry_run,
    )

    holder = f"{socket.gethostname()}:{datetime.now(UTC).isoformat()}"
    acquired = firestore_client.acquire_run_lock(holder=holder, ttl_seconds=settings.run_lock_ttl_seconds)
    if not acquired:
        print("Run lock already held, exiting")
        return 2

    try:
        scrape_client = _build_scrape_client(settings)
        session_manager = SessionManager(settings.ig_profile_dir, settings.tiktok_profile_dir)
        orchestrator = Orchestrator(
            sheets_client=sheets_client,
            scrape_client=scrape_client,
            firestore_client=firestore_client,
            account_router=AccountRouter(firestore_client),
            email_sender=EmailSender(settings),
            ig_sender=InstagramDmSender(session_manager),
            tiktok_sender=TiktokDmSender(
                session_manager,
                attach_mode=settings.tiktok_attach_mode,
                cdp_url=settings.tiktok_cdp_url,
                min_seconds_between_sends=settings.tiktok_min_seconds_between_sends,
            ),
            sender_profile=settings.sender_profile,
            scrape_app=settings.scrape_app,
            enable_email="email" in enabled_channels,
            enable_instagram="instagram" in enabled_channels,
            enable_tiktok="tiktok" in enabled_channels,
            dedupe_enabled=not args.ignore_dedupe,
        )
        result = orchestrator.run(
            batch_size=effective_batch,
            dry_run=dry_run,
            row_index=args.lead_row_index,
        )
        print(
            f"processed={result.processed} failed={result.failed} skipped={result.skipped} "
            f"dry_run={dry_run} channels={','.join(sorted(enabled_channels))}"
        )
        return 0
    finally:
        firestore_client.release_run_lock(holder=holder)


def _build_scrape_client(settings: Settings) -> LocalScrapeClient:
    if not settings.searchapi_key:
        raise ValueError("Local scrape backend requires SEARCHAPI_KEY")
    return LocalScrapeClient(
        LocalScrapeSettings(
            searchapi_key=settings.searchapi_key,
            request_timeout_seconds=settings.searchapi_timeout_seconds,
            same_username_fallback=settings.scrape_same_username_fallback,
            templates_dir=settings.local_templates_dir,
            outreach_apps_json=settings.local_outreach_apps_json,
        )
    )


def _run_startup_preflight(
    *,
    settings: Settings,
    firestore_client: FirestoreClient,
    enabled_channels: set[str],
    dry_run: bool,
) -> None:
    if not settings.local_templates_dir.exists():
        raise ValueError(f"LOCAL_TEMPLATES_DIR does not exist: {settings.local_templates_dir}")
    app_template = settings.local_templates_dir / f"{settings.scrape_app.lower()}.py"
    if not app_template.exists():
        raise ValueError(
            f"Missing app template file: {app_template}. "
            f"Ensure SCRAPE_APP matches a template in LOCAL_TEMPLATES_DIR."
        )
    if not settings.searchapi_key:
        raise ValueError("Missing SEARCHAPI_KEY for local scrape backend.")

    if dry_run:
        return

    session_manager = SessionManager(settings.ig_profile_dir, settings.tiktok_profile_dir)
    if "instagram" in enabled_channels:
        _ensure_account_sessions_exist(
            accounts=firestore_client.list_active_accounts(Platform.INSTAGRAM),
            platform=Platform.INSTAGRAM,
            session_manager=session_manager,
        )
    if "tiktok" in enabled_channels and not settings.tiktok_attach_mode:
        _ensure_account_sessions_exist(
            accounts=firestore_client.list_active_accounts(Platform.TIKTOK),
            platform=Platform.TIKTOK,
            session_manager=session_manager,
        )


def _ensure_account_sessions_exist(
    *,
    accounts: list[Account],
    platform: Platform,
    session_manager: SessionManager,
) -> None:
    missing: list[str] = []
    for account in accounts:
        handle = account.handle
        if not handle:
            continue
        profile_dir = session_manager.profile_dir_for(platform, handle)
        if not profile_dir.exists():
            missing.append(handle)
    if missing:
        joined = ", ".join(sorted(missing))
        raise ValueError(
            f"Missing {platform.value} sessions for active accounts: {joined}. "
            "Run login bootstrap before live sends."
        )


def _parse_channels(raw: str) -> set[str]:
    aliases = {
        "email": "email",
        "mail": "email",
        "ig": "instagram",
        "instagram": "instagram",
        "tt": "tiktok",
        "tiktok": "tiktok",
    }
    requested = {part.strip().lower() for part in raw.split(",") if part.strip()}
    normalized = {aliases[item] for item in requested if item in aliases}
    if not normalized:
        raise ValueError("No valid channels selected. Use email,instagram,tiktok.")
    return normalized


if __name__ == "__main__":
    raise SystemExit(main())
