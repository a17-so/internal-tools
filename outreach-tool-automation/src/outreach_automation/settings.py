from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class GmailAccountConfig:
    email: str
    refresh_token: str


@dataclass(frozen=True, slots=True)
class Settings:
    flask_scrape_url: str
    scrape_app: str
    google_service_account_json: str | None
    google_sheets_id: str
    firestore_project_id: str
    raw_leads_sheet_name: str
    raw_leads_url_column: str | None
    raw_leads_tier_column: str | None
    raw_leads_status_column: str | None
    log_level: str
    batch_size: int
    run_lock_ttl_seconds: int
    sender_profile: str
    default_creator_tier: str
    dry_run: bool
    email_send_enabled: bool
    gmail_client_id: str | None
    gmail_client_secret: str | None
    gmail_accounts: tuple[GmailAccountConfig, ...]
    ig_profile_dir: Path
    tiktok_profile_dir: Path


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def _gmail_accounts() -> tuple[GmailAccountConfig, ...]:
    accounts: list[GmailAccountConfig] = []
    for idx in range(1, 4):
        email = os.getenv(f"GMAIL_ACCOUNT_{idx}_EMAIL", "").strip()
        token = os.getenv(f"GMAIL_ACCOUNT_{idx}_REFRESH_TOKEN", "").strip()
        if email and token:
            accounts.append(GmailAccountConfig(email=email, refresh_token=token))
    return tuple(accounts)


def load_settings(*, dotenv_path: str | None = None) -> Settings:
    if dotenv_path:
        load_dotenv(dotenv_path=dotenv_path)
    else:
        load_dotenv()

    ig_profile_dir = Path(
        os.getenv("IG_PROFILE_DIR", os.getenv("IG_SESSION_DIR", "profiles/instagram"))
    ).resolve()
    tiktok_profile_dir = Path(
        os.getenv("TIKTOK_PROFILE_DIR", os.getenv("TIKTOK_SESSION_DIR", "profiles/tiktok"))
    ).resolve()

    return Settings(
        flask_scrape_url=_required("FLASK_SCRAPE_URL"),
        scrape_app=os.getenv("SCRAPE_APP", "regen").strip() or "regen",
        google_service_account_json=os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip() or None,
        google_sheets_id=_required("GOOGLE_SHEETS_ID"),
        firestore_project_id=_required("FIRESTORE_PROJECT_ID"),
        raw_leads_sheet_name=os.getenv("RAW_LEADS_SHEET_NAME", "Raw Leads"),
        raw_leads_url_column=os.getenv("RAW_LEADS_URL_COLUMN", "").strip() or None,
        raw_leads_tier_column=os.getenv("RAW_LEADS_TIER_COLUMN", "").strip() or None,
        raw_leads_status_column=os.getenv("RAW_LEADS_STATUS_COLUMN", "").strip() or None,
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        batch_size=int(os.getenv("BATCH_SIZE", "100")),
        run_lock_ttl_seconds=int(os.getenv("RUN_LOCK_TTL_SECONDS", "1800")),
        sender_profile=os.getenv("SENDER_PROFILE", "default"),
        default_creator_tier=os.getenv("DEFAULT_CREATOR_TIER", "Submicro"),
        dry_run=os.getenv("DRY_RUN", "false").lower() == "true",
        email_send_enabled=os.getenv("EMAIL_SEND_ENABLED", "true").lower() == "true",
        gmail_client_id=os.getenv("GMAIL_CLIENT_ID"),
        gmail_client_secret=os.getenv("GMAIL_CLIENT_SECRET"),
        gmail_accounts=_gmail_accounts(),
        ig_profile_dir=ig_profile_dir,
        tiktok_profile_dir=tiktok_profile_dir,
    )
