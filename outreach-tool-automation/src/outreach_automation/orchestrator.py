from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from outreach_automation.account_router import RoutedAccounts
from outreach_automation.models import (
    Account,
    ChannelResult,
    JobRecord,
    LeadRow,
    ScrapePayload,
    ScrapeResponse,
)
from outreach_automation.status_mapper import final_sheet_status
from outreach_automation.tier_resolver import InvalidTierError, MissingTierError, resolve_tier

_LOG = logging.getLogger(__name__)


class SheetsClientProto(Protocol):
    def fetch_unprocessed(self, batch_size: int, row_index: int | None = None) -> list[LeadRow]: ...
    def update_status(self, row_index: int, status: str) -> None: ...
    def clear_creator_link(self, lead: LeadRow) -> None: ...
    def mark_creator_link_error(self, lead: LeadRow) -> None: ...
    def clear_creator_link_error(self, lead: LeadRow) -> None: ...


class ScraperClientProto(Protocol):
    def scrape(self, payload: ScrapePayload) -> ScrapeResponse: ...


class FirestoreClientProto(Protocol):
    def was_processed_url(self, lead_url: str) -> bool: ...
    def mark_account_cooling(self, account_id: str, cooldown_minutes: int = 60) -> None: ...
    def mark_dead_job(self, job_id: str, reason: str) -> None: ...
    def write_job(self, job_id: str, record: JobRecord) -> None: ...


class AccountRouterProto(Protocol):
    def route_all(self) -> RoutedAccounts: ...
    def route_selected(
        self,
        *,
        enable_email: bool,
        enable_instagram: bool,
        enable_tiktok: bool,
    ) -> RoutedAccounts: ...


class EmailSenderProto(Protocol):
    def send(
        self,
        to_email: str | None,
        subject: str | None,
        body: str | None,
        account: Account | None,
        *,
        dry_run: bool,
    ) -> ChannelResult: ...


class InstagramSenderProto(Protocol):
    def send(
        self,
        ig_handle: str | None,
        dm_text: str,
        account: Account | None,
        *,
        dry_run: bool,
    ) -> ChannelResult: ...


class TiktokSenderProto(Protocol):
    def send(
        self,
        creator_url: str,
        dm_text: str,
        account: Account | None,
        *,
        dry_run: bool,
    ) -> ChannelResult: ...


@dataclass(slots=True)
class OrchestratorResult:
    processed: int
    failed: int
    skipped: int


class Orchestrator:
    def __init__(
        self,
        sheets_client: SheetsClientProto,
        scrape_client: ScraperClientProto,
        firestore_client: FirestoreClientProto,
        account_router: AccountRouterProto,
        email_sender: EmailSenderProto,
        ig_sender: InstagramSenderProto,
        tiktok_sender: TiktokSenderProto,
        sender_profile: str,
        scrape_app: str = "regen",
        enable_email: bool = True,
        enable_instagram: bool = True,
        enable_tiktok: bool = True,
        dedupe_enabled: bool = True,
    ) -> None:
        self._sheets = sheets_client
        self._scraper = scrape_client
        self._firestore = firestore_client
        self._router = account_router
        self._email_sender = email_sender
        self._ig_sender = ig_sender
        self._tiktok_sender = tiktok_sender
        self._sender_profile = sender_profile
        self._scrape_app = scrape_app
        self._enable_email = enable_email
        self._enable_instagram = enable_instagram
        self._enable_tiktok = enable_tiktok
        self._dedupe_enabled = dedupe_enabled

    def run(self, batch_size: int, dry_run: bool, row_index: int | None = None) -> OrchestratorResult:
        leads = self._sheets.fetch_unprocessed(batch_size=batch_size, row_index=row_index)
        _LOG.info("fetched leads", extra={"count": len(leads)})
        processed = 0
        failed = 0
        skipped = 0

        for lead in leads:
            result = self._process_lead(lead=lead, dry_run=dry_run)
            if result == "processed":
                processed += 1
            elif result == "skipped":
                skipped += 1
            else:
                failed += 1

        return OrchestratorResult(processed=processed, failed=failed, skipped=skipped)

    def _process_lead(self, lead: LeadRow, dry_run: bool) -> str:
        if self._dedupe_enabled and self._firestore.was_processed_url(lead.creator_url):
            return "skipped"

        now = datetime.now(UTC)
        email_result = ChannelResult(status="skipped", error_code="not_attempted")
        ig_result = ChannelResult(status="skipped", error_code="not_attempted")
        tiktok_result = ChannelResult(status="skipped", error_code="not_attempted")
        sender_email = None
        sender_ig = None
        sender_tiktok = None
        category = ""
        ig_handle = None
        email_to = None
        job_error = None
        job_status = "completed"

        try:
            tier = resolve_tier(lead.creator_tier)
            category = tier.value
        except MissingTierError:
            self._sheets.update_status(lead.row_index, "failed_missing_tier")
            self._write_validation_job(lead, "failed_missing_tier", dry_run)
            self._sheets.mark_creator_link_error(lead)
            return "failed"
        except InvalidTierError:
            self._sheets.update_status(lead.row_index, "failed_invalid_tier")
            self._write_validation_job(lead, "failed_invalid_tier", dry_run)
            self._sheets.mark_creator_link_error(lead)
            return "failed"

        if not lead.creator_url.strip():
            self._sheets.update_status(lead.row_index, "failed_missing_url")
            self._write_validation_job(lead, "failed_missing_url", dry_run)
            return "failed"

        try:
            scrape = self._scraper.scrape(
                ScrapePayload(
                    app=self._scrape_app,
                    creator_url=lead.creator_url,
                    category=category,
                    sender_profile=self._sender_profile,
                )
            )
            email_to = scrape.email_to
            ig_handle = scrape.ig_handle

            routed = self._router.route_selected(
                enable_email=self._enable_email,
                enable_instagram=self._enable_instagram,
                enable_tiktok=self._enable_tiktok,
            )
            sender_email = routed.email.handle if routed.email else None
            sender_ig = routed.instagram.handle if routed.instagram else None
            sender_tiktok = routed.tiktok.handle if routed.tiktok else None

            if self._enable_tiktok:
                tiktok_result = self._tiktok_sender.send(
                    creator_url=lead.creator_url,
                    dm_text=scrape.dm_text,
                    account=routed.tiktok,
                    dry_run=dry_run,
                )
            else:
                tiktok_result = ChannelResult(status="skipped", error_code="channel_disabled")

            if self._enable_instagram:
                ig_result = self._ig_sender.send(
                    ig_handle=scrape.ig_handle,
                    dm_text=scrape.dm_text,
                    account=routed.instagram,
                    dry_run=dry_run,
                )
            else:
                ig_result = ChannelResult(status="skipped", error_code="channel_disabled")

            if self._enable_email:
                email_result = self._email_sender.send(
                    to_email=scrape.email_to,
                    subject=scrape.email_subject,
                    body=scrape.email_body_text,
                    account=routed.email,
                    dry_run=dry_run,
                )
            else:
                email_result = ChannelResult(status="skipped", error_code="channel_disabled")

            if routed.instagram and ig_result.error_code == "ig_blocked":
                self._firestore.mark_account_cooling(routed.instagram.id)
            if routed.tiktok and tiktok_result.error_code == "tiktok_blocked":
                self._firestore.mark_account_cooling(routed.tiktok.id)

            final_status = final_sheet_status(email_result, ig_result, tiktok_result)
            self._sheets.update_status(lead.row_index, final_status)
            if final_status == "Processed":
                self._sheets.clear_creator_link(lead)
            elif final_status.startswith("failed"):
                if _any_channel_sent(email_result, ig_result, tiktok_result):
                    self._sheets.clear_creator_link_error(lead)
                else:
                    self._sheets.mark_creator_link_error(lead)

            if final_status == "Processed":
                return_value = "processed"
            elif final_status.startswith("pending"):
                return_value = "skipped"
            else:
                return_value = "failed"

            if return_value != "processed":
                job_status = "dead"
                job_error = final_status

        except Exception as exc:
            final_status = "failed_internal_error"
            self._sheets.update_status(lead.row_index, final_status)
            if not _any_channel_sent(email_result, ig_result, tiktok_result):
                self._sheets.mark_creator_link_error(lead)
            job_error = str(exc)
            job_status = "dead"
            self._firestore.mark_dead_job(str(uuid4()), reason=str(exc))
            return_value = "failed"

        completed = datetime.now(UTC)
        record = JobRecord(
            lead_url=lead.creator_url,
            category=category,
            email_status=email_result,
            ig_status=ig_result,
            tiktok_status=tiktok_result,
            created_at=now,
            completed_at=completed,
            sender_email=sender_email,
            sender_ig=sender_ig,
            sender_tiktok=sender_tiktok,
            dry_run=dry_run,
            ig_handle=ig_handle,
            email_to=email_to,
            error=job_error,
            status=job_status,
        )
        self._firestore.write_job(str(uuid4()), record)
        return return_value

    def _write_validation_job(self, lead: LeadRow, status: str, dry_run: bool) -> None:
        now = datetime.now(UTC)
        record = JobRecord(
            lead_url=lead.creator_url,
            category=lead.creator_tier,
            email_status=ChannelResult(status="skipped", error_code=status),
            ig_status=ChannelResult(status="skipped", error_code=status),
            tiktok_status=ChannelResult(status="skipped", error_code=status),
            created_at=now,
            completed_at=now,
            sender_email=None,
            sender_ig=None,
            sender_tiktok=None,
            dry_run=dry_run,
            error=status,
            status="dead",
        )
        self._firestore.write_job(str(uuid4()), record)


def _any_channel_sent(*results: ChannelResult) -> bool:
    return any(result.status == "sent" for result in results)
