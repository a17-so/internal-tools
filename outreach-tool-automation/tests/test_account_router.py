from outreach_automation.account_router import AccountRouter
from outreach_automation.models import Account, AccountStatus, Platform


class FakeFirestore:
    def __init__(self) -> None:
        self._accounts = {
            Platform.EMAIL: Account(
                id="email1",
                platform=Platform.EMAIL,
                handle="sender@a17.so",
                status=AccountStatus.ACTIVE,
                daily_sent=0,
                daily_limit=10,
            ),
            Platform.INSTAGRAM: None,
            Platform.TIKTOK: Account(
                id="tt1",
                platform=Platform.TIKTOK,
                handle="@sender",
                status=AccountStatus.ACTIVE,
                daily_sent=2,
                daily_limit=10,
            ),
        }

    def next_account(self, platform: Platform) -> Account | None:
        return self._accounts.get(platform)

    def next_account_for_handle(self, platform: Platform, handle: str) -> Account | None:
        account = self._accounts.get(platform)
        if account is None:
            return None
        return account if account.handle.lower() == handle.lower() else None


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


def test_non_strict_sender_pinning_allows_fallback() -> None:
    router = AccountRouter(
        FakeFirestore(),
        tiktok_handle="@missing",
        strict_sender_pinning=False,
    )
    routed = router.route(Platform.TIKTOK)
    assert routed is not None
    assert routed.handle == "@sender"
