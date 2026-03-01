from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from outreach_automation.models import Account, Platform


@dataclass(slots=True)
class RoutedAccounts:
    email: Account | None
    instagram: Account | None
    tiktok: Account | None


class FirestoreClientProto(Protocol):
    def next_account(self, platform: Platform) -> Account | None: ...
    def next_account_for_handle(self, platform: Platform, handle: str) -> Account | None: ...


class AccountRouter:
    def __init__(
        self,
        firestore_client: FirestoreClientProto,
        *,
        email_handle: str | None = None,
        instagram_handle: str | None = None,
        tiktok_handle: str | None = None,
    ) -> None:
        self._firestore = firestore_client
        self._email_handle = email_handle
        self._instagram_handle = instagram_handle
        self._tiktok_handle = tiktok_handle

    def route(self, platform: Platform) -> Account | None:
        preferred: str | None = None
        if platform == Platform.EMAIL:
            preferred = self._email_handle
        elif platform == Platform.INSTAGRAM:
            preferred = self._instagram_handle
        elif platform == Platform.TIKTOK:
            preferred = self._tiktok_handle
        if preferred:
            account = self._firestore.next_account_for_handle(platform, preferred)
            if account is not None:
                return account
        return self._firestore.next_account(platform)

    def route_all(self) -> RoutedAccounts:
        return RoutedAccounts(
            email=self.route(Platform.EMAIL),
            instagram=self.route(Platform.INSTAGRAM),
            tiktok=self.route(Platform.TIKTOK),
        )

    def route_selected(
        self,
        *,
        enable_email: bool,
        enable_instagram: bool,
        enable_tiktok: bool,
    ) -> RoutedAccounts:
        return RoutedAccounts(
            email=self.route(Platform.EMAIL) if enable_email else None,
            instagram=self.route(Platform.INSTAGRAM) if enable_instagram else None,
            tiktok=self.route(Platform.TIKTOK) if enable_tiktok else None,
        )
