from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from outreach_automation.models import Account, Platform, Tier

_LOG = logging.getLogger(__name__)


@dataclass(slots=True)
class RoutedAccounts:
    email: Account | None
    instagram: Account | None
    tiktok: Account | None
    tiktok_route_error: str | None = None


class FirestoreClientProto(Protocol):
    def list_eligible_accounts(self, platform: Platform) -> list[Account]: ...
    def list_active_accounts(self, platform: Platform) -> list[Account]: ...
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
        tiktok_fill_then_cycle: bool = False,
        is_account_ready: Callable[[Platform, Account], tuple[bool, str | None]] | None = None,
    ) -> None:
        self._firestore = firestore_client
        self._email_handle = email_handle
        self._instagram_handle = instagram_handle
        self._tiktok_handle = tiktok_handle
        self._strict_sender_pinning = strict_sender_pinning
        self._tiktok_fill_then_cycle = tiktok_fill_then_cycle
        self._is_account_ready = is_account_ready
        self._selected_counts: dict[str, int] = {}
        self._skipped_counts: dict[str, int] = {}
        self._tt_round_robin_cursor = 0

    _TT_HANDLE_BY_TIER: dict[Tier, tuple[str, ...]] = {
        Tier.MACRO: ("@regen.app",),
        Tier.AI_INFLUENCER: ("@abhaychebium",),
        Tier.MICRO: ("@advaithakella", "@ekam_m3hat"),
        Tier.SUBMICRO: ("@advaithakella", "@ekam_m3hat"),
        Tier.AMBASSADOR: ("@advaithakella", "@ekam_m3hat"),
        Tier.THEMEPAGE: ("@advaithakella", "@ekam_m3hat"),
    }

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
        tiktok_tier: Tier | None = None,
    ) -> RoutedAccounts:
        tiktok = None
        tiktok_route_error = None
        if enable_tiktok:
            tiktok, tiktok_route_error = self._route_tiktok_by_tier(tiktok_tier=tiktok_tier)
        return RoutedAccounts(
            email=self.route(Platform.EMAIL) if enable_email else None,
            instagram=self.route(Platform.INSTAGRAM) if enable_instagram else None,
            tiktok=tiktok,
            tiktok_route_error=tiktok_route_error,
        )

    def has_available(self, platform: Platform, *, tiktok_tier: Tier | None = None) -> bool:
        preferred: str | None = None
        if platform == Platform.EMAIL:
            preferred = self._email_handle
        elif platform == Platform.INSTAGRAM:
            preferred = self._instagram_handle
        elif platform == Platform.TIKTOK:
            if tiktok_tier is not None:
                tier_handles = self._TT_HANDLE_BY_TIER.get(tiktok_tier)
                if not tier_handles:
                    return False
                return self._has_available_for_handles(platform=platform, handles=tier_handles)
            preferred = self._tiktok_handle
        eligible = self._firestore.list_eligible_accounts(platform)
        if preferred:
            preferred_norm = preferred.strip().lower()
            preferred_eligible = [acc for acc in eligible if acc.handle.strip().lower() == preferred_norm]
            if self._strict_sender_pinning:
                return any(self._is_ready(platform, account) for account in preferred_eligible)
            if preferred_eligible:
                return any(self._is_ready(platform, account) for account in preferred_eligible)
        return any(self._is_ready(platform, account) for account in eligible)

    def _route_tiktok_by_tier(self, *, tiktok_tier: Tier | None) -> tuple[Account | None, str | None]:
        if tiktok_tier is None:
            return self.route(Platform.TIKTOK), None
        handles = self._TT_HANDLE_BY_TIER.get(tiktok_tier)
        if not handles:
            self._bump_skip("tiktok:tier_unmapped")
            return None, "deferred_tiktok_sender_unavailable"
        account, reason = self._route_from_specific_handles(
            platform=Platform.TIKTOK,
            handles=handles,
            reason_prefix=f"tier:{tiktok_tier.value.lower().replace(' ', '_')}",
            round_robin=len(handles) > 1,
        )
        if account is not None:
            return account, None
        return None, reason

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
        if platform == Platform.TIKTOK and self._tiktok_fill_then_cycle:
            eligible = sorted(eligible, key=lambda account: account.id)
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

    def _route_from_specific_handles(
        self,
        *,
        platform: Platform,
        handles: tuple[str, ...],
        reason_prefix: str,
        round_robin: bool,
    ) -> tuple[Account | None, str]:
        normalized_handles = tuple(self._normalize_handle(handle) for handle in handles)
        eligible_all = self._firestore.list_eligible_accounts(platform)
        active_all = self._firestore.list_active_accounts(platform)
        eligible = [acc for acc in eligible_all if self._normalize_handle(acc.handle) in normalized_handles]
        active = [acc for acc in active_all if self._normalize_handle(acc.handle) in normalized_handles]
        if not active:
            self._bump_skip(f"{platform.value}:{reason_prefix}:unavailable")
            return None, "deferred_tiktok_sender_unavailable"
        if not eligible:
            self._bump_skip(f"{platform.value}:{reason_prefix}:capped")
            return None, "deferred_tiktok_sender_capped"

        account_order = self._ordered_candidates(
            accounts=eligible,
            handles=normalized_handles,
            round_robin=round_robin,
        )
        for account in account_order:
            if not self._is_ready(platform, account):
                continue
            if self._firestore.claim_account(account.id, account.daily_sent):
                self._bump_selected(platform, account.handle)
                return account, ""
            self._bump_skip(f"{platform.value}:{reason_prefix}:claim_race")
        self._bump_skip(f"{platform.value}:{reason_prefix}:unavailable")
        return None, "deferred_tiktok_sender_unavailable"

    def _ordered_candidates(
        self,
        *,
        accounts: list[Account],
        handles: tuple[str, ...],
        round_robin: bool,
    ) -> list[Account]:
        by_handle = {self._normalize_handle(account.handle): account for account in accounts}
        selected: list[Account] = []
        for handle in handles:
            account = by_handle.get(handle)
            if account is not None:
                selected.append(account)
        if not round_robin or len(selected) <= 1:
            return selected
        start = self._tt_round_robin_cursor % len(selected)
        self._tt_round_robin_cursor += 1
        return selected[start:] + selected[:start]

    def _has_available_for_handles(self, *, platform: Platform, handles: tuple[str, ...]) -> bool:
        normalized_handles = {self._normalize_handle(handle) for handle in handles}
        eligible = self._firestore.list_eligible_accounts(platform)
        for account in eligible:
            if self._normalize_handle(account.handle) not in normalized_handles:
                continue
            if self._is_ready(platform, account):
                return True
        return False

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

    @staticmethod
    def _normalize_handle(handle: str) -> str:
        normalized = (handle or "").strip().lower()
        if normalized and not normalized.startswith("@"):
            normalized = f"@{normalized}"
        return normalized
