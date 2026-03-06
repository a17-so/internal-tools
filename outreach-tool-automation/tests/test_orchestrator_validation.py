from typing import Any

from outreach_automation.account_router import RoutedAccounts
from outreach_automation.models import (
    Account,
    AccountStatus,
    ChannelResult,
    LeadRow,
    Platform,
    ScrapeResponse,
)
from outreach_automation.orchestrator import Orchestrator


class FakeSheets:
    def __init__(self) -> None:
        self._statuses: dict[int, str] = {}
        self.cleared_rows: list[int] = []
        self.tracking_rows: list[dict[str, str | None]] = []

    def fetch_unprocessed(self, batch_size: int, row_index: int | None = None) -> list[LeadRow]:
        _ = (batch_size, row_index)
        return [LeadRow(row_index=2, creator_url="https://tiktok.com/@user", creator_tier="Micro", status="")]

    def update_status(self, row_index: int, status: str) -> None:
        self._statuses[row_index] = status

    def clear_creator_link(self, lead: LeadRow) -> None:
        self.cleared_rows.append(lead.row_index)

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
    ) -> None:
        self.tracking_rows.append(
            {
                "category": category,
                "creator_name": creator_name,
                "ig_handle": ig_handle,
                "tiktok_handle": tiktok_handle,
                "email": email,
                "sender_email": sender_email,
                "sender_ig": sender_ig,
                "sender_tiktok": sender_tiktok,
                "status": status,
            }
        )


class FakeScraper:
    def __init__(self) -> None:
        self.last_category: str | None = None

    def scrape(self, payload: Any) -> ScrapeResponse:
        self.last_category = payload.category
        return ScrapeResponse(
            dm_text="hello",
            email_to="test@example.com",
            email_subject="subj",
            email_body_text="body",
            ig_handle="user_ig",
        )


class FakeFirestore:
    def __init__(self) -> None:
        self.jobs: list[tuple[str, Any]] = []
        self.processed_email: set[str] = set()

    def write_job(self, job_id: str, record: Any) -> None:
        self.jobs.append((job_id, record))

    def mark_dead_job(self, job_id: str, reason: str) -> None:
        _ = (job_id, reason)

    def mark_account_cooling(self, account_id: str, cooldown_minutes: int = 60) -> None:
        _ = (account_id, cooldown_minutes)

    def was_processed_url(self, lead_url: str) -> bool:
        _ = lead_url
        return False

    def was_processed_email(self, email_to: str) -> bool:
        return email_to.lower() in self.processed_email


class FakeRouter:
    def route_all(self) -> RoutedAccounts:
        return self.route_selected(enable_email=True, enable_instagram=True, enable_tiktok=True)

    def route_selected(
        self,
        *,
        enable_email: bool,
        enable_instagram: bool,
        enable_tiktok: bool,
    ) -> RoutedAccounts:
        return RoutedAccounts(
            email=Account(
                id="e1",
                platform=Platform.EMAIL,
                handle="ethan@a17.so",
                status=AccountStatus.ACTIVE,
                daily_sent=0,
                daily_limit=100,
            )
            if enable_email
            else None,
            instagram=Account(
                id="i1",
                platform=Platform.INSTAGRAM,
                handle="@ethan",
                status=AccountStatus.ACTIVE,
                daily_sent=0,
                daily_limit=25,
            )
            if enable_instagram
            else None,
            tiktok=Account(
                id="t1",
                platform=Platform.TIKTOK,
                handle="@ethan",
                status=AccountStatus.ACTIVE,
                daily_sent=0,
                daily_limit=40,
            )
            if enable_tiktok
            else None,
        )


class FakeEmailSender:
    def send(
        self,
        to_email: str | None,
        subject: str | None,
        body: str | None,
        account: Any,
        *,
        dry_run: bool,
    ) -> ChannelResult:
        _ = (to_email, subject, body, account, dry_run)
        return ChannelResult(status="sent")


class FakeIgSender:
    def send(
        self,
        ig_handle: str | None,
        dm_text: str,
        account: Any,
        *,
        dry_run: bool,
    ) -> ChannelResult:
        _ = (ig_handle, dm_text, account, dry_run)
        return ChannelResult(status="sent")


class FakeTiktokSender:
    def send(
        self,
        creator_url: str,
        dm_text: str,
        account: Any,
        *,
        dry_run: bool,
    ) -> ChannelResult:
        _ = (creator_url, dm_text, account, dry_run)
        return ChannelResult(status="sent")


class FailingIgSender:
    def send(
        self,
        ig_handle: str | None,
        dm_text: str,
        account: Any,
        *,
        dry_run: bool,
    ) -> ChannelResult:
        _ = (ig_handle, dm_text, account, dry_run)
        return ChannelResult(status="failed", error_code="ig_send_failed")


class FailingEmailSender:
    def send(
        self,
        to_email: str | None,
        subject: str | None,
        body: str | None,
        account: Any,
        *,
        dry_run: bool,
    ) -> ChannelResult:
        _ = (to_email, subject, body, account, dry_run)
        return ChannelResult(status="failed", error_code="email_send_failed")


class FailingTiktokSender:
    def send(
        self,
        creator_url: str,
        dm_text: str,
        account: Any,
        *,
        dry_run: bool,
    ) -> ChannelResult:
        _ = (creator_url, dm_text, account, dry_run)
        return ChannelResult(status="failed", error_code="tiktok_send_failed")


def test_missing_tier_fails_validation() -> None:
    sheets = FakeSheets()
    sheets.fetch_unprocessed = lambda batch_size, row_index=None: [  # type: ignore[method-assign]
        LeadRow(row_index=2, creator_url="https://tiktok.com/@user", creator_tier="", status="")
    ]
    firestore = FakeFirestore()
    scraper = FakeScraper()

    orchestrator = Orchestrator(
        sheets_client=sheets,
        scrape_client=scraper,
        firestore_client=firestore,
        account_router=FakeRouter(),
        email_sender=FakeEmailSender(),
        ig_sender=FakeIgSender(),
        tiktok_sender=FakeTiktokSender(),
        sender_profile="ethan",
        scrape_app="regen",
    )

    result = orchestrator.run(batch_size=1, dry_run=True)
    assert result.failed == 1
    assert sheets._statuses[2] == "failed_missing_tier"
    assert sheets.cleared_rows == [2]
    assert sheets.tracking_rows == []
    assert scraper.last_category is None
    assert len(firestore.jobs) == 1
    assert result.failed_tiktok_links == []


def test_partial_failure_does_not_mark_link_error_when_any_channel_sent() -> None:
    sheets = FakeSheets()
    firestore = FakeFirestore()
    scraper = FakeScraper()

    orchestrator = Orchestrator(
        sheets_client=sheets,
        scrape_client=scraper,
        firestore_client=firestore,
        account_router=FakeRouter(),
        email_sender=FakeEmailSender(),
        ig_sender=FailingIgSender(),
        tiktok_sender=FakeTiktokSender(),
        sender_profile="ethan",
        scrape_app="regen",
    )

    result = orchestrator.run(batch_size=1, dry_run=False)
    assert result.processed == 1
    assert sheets._statuses[2] == "Processed"
    assert sheets.cleared_rows == [2]
    assert len(sheets.tracking_rows) == 1
    assert sheets.tracking_rows[0]["sender_email"] == "ethan@a17.so"
    assert result.failed_tiktok_links == []


def test_full_failure_clears_link_and_tracks_tiktok_failure() -> None:
    sheets = FakeSheets()
    firestore = FakeFirestore()
    scraper = FakeScraper()

    orchestrator = Orchestrator(
        sheets_client=sheets,
        scrape_client=scraper,
        firestore_client=firestore,
        account_router=FakeRouter(),
        email_sender=FailingEmailSender(),
        ig_sender=FailingIgSender(),
        tiktok_sender=FailingTiktokSender(),
        sender_profile="ethan",
        scrape_app="regen",
    )

    result = orchestrator.run(batch_size=1, dry_run=False)
    assert result.failed == 1
    assert sheets._statuses[2].startswith("failed_")
    assert sheets.cleared_rows == [2]
    assert sheets.tracking_rows == []
    assert result.failed_tiktok_links == ["https://tiktok.com/@user"]


def test_invalid_tier_fails_validation() -> None:
    sheets = FakeSheets()
    sheets.fetch_unprocessed = lambda batch_size, row_index=None: [  # type: ignore[method-assign]
        LeadRow(row_index=2, creator_url="https://tiktok.com/@user", creator_tier="invalid-tier", status="")
    ]
    firestore = FakeFirestore()
    scraper = FakeScraper()

    orchestrator = Orchestrator(
        sheets_client=sheets,
        scrape_client=scraper,
        firestore_client=firestore,
        account_router=FakeRouter(),
        email_sender=FakeEmailSender(),
        ig_sender=FakeIgSender(),
        tiktok_sender=FakeTiktokSender(),
        sender_profile="ethan",
        scrape_app="regen",
    )

    result = orchestrator.run(batch_size=1, dry_run=True)
    assert result.failed == 1
    assert sheets._statuses[2] == "failed_invalid_tier"
    assert sheets.cleared_rows == [2]
    assert sheets.tracking_rows == []
    assert scraper.last_category is None
    assert result.failed_tiktok_links == []


def test_email_skips_when_address_already_contacted() -> None:
    sheets = FakeSheets()
    firestore = FakeFirestore()
    firestore.processed_email.add("test@example.com")
    scraper = FakeScraper()

    orchestrator = Orchestrator(
        sheets_client=sheets,
        scrape_client=scraper,
        firestore_client=firestore,
        account_router=FakeRouter(),
        email_sender=FakeEmailSender(),
        ig_sender=FakeIgSender(),
        tiktok_sender=FakeTiktokSender(),
        sender_profile="ethan",
        scrape_app="regen",
    )

    result = orchestrator.run(batch_size=1, dry_run=False)
    assert result.processed == 1
    assert len(firestore.jobs) == 1
    record = firestore.jobs[0][1]
    assert record.email_status.status == "skipped"
    assert record.email_status.error_code == "email_already_contacted"
