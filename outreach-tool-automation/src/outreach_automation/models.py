from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal


class Tier(StrEnum):
    MACRO = "Macro"
    MICRO = "Micro"
    SUBMICRO = "Submicro"
    AMBASSADOR = "Ambassador"
    THEMEPAGE = "Themepage"


class Platform(StrEnum):
    EMAIL = "email"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"


class AccountStatus(StrEnum):
    ACTIVE = "active"
    COOLING = "cooling"
    FLAGGED = "flagged"


ChannelStatus = Literal["sent", "failed", "skipped", "pending_tomorrow"]


@dataclass(slots=True)
class LeadRow:
    row_index: int
    creator_url: str
    creator_tier: str
    status: str = ""
    col_index: int | None = None


@dataclass(slots=True)
class ScrapePayload:
    app: str
    creator_url: str
    category: str
    sender_profile: str


@dataclass(slots=True)
class ScrapeResponse:
    dm_text: str
    email_to: str | None
    email_subject: str | None
    email_body_text: str | None
    ig_handle: str | None


@dataclass(slots=True)
class ChannelResult:
    status: ChannelStatus
    error_code: str | None = None
    error_message: str | None = None


@dataclass(slots=True)
class Account:
    id: str
    platform: Platform
    handle: str
    status: AccountStatus
    daily_sent: int
    daily_limit: int
    last_reset: str | None = None
    cooldown_until: datetime | None = None


@dataclass(slots=True)
class JobRecord:
    lead_url: str
    category: str
    email_status: ChannelResult
    ig_status: ChannelResult
    tiktok_status: ChannelResult
    created_at: datetime
    completed_at: datetime
    sender_email: str | None
    sender_ig: str | None
    sender_tiktok: str | None
    dry_run: bool
    ig_handle: str | None = None
    email_to: str | None = None
    error: str | None = None
    status: str = "completed"
    metadata: dict[str, Any] = field(default_factory=dict)
