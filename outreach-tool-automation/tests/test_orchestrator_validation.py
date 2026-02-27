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

    def fetch_unprocessed(self, batch_size: int, row_index: int | None = None) -> list[LeadRow]:
        _ = (batch_size, row_index)
        return [LeadRow(row_index=2, creator_url="https://tiktok.com/@user", creator_tier="", status="")]

    def update_status(self, row_index: int, status: str) -> None:
        self._statuses[row_index] = status


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

    def write_job(self, job_id: str, record: Any) -> None:
        self.jobs.append((job_id, record))

    def mark_dead_job(self, job_id: str, reason: str) -> None:
        _ = (job_id, reason)

    def mark_account_cooling(self, account_id: str, cooldown_minutes: int = 60) -> None:
        _ = (account_id, cooldown_minutes)

    def was_processed_url(self, lead_url: str) -> bool:
        _ = lead_url
        return False


class FakeRouter:
    def route_all(self) -> RoutedAccounts:
        return RoutedAccounts(
            email=Account(
                id="e1",
                platform=Platform.EMAIL,
                handle="ethan@a17.so",
                status=AccountStatus.ACTIVE,
                daily_sent=0,
                daily_limit=100,
            ),
            instagram=Account(
                id="i1",
                platform=Platform.INSTAGRAM,
                handle="@ethan",
                status=AccountStatus.ACTIVE,
                daily_sent=0,
                daily_limit=25,
            ),
            tiktok=Account(
                id="t1",
                platform=Platform.TIKTOK,
                handle="@ethan",
                status=AccountStatus.ACTIVE,
                daily_sent=0,
                daily_limit=40,
            ),
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


def test_missing_tier_defaults_to_submicro_and_processes() -> None:
    sheets = FakeSheets()
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
        default_creator_tier="Submicro",
    )

    result = orchestrator.run(batch_size=1, dry_run=True)
    assert result.processed == 1
    assert sheets._statuses[2] == "Processed"
    assert scraper.last_category == "Submicro"
    assert len(firestore.jobs) == 1
