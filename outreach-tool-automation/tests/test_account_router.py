from outreach_automation.account_router import AccountRouter
from outreach_automation.models import Account, AccountStatus, Platform


class FakeFirestore:
    def __init__(self) -> None:
        self._accounts: dict[Platform, list[Account]] = {
            Platform.EMAIL: [
                Account(
                    id="email1",
                    platform=Platform.EMAIL,
                    handle="sender1@a17.so",
                    status=AccountStatus.ACTIVE,
                    daily_sent=0,
                    daily_limit=10,
                )
            ],
            Platform.INSTAGRAM: [],
            Platform.TIKTOK: [
                Account(
                    id="tt1",
                    platform=Platform.TIKTOK,
                    handle="@sender",
                    status=AccountStatus.ACTIVE,
                    daily_sent=1,
                    daily_limit=10,
                ),
                Account(
                    id="tt2",
                    platform=Platform.TIKTOK,
                    handle="@backup",
                    status=AccountStatus.ACTIVE,
                    daily_sent=2,
                    daily_limit=10,
                ),
            ],
        }
        self.claims: list[tuple[str, int]] = []

    def next_account(self, platform: Platform) -> Account | None:  # pragma: no cover - proto compatibility
        accounts = self._accounts.get(platform, [])
        return accounts[0] if accounts else None

    def next_account_for_handle(
        self, platform: Platform, handle: str
    ) -> Account | None:  # pragma: no cover - proto compatibility
        for account in self._accounts.get(platform, []):
            if account.handle.lower() == handle.lower():
                return account
        return None

    def list_eligible_accounts(self, platform: Platform) -> list[Account]:
        return list(self._accounts.get(platform, []))

    def claim_account(self, account_id: str, expected_daily_sent: int) -> bool:
        self.claims.append((account_id, expected_daily_sent))
        for platform, accounts in self._accounts.items():
            for idx, account in enumerate(accounts):
                if account.id != account_id:
                    continue
                if account.daily_sent != expected_daily_sent:
                    return False
                accounts[idx] = Account(
                    id=account.id,
                    platform=platform,
                    handle=account.handle,
                    status=account.status,
                    daily_sent=account.daily_sent + 1,
                    daily_limit=account.daily_limit,
                )
                return True
        return False


def test_route_all() -> None:
    router = AccountRouter(FakeFirestore())
    routed = router.route_all()
    assert routed.email is not None
    assert routed.instagram is None
    assert routed.tiktok is not None


def test_strict_sender_pinning_does_not_fallback() -> None:
    router = AccountRouter(
        FakeFirestore(),
        instagram_handle="@missing",
        strict_sender_pinning=True,
    )
    assert router.route(Platform.INSTAGRAM) is None
    telemetry = router.telemetry()
    assert telemetry.skipped_counts["instagram:preferred_unavailable"] == 1


def test_non_strict_sender_pinning_allows_fallback() -> None:
    router = AccountRouter(
        FakeFirestore(),
        tiktok_handle="@missing",
        strict_sender_pinning=False,
    )
    routed = router.route(Platform.TIKTOK)
    assert routed is not None
    assert routed.handle == "@sender"
    telemetry = router.telemetry()
    assert telemetry.skipped_counts["tiktok:preferred_fallback"] == 1


def test_readiness_filter_skips_unready_and_claims_ready_account() -> None:
    firestore = FakeFirestore()

    def _is_ready(platform: Platform, account: Account) -> tuple[bool, str | None]:
        if platform == Platform.TIKTOK and account.handle == "@sender":
            return False, "missing_session"
        return True, None

    router = AccountRouter(firestore, is_account_ready=_is_ready)
    routed = router.route(Platform.TIKTOK)
    assert routed is not None
    assert routed.handle == "@backup"
    telemetry = router.telemetry()
    assert telemetry.skipped_counts["tiktok:unready:missing_session"] == 1
    assert telemetry.selected_counts["tiktok:@backup"] == 1
