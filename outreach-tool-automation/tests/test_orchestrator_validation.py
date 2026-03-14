from typing import Any

from outreach_automation.account_router import RoutedAccounts
from outreach_automation.clients.local_scraper_client import (
    InvalidCreatorUrlError,
    ProfileNotFoundError,
)
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


class FailingAppendSheets(FakeSheets):
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
        _ = (
            category,
            creator_name,
            ig_handle,
            tiktok_handle,
            email,
            sender_email,
            sender_ig,
            sender_tiktok,
            status,
        )
        raise RuntimeError("append failed")


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


class MissingProfileScraper(FakeScraper):
    def scrape(self, payload: Any) -> ScrapeResponse:
        _ = payload
        raise ProfileNotFoundError("SearchAPI returned no profile for @user")


class FakeFirestore:
    def __init__(self) -> None:
        self.jobs: list[tuple[str, Any]] = []
        self.processed_email: set[str] = set()
        self.processed_urls: set[str] = set()

    def write_job(self, job_id: str, record: Any) -> None:
        self.jobs.append((job_id, record))

    def mark_dead_job(self, job_id: str, reason: str) -> None:
        _ = (job_id, reason)

    def mark_account_cooling(self, account_id: str, cooldown_minutes: int = 60) -> None:
        _ = (account_id, cooldown_minutes)

    def was_processed_url(self, lead_url: str) -> bool:
        return lead_url in self.processed_urls

    def was_processed_email(self, email_to: str) -> bool:
        return email_to.lower() in self.processed_email


class FakeRouter:
    def route_all(self) -> RoutedAccounts:
        return self.route_selected(enable_email=True, enable_instagram=True, enable_tiktok=True)

    def has_available(self, platform: Platform, *, tiktok_tier: Any | None = None) -> bool:
        _ = (platform, tiktok_tier)
        return True

    def route_selected(
        self,
        *,
        enable_email: bool,
        enable_instagram: bool,
        enable_tiktok: bool,
        tiktok_tier: Any | None = None,
    ) -> RoutedAccounts:
        _ = tiktok_tier
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
        target_tiktok_url: str | None,
        dm_text: str,
        account: Any,
        *,
        dry_run: bool,
    ) -> ChannelResult:
        _ = (target_tiktok_url, dm_text, account, dry_run)
        return ChannelResult(status="sent")


class CapturingTiktokSender:
    def __init__(self) -> None:
        self.targets: list[str | None] = []

    def send(
        self,
        target_tiktok_url: str | None,
        dm_text: str,
        account: Any,
        *,
        dry_run: bool,
    ) -> ChannelResult:
        _ = (dm_text, account, dry_run)
        self.targets.append(target_tiktok_url)
        if not target_tiktok_url:
            return ChannelResult(status="skipped", error_code="missing_tiktok_from_source_profile")
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
        target_tiktok_url: str | None,
        dm_text: str,
        account: Any,
        *,
        dry_run: bool,
    ) -> ChannelResult:
        _ = (target_tiktok_url, dm_text, account, dry_run)
        return ChannelResult(status="failed", error_code="tiktok_send_failed")


class InstagramNoTiktokScraper(FakeScraper):
    def scrape(self, payload: Any) -> ScrapeResponse:
        _ = payload
        return ScrapeResponse(
            dm_text="hello",
            email_to="test@example.com",
            email_subject="subj",
            email_body_text="body",
            ig_handle="ig_user",
            creator_name="ig_user",
            tiktok_handle=None,
        )


class InstagramWithTiktokScraper(FakeScraper):
    def scrape(self, payload: Any) -> ScrapeResponse:
        _ = payload
        return ScrapeResponse(
            dm_text="hello",
            email_to="test@example.com",
            email_subject="subj",
            email_body_text="body",
            ig_handle="ig_user",
            creator_name="ig_user",
            tiktok_handle="discovered_tt",
        )


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
    assert result.lead_summaries[0].sender_email == "ethan@a17.so"
    assert result.lead_summaries[0].sender_ig == "@ethan"
    assert result.lead_summaries[0].sender_tiktok == "@ethan"
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


def test_deferred_unsupported_tier_is_skipped() -> None:
    sheets = FakeSheets()
    sheets.fetch_unprocessed = lambda batch_size, row_index=None: [  # type: ignore[method-assign]
        LeadRow(row_index=2, creator_url="https://tiktok.com/@user", creator_tier="YT Creator", status="")
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
    assert result.failed == 0
    assert result.skipped == 1
    assert sheets._statuses[2] == "skipped_unsupported_tier"
    assert sheets.cleared_rows == [2]
    assert sheets.tracking_rows == []
    assert scraper.last_category is None
    assert result.failed_tiktok_links == []


def test_missing_profile_is_skipped_and_cleared() -> None:
    sheets = FakeSheets()
    firestore = FakeFirestore()
    scraper = MissingProfileScraper()

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
    assert result.failed == 0
    assert result.skipped == 1
    assert sheets._statuses[2] == "skipped_profile_not_found"
    assert sheets.cleared_rows == [2]
    assert result.lead_summaries[0].final_status == "skipped_profile_not_found"
    assert len(firestore.jobs) == 1
    assert firestore.jobs[0][1].status == "completed"


def test_email_still_sends_when_address_was_already_contacted() -> None:
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
    # Dedupe is intentionally disabled in v1 automation so every raw lead is attempted.
    assert record.email_status.status == "sent"
    assert record.email_status.error_code is None


def test_dedupe_skip_clears_and_marks_row() -> None:
    sheets = FakeSheets()
    firestore = FakeFirestore()
    firestore.processed_urls.add("https://tiktok.com/@user")
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
    assert result.skipped == 1
    assert sheets._statuses[2] == "skipped_dedupe"
    assert sheets.cleared_rows == [2]
    assert scraper.last_category is None


def test_tracking_append_failure_is_reported_but_run_still_processed() -> None:
    sheets = FailingAppendSheets()
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

    result = orchestrator.run(batch_size=1, dry_run=False)
    assert result.processed == 1
    assert result.failed == 0
    assert result.tracking_append_failed_links == ["https://tiktok.com/@user"]


def test_tiktok_tier_deferred_keeps_creator_link_for_retry() -> None:
    class DeferredTiktokRouter(FakeRouter):
        def route_selected(
            self,
            *,
            enable_email: bool,
            enable_instagram: bool,
            enable_tiktok: bool,
            tiktok_tier: Any | None = None,
        ) -> RoutedAccounts:
            _ = (enable_email, enable_instagram, enable_tiktok, tiktok_tier)
            return RoutedAccounts(email=None, instagram=None, tiktok=None, tiktok_route_error="deferred_tiktok_sender_capped")

    sheets = FakeSheets()
    firestore = FakeFirestore()
    scraper = FakeScraper()

    orchestrator = Orchestrator(
        sheets_client=sheets,
        scrape_client=scraper,
        firestore_client=firestore,
        account_router=DeferredTiktokRouter(),
        email_sender=FakeEmailSender(),
        ig_sender=FakeIgSender(),
        tiktok_sender=FakeTiktokSender(),
        sender_profile="ethan",
        scrape_app="regen",
    )

    result = orchestrator.run(batch_size=1, dry_run=False)
    assert result.skipped == 1
    assert result.lead_summaries[0].final_status == "pending_tomorrow"
    assert result.lead_summaries[0].tiktok_error == "deferred_tiktok_sender_capped"
    assert sheets._statuses[2] == "pending_tomorrow"
    assert sheets.cleared_rows == []
    assert len(firestore.jobs) == 1
    assert firestore.jobs[0][1].status == "completed"


def test_instagram_source_without_discovered_tiktok_still_processes_email_and_ig() -> None:
    sheets = FakeSheets()
    sheets.fetch_unprocessed = lambda batch_size, row_index=None: [  # type: ignore[method-assign]
        LeadRow(row_index=2, creator_url="https://www.instagram.com/ig_user", creator_tier="Micro", status="")
    ]
    firestore = FakeFirestore()
    scraper = InstagramNoTiktokScraper()
    tiktok_sender = CapturingTiktokSender()

    orchestrator = Orchestrator(
        sheets_client=sheets,
        scrape_client=scraper,
        firestore_client=firestore,
        account_router=FakeRouter(),
        email_sender=FakeEmailSender(),
        ig_sender=FakeIgSender(),
        tiktok_sender=tiktok_sender,
        sender_profile="ethan",
        scrape_app="regen",
    )

    result = orchestrator.run(batch_size=1, dry_run=False)
    assert result.processed == 1
    assert result.failed == 0
    assert tiktok_sender.targets == []
    assert result.lead_summaries[0].tiktok_error == "missing_tiktok_from_source_profile"
    assert result.lead_summaries[0].sender_tiktok is None
    assert sheets._statuses[2] == "Processed"


def test_instagram_source_with_discovered_tiktok_uses_resolved_target_url() -> None:
    sheets = FakeSheets()
    sheets.fetch_unprocessed = lambda batch_size, row_index=None: [  # type: ignore[method-assign]
        LeadRow(row_index=2, creator_url="https://www.instagram.com/ig_user", creator_tier="Micro", status="")
    ]
    firestore = FakeFirestore()
    scraper = InstagramWithTiktokScraper()
    tiktok_sender = CapturingTiktokSender()

    orchestrator = Orchestrator(
        sheets_client=sheets,
        scrape_client=scraper,
        firestore_client=firestore,
        account_router=FakeRouter(),
        email_sender=FakeEmailSender(),
        ig_sender=FakeIgSender(),
        tiktok_sender=tiktok_sender,
        sender_profile="ethan",
        scrape_app="regen",
    )

    result = orchestrator.run(batch_size=1, dry_run=False)
    assert result.processed == 1
    assert tiktok_sender.targets == ["https://www.tiktok.com/@discovered_tt"]
    assert result.lead_summaries[0].sender_tiktok == "@ethan"


def test_invalid_creator_url_maps_to_specific_status_not_runtime_error() -> None:
    class InvalidUrlScraper(FakeScraper):
        def scrape(self, payload: Any) -> ScrapeResponse:
            _ = payload
            raise InvalidCreatorUrlError("Invalid Instagram URL, could not extract handle: https://www.instagram.com/p/xyz")

    sheets = FakeSheets()
    sheets.fetch_unprocessed = lambda batch_size, row_index=None: [  # type: ignore[method-assign]
        LeadRow(row_index=2, creator_url="https://www.instagram.com/p/xyz", creator_tier="Micro", status="")
    ]
    firestore = FakeFirestore()
    scraper = InvalidUrlScraper()

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
    assert result.failed == 1
    assert sheets._statuses[2] == "failed_invalid_creator_url"
    assert result.lead_summaries[0].final_status == "failed_invalid_creator_url"
