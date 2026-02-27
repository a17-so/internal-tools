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


class AccountRouter:
    def __init__(self, firestore_client: FirestoreClientProto) -> None:
        self._firestore = firestore_client

    def route_all(self) -> RoutedAccounts:
        return RoutedAccounts(
            email=self._firestore.next_account(Platform.EMAIL),
            instagram=self._firestore.next_account(Platform.INSTAGRAM),
            tiktok=self._firestore.next_account(Platform.TIKTOK),
        )
