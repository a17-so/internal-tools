from outreach_automation.account_router import AccountRouter
from outreach_automation.models import Account, AccountStatus, Platform, Tier


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
                    handle="@regenapp",
                    status=AccountStatus.ACTIVE,
                    daily_sent=0,
                    daily_limit=25,
                ),
                Account(
                    id="tt2",
                    platform=Platform.TIKTOK,
                    handle="@abhaychebium",
                    status=AccountStatus.ACTIVE,
                    daily_sent=0,
                    daily_limit=25,
                ),
                Account(
                    id="tt3",
                    platform=Platform.TIKTOK,
                    handle="@advaithakella",
                    status=AccountStatus.ACTIVE,
                    daily_sent=0,
                    daily_limit=25,
                ),
                Account(
                    id="tt4",
                    platform=Platform.TIKTOK,
                    handle="@ekam_m3hat",
                    status=AccountStatus.ACTIVE,
                    daily_sent=0,
                    daily_limit=25,
                ),
            ],
        }
        self.claims: list[tuple[str, int]] = []

    def list_active_accounts(self, platform: Platform) -> list[Account]:
        return list(self._accounts.get(platform, []))

    def list_eligible_accounts(self, platform: Platform) -> list[Account]:
        out: list[Account] = []
        for account in self._accounts.get(platform, []):
            if account.daily_sent < account.daily_limit:
                out.append(account)
        return out

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
    telemetry = router.telemetry()
    assert telemetry.skipped_counts["tiktok:preferred_fallback"] == 1


def test_readiness_filter_skips_unready_and_claims_ready_account() -> None:
    firestore = FakeFirestore()

    def _is_ready(platform: Platform, account: Account) -> tuple[bool, str | None]:
        if platform == Platform.TIKTOK and account.handle == "@regenapp":
            return False, "missing_session"
        return True, None

    router = AccountRouter(firestore, is_account_ready=_is_ready)
    routed = router.route_selected(
        enable_email=False,
        enable_instagram=False,
        enable_tiktok=True,
        tiktok_tier=Tier.MACRO,
    )
    assert routed.tiktok is None
    assert routed.tiktok_route_error == "deferred_tiktok_sender_unavailable"
    telemetry = router.telemetry()
    assert telemetry.skipped_counts["tiktok:unready:missing_session"] == 1


def test_tiktok_tier_routes_macro_to_regen_app() -> None:
    router = AccountRouter(FakeFirestore())
    routed = router.route_selected(
        enable_email=False,
        enable_instagram=False,
        enable_tiktok=True,
        tiktok_tier=Tier.MACRO,
    )
    assert routed.tiktok is not None
    assert routed.tiktok.handle == "@regenapp"
    assert routed.tiktok_route_error is None


def test_tiktok_tier_routes_ai_to_abhay() -> None:
    router = AccountRouter(FakeFirestore())
    routed = router.route_selected(
        enable_email=False,
        enable_instagram=False,
        enable_tiktok=True,
        tiktok_tier=Tier.AI_INFLUENCER,
    )
    assert routed.tiktok is not None
    assert routed.tiktok.handle == "@abhaychebium"
    assert routed.tiktok_route_error is None


def test_tiktok_tier_routes_micro_pool_round_robin() -> None:
    router = AccountRouter(FakeFirestore())
    first = router.route_selected(
        enable_email=False,
        enable_instagram=False,
        enable_tiktok=True,
        tiktok_tier=Tier.MICRO,
    )
    second = router.route_selected(
        enable_email=False,
        enable_instagram=False,
        enable_tiktok=True,
        tiktok_tier=Tier.MICRO,
    )
    assert first.tiktok is not None
    assert second.tiktok is not None
    assert {first.tiktok.handle, second.tiktok.handle} == {"@advaithakella", "@ekam_m3hat"}


def test_tiktok_tier_returns_capped_error_when_tier_pool_is_exhausted() -> None:
    firestore = FakeFirestore()
    for idx, account in enumerate(firestore._accounts[Platform.TIKTOK]):
        if account.handle == "@abhaychebium":
            firestore._accounts[Platform.TIKTOK][idx] = Account(
                id=account.id,
                platform=account.platform,
                handle=account.handle,
                status=account.status,
                daily_sent=account.daily_limit,
                daily_limit=account.daily_limit,
            )
            break

    router = AccountRouter(firestore)
    routed = router.route_selected(
        enable_email=False,
        enable_instagram=False,
        enable_tiktok=True,
        tiktok_tier=Tier.AI_INFLUENCER,
    )
    assert routed.tiktok is None
    assert routed.tiktok_route_error == "deferred_tiktok_sender_capped"


def test_has_available_respects_tier_mapping() -> None:
    router = AccountRouter(FakeFirestore())
    assert router.has_available(Platform.TIKTOK, tiktok_tier=Tier.MACRO) is True
