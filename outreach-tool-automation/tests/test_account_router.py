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


def test_route_all() -> None:
    router = AccountRouter(FakeFirestore())
    routed = router.route_all()
    assert routed.email is not None
    assert routed.instagram is None
    assert routed.tiktok is not None
