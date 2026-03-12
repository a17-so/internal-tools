from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from outreach_automation.account_router import RoutedAccounts
from outreach_automation.clients.local_scraper_client import ProfileNotFoundError
from outreach_automation.models import (
    Account,
    ChannelResult,
    JobRecord,
    LeadRow,
    Platform,
    ScrapePayload,
    ScrapeResponse,
)
from outreach_automation.status_mapper import final_sheet_status
from outreach_automation.tier_resolver import (
    InvalidTierError,
    MissingTierError,
    UnsupportedTierDeferredError,
    resolve_tier,
)

_LOG = logging.getLogger(__name__)


class SheetsClientProto(Protocol):
    def fetch_unprocessed(self, batch_size: int, row_index: int | None = None) -> list[LeadRow]: ...
    def update_status(self, row_index: int, status: str) -> None: ...
    def clear_creator_link(self, lead: LeadRow) -> None: ...
    def append_outreach_tracking_row(
        self,
        *,
        category: str,
        creator_name: str | None,
        ig_handle: str | None,
        tiktok_handle: str | None,
        email: str | None,
        sender_email: str | None,
        sender_ig: str | None,
        sender_tiktok: str | None,
        status: str = "Sent",
    ) -> None: ...


class ScraperClientProto(Protocol):
    def scrape(self, payload: ScrapePayload) -> ScrapeResponse: ...


class FirestoreClientProto(Protocol):
    def was_processed_url(self, lead_url: str) -> bool: ...
    def was_processed_email(self, email_to: str) -> bool: ...
    def mark_account_cooling(self, account_id: str, cooldown_minutes: int = 60) -> None: ...
    def mark_dead_job(self, job_id: str, reason: str) -> None: ...
    def write_job(self, job_id: str, record: JobRecord) -> None: ...


class AccountRouterProto(Protocol):
    def route_all(self) -> RoutedAccounts: ...
    def has_available(self, platform: Platform) -> bool: ...
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
    failed_tiktok_links: list[str]
    tracking_append_failed_links: list[str]
    lead_summaries: list[LeadRunSummary]


@dataclass(slots=True)
class LeadRunSummary:
    row_index: int
    url: str
    final_status: str
    sender_email: str | None
    sender_ig: str | None
    sender_tiktok: str | None
    email_status: str
    email_error: str | None
    ig_status: str
    ig_error: str | None
    tiktok_status: str
    tiktok_error: str | None


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
        stop_when_tiktok_exhausted: bool = False,
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
        self._stop_when_tiktok_exhausted = stop_when_tiktok_exhausted

    def run(self, batch_size: int, dry_run: bool, row_index: int | None = None) -> OrchestratorResult:
        leads = self._sheets.fetch_unprocessed(batch_size=batch_size, row_index=row_index)
        _LOG.info("fetched leads", extra={"count": len(leads)})
        processed = 0
        failed = 0
        skipped = 0
        failed_tiktok_links: list[str] = []
        tracking_append_failed_links: list[str] = []
        lead_summaries: list[LeadRunSummary] = []

        for lead in leads:
            if (
                self._enable_tiktok
                and self._stop_when_tiktok_exhausted
                and not self._router.has_available(Platform.TIKTOK)
            ):
                _LOG.info("stopping run because no TikTok accounts are currently available")
                break
            result, failed_tiktok_link, tracking_append_failed_link, summary = self._process_lead(
                lead=lead,
                dry_run=dry_run,
            )
            if result == "processed":
                processed += 1
            elif result == "skipped":
                skipped += 1
            else:
                failed += 1
            if failed_tiktok_link:
                failed_tiktok_links.append(failed_tiktok_link)
            if tracking_append_failed_link:
                tracking_append_failed_links.append(tracking_append_failed_link)
            if summary is not None:
                lead_summaries.append(summary)

        return OrchestratorResult(
            processed=processed,
            failed=failed,
            skipped=skipped,
            failed_tiktok_links=failed_tiktok_links,
            tracking_append_failed_links=tracking_append_failed_links,
            lead_summaries=lead_summaries,
        )

    def _process_lead(
        self,
        lead: LeadRow,
        dry_run: bool,
    ) -> tuple[str, str | None, str | None, LeadRunSummary | None]:
        if self._dedupe_enabled and self._firestore.was_processed_url(lead.creator_url):
            self._safe_finalize_lead(lead, "skipped_dedupe")
            return (
                "skipped",
                None,
                None,
                LeadRunSummary(
                    row_index=lead.row_index,
                    url=lead.creator_url,
                    final_status="skipped_dedupe",
                    sender_email=None,
                    sender_ig=None,
                    sender_tiktok=None,
                    email_status="skipped",
                    email_error="dedupe",
                    ig_status="skipped",
                    ig_error="dedupe",
                    tiktok_status="skipped",
                    tiktok_error="dedupe",
                ),
            )

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
        creator_name = None
        tiktok_handle = None
        job_error = None
        job_status = "completed"
        tracking_append_failed_link: str | None = None

        try:
            tier = resolve_tier(lead.creator_tier)
            category = tier.value
        except MissingTierError:
            self._safe_finalize_lead(lead, "failed_missing_tier")
            self._write_validation_job(lead, "failed_missing_tier", dry_run)
            return (
                "failed",
                None,
                None,
                LeadRunSummary(
                    row_index=lead.row_index,
                    url=lead.creator_url,
                    final_status="failed_missing_tier",
                    sender_email=None,
                    sender_ig=None,
                    sender_tiktok=None,
                    email_status="skipped",
                    email_error="failed_missing_tier",
                    ig_status="skipped",
                    ig_error="failed_missing_tier",
                    tiktok_status="skipped",
                    tiktok_error="failed_missing_tier",
                ),
            )
        except InvalidTierError:
            self._safe_finalize_lead(lead, "failed_invalid_tier")
            self._write_validation_job(lead, "failed_invalid_tier", dry_run)
            return (
                "failed",
                None,
                None,
                LeadRunSummary(
                    row_index=lead.row_index,
                    url=lead.creator_url,
                    final_status="failed_invalid_tier",
                    sender_email=None,
                    sender_ig=None,
                    sender_tiktok=None,
                    email_status="skipped",
                    email_error="failed_invalid_tier",
                    ig_status="skipped",
                    ig_error="failed_invalid_tier",
                    tiktok_status="skipped",
                    tiktok_error="failed_invalid_tier",
                ),
            )
        except UnsupportedTierDeferredError:
            self._safe_finalize_lead(lead, "skipped_unsupported_tier")
            self._write_validation_job(lead, "skipped_unsupported_tier", dry_run)
            return (
                "skipped",
                None,
                None,
                LeadRunSummary(
                    row_index=lead.row_index,
                    url=lead.creator_url,
                    final_status="skipped_unsupported_tier",
                    sender_email=None,
                    sender_ig=None,
                    sender_tiktok=None,
                    email_status="skipped",
                    email_error="skipped_unsupported_tier",
                    ig_status="skipped",
                    ig_error="skipped_unsupported_tier",
                    tiktok_status="skipped",
                    tiktok_error="skipped_unsupported_tier",
                ),
            )

        if not lead.creator_url.strip():
            self._safe_finalize_lead(lead, "failed_missing_url")
            self._write_validation_job(lead, "failed_missing_url", dry_run)
            return (
                "failed",
                None,
                None,
                LeadRunSummary(
                    row_index=lead.row_index,
                    url=lead.creator_url,
                    final_status="failed_missing_url",
                    sender_email=None,
                    sender_ig=None,
                    sender_tiktok=None,
                    email_status="skipped",
                    email_error="failed_missing_url",
                    ig_status="skipped",
                    ig_error="failed_missing_url",
                    tiktok_status="skipped",
                    tiktok_error="failed_missing_url",
                ),
            )

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
            creator_name = scrape.creator_name
            tiktok_handle = scrape.tiktok_handle

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
            if final_status == "Processed" and not dry_run:
                try:
                    self._sheets.append_outreach_tracking_row(
                        category=category,
                        creator_name=creator_name,
                        ig_handle=scrape.ig_handle,
                        tiktok_handle=tiktok_handle,
                        email=scrape.email_to,
                        sender_email=sender_email,
                        sender_ig=sender_ig,
                        sender_tiktok=sender_tiktok,
                        status="Sent",
                    )
                except Exception:
                    _LOG.exception("failed to append outreach tracking row", extra={"url": lead.creator_url})
                    tracking_append_failed_link = lead.creator_url
            self._safe_finalize_lead(lead, final_status)

            if final_status == "Processed":
                return_value = "processed"
            elif final_status.startswith("pending"):
                return_value = "skipped"
            else:
                return_value = "failed"

            if return_value != "processed":
                job_status = "dead"
                job_error = final_status

        except ProfileNotFoundError as exc:
            final_status = "skipped_profile_not_found"
            _LOG.info(
                "lead skipped because profile was not found",
                extra={"row_index": lead.row_index, "url": lead.creator_url},
            )
            self._safe_finalize_lead(lead, final_status)
            job_error = str(exc)
            job_status = "completed"
            return_value = "skipped"
        except Exception as exc:
            final_status = self._runtime_status_for_exception(exc)
            _LOG.exception(
                "lead processing runtime failure",
                extra={"row_index": lead.row_index, "url": lead.creator_url},
            )
            self._safe_finalize_lead(lead, final_status)
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
        failed_tiktok_link = lead.creator_url if tiktok_result.status == "failed" else None
        summary = LeadRunSummary(
            row_index=lead.row_index,
            url=lead.creator_url,
            final_status=final_status,
            sender_email=sender_email,
            sender_ig=sender_ig,
            sender_tiktok=sender_tiktok,
            email_status=email_result.status,
            email_error=email_result.error_code,
            ig_status=ig_result.status,
            ig_error=ig_result.error_code,
            tiktok_status=tiktok_result.status,
            tiktok_error=tiktok_result.error_code,
        )
        return return_value, failed_tiktok_link, tracking_append_failed_link, summary

    @staticmethod
    def _runtime_status_for_exception(exc: Exception) -> str:
        message = str(exc).lower()
        if "searchapi returned no profile" in message:
            return "skipped_profile_not_found"
        if "missing app template file" in message:
            return "failed_missing_scrape_template"
        if "missing required environment variable" in message:
            return "failed_missing_config"
        return "failed_runtime_error"

    def _safe_update_status(self, row_index: int, status: str) -> None:
        try:
            self._sheets.update_status(row_index, status)
        except Exception:
            _LOG.exception("failed to update sheet status", extra={"row_index": row_index, "status": status})

    def _safe_clear_creator_link(self, lead: LeadRow) -> None:
        try:
            self._sheets.clear_creator_link(lead)
        except Exception:
            _LOG.exception("failed to clear creator link", extra={"row_index": lead.row_index, "url": lead.creator_url})

    def _safe_finalize_lead(self, lead: LeadRow, status: str) -> None:
        finalize = getattr(self._sheets, "finalize_lead", None)
        if callable(finalize):
            try:
                finalize(lead=lead, status=status)
                return
            except Exception:
                _LOG.exception(
                    "failed to finalize lead row in batch update",
                    extra={"row_index": lead.row_index, "url": lead.creator_url, "status": status},
                )
        self._safe_update_status(lead.row_index, status)
        self._safe_clear_creator_link(lead)

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
