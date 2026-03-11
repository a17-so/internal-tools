from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from outreach_automation.models import Account, Platform

_LOG = logging.getLogger(__name__)


@dataclass(slots=True)
class RoutedAccounts:
    email: Account | None
    instagram: Account | None
    tiktok: Account | None


class FirestoreClientProto(Protocol):
    def list_eligible_accounts(self, platform: Platform) -> list[Account]: ...
    def claim_account(self, account_id: str, expected_daily_sent: int) -> bool: ...


@dataclass(slots=True)
class AccountRouteTelemetry:
    selected_counts: dict[str, int]
    skipped_counts: dict[str, int]


class AccountRouter:
    def __init__(
        self,
        firestore_client: FirestoreClientProto,
        *,
        email_handle: str | None = None,
        instagram_handle: str | None = None,
        tiktok_handle: str | None = None,
        strict_sender_pinning: bool = True,
        is_account_ready: Callable[[Platform, Account], tuple[bool, str | None]] | None = None,
    ) -> None:
        self._firestore = firestore_client
        self._email_handle = email_handle
        self._instagram_handle = instagram_handle
        self._tiktok_handle = tiktok_handle
        self._strict_sender_pinning = strict_sender_pinning
        self._is_account_ready = is_account_ready
        self._selected_counts: dict[str, int] = {}
        self._skipped_counts: dict[str, int] = {}

    def route(self, platform: Platform) -> Account | None:
        preferred: str | None = None
        if platform == Platform.EMAIL:
            preferred = self._email_handle
        elif platform == Platform.INSTAGRAM:
            preferred = self._instagram_handle
        elif platform == Platform.TIKTOK:
            preferred = self._tiktok_handle
        if preferred:
            return self._route_preferred(platform, preferred)
        return self._route_from_pool(platform)

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

    def telemetry(self) -> AccountRouteTelemetry:
        return AccountRouteTelemetry(
            selected_counts=dict(self._selected_counts),
            skipped_counts=dict(self._skipped_counts),
        )

    def _route_preferred(self, platform: Platform, preferred: str) -> Account | None:
        preferred_norm = preferred.strip().lower()
        eligible = self._firestore.list_eligible_accounts(platform)
        for account in eligible:
            if account.handle.strip().lower() != preferred_norm:
                continue
            if not self._is_ready(platform, account):
                self._bump_skip(f"{platform.value}:preferred_unready")
                return None
            if self._firestore.claim_account(account.id, account.daily_sent):
                self._bump_selected(platform, account.handle)
                return account
            self._bump_skip(f"{platform.value}:preferred_claim_race")
            return None

        if self._strict_sender_pinning:
            self._bump_skip(f"{platform.value}:preferred_unavailable")
            return None
        self._bump_skip(f"{platform.value}:preferred_fallback")
        return self._route_from_pool(platform)

    def _route_from_pool(self, platform: Platform) -> Account | None:
        eligible = self._firestore.list_eligible_accounts(platform)
        if not eligible:
            self._bump_skip(f"{platform.value}:no_eligible")
            return None
        for account in eligible:
            if not self._is_ready(platform, account):
                continue
            if self._firestore.claim_account(account.id, account.daily_sent):
                self._bump_selected(platform, account.handle)
                return account
            self._bump_skip(f"{platform.value}:claim_race")
        self._bump_skip(f"{platform.value}:no_ready")
        return None

    def _is_ready(self, platform: Platform, account: Account) -> bool:
        if self._is_account_ready is None:
            return True
        ready, reason = self._is_account_ready(platform, account)
        if not ready:
            self._bump_skip(f"{platform.value}:unready:{reason or 'unknown'}")
        return ready

    def _bump_selected(self, platform: Platform, handle: str) -> None:
        key = f"{platform.value}:{handle}"
        self._selected_counts[key] = self._selected_counts.get(key, 0) + 1

    def _bump_skip(self, reason: str) -> None:
        self._skipped_counts[reason] = self._skipped_counts.get(reason, 0) + 1
        _LOG.info("account_route_skipped", extra={"reason": reason})
