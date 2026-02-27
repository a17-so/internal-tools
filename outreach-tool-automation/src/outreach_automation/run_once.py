from __future__ import annotations

import argparse
import socket
from datetime import UTC, datetime

from outreach_automation.account_router import AccountRouter
from outreach_automation.email_sender import EmailSender
from outreach_automation.firestore_client import FirestoreClient
from outreach_automation.ig_dm import InstagramDmSender
from outreach_automation.logger import setup_logging
from outreach_automation.orchestrator import Orchestrator
from outreach_automation.scraper_client import ScrapeClient
from outreach_automation.session_manager import SessionManager
from outreach_automation.settings import load_settings
from outreach_automation.sheets_client import SheetsClient
from outreach_automation.tiktok_dm import TiktokDmSender


def main() -> int:
    parser = argparse.ArgumentParser(description="Run outreach orchestration once")
    parser.add_argument("--dry-run", action="store_true", help="Do not send messages/emails")
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--max-leads", type=int, default=None)
    parser.add_argument("--lead-row-index", type=int, default=None)
    parser.add_argument("--dotenv-path", type=str, default=None)
    args = parser.parse_args()

    settings = load_settings(dotenv_path=args.dotenv_path)
    setup_logging(settings.log_level)

    effective_batch = args.batch_size or args.max_leads or settings.batch_size
    dry_run = args.dry_run or settings.dry_run

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

    holder = f"{socket.gethostname()}:{datetime.now(UTC).isoformat()}"
    acquired = firestore_client.acquire_run_lock(holder=holder, ttl_seconds=settings.run_lock_ttl_seconds)
    if not acquired:
        print("Run lock already held, exiting")
        return 2

    try:
        session_manager = SessionManager(settings.ig_session_dir, settings.tiktok_session_dir)
        orchestrator = Orchestrator(
            sheets_client=sheets_client,
            scrape_client=ScrapeClient(settings.flask_scrape_url),
            firestore_client=firestore_client,
            account_router=AccountRouter(firestore_client),
            email_sender=EmailSender(settings),
        ig_sender=InstagramDmSender(session_manager),
        tiktok_sender=TiktokDmSender(session_manager),
        sender_profile=settings.sender_profile,
        scrape_app=settings.scrape_app,
        default_creator_tier=settings.default_creator_tier,
    )
        result = orchestrator.run(
            batch_size=effective_batch,
            dry_run=dry_run,
            row_index=args.lead_row_index,
        )
        print(
            f"processed={result.processed} failed={result.failed} skipped={result.skipped} dry_run={dry_run}"
        )
        return 0
    finally:
        firestore_client.release_run_lock(holder=holder)


if __name__ == "__main__":
    raise SystemExit(main())
