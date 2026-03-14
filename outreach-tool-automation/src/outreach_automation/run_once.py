from __future__ import annotations

import argparse
import contextlib
import json
import logging
import os
import signal
import socket
import subprocess
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from types import FrameType
from urllib.parse import urlparse

from outreach_automation.account_router import AccountRouter
from outreach_automation.clients.firestore_client import FirestoreClient
from outreach_automation.clients.local_scraper_client import LocalScrapeClient, LocalScrapeSettings
from outreach_automation.clients.sheets_client import SheetsClient
from outreach_automation.logger import setup_logging
from outreach_automation.models import Account, Platform
from outreach_automation.orchestrator import LeadRunSummary, Orchestrator, OrchestratorResult
from outreach_automation.senders.email_sender import EmailSender
from outreach_automation.senders.ig_dm import InstagramDmSender
from outreach_automation.senders.tiktok_dm import TiktokDmSender
from outreach_automation.session_manager import SessionManager
from outreach_automation.settings import Settings, load_settings

_LOG = logging.getLogger(__name__)


def main() -> int:
    _install_signal_handlers()
    parser = argparse.ArgumentParser(description="Run outreach orchestration once")
    parser.add_argument("--dry-run", action="store_true", help="Do not send messages/emails")
    parser.add_argument("--live", action="store_true", help="Force live mode even if DRY_RUN=true")
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--max-leads", type=int, default=None)
    parser.add_argument("--lead-row-index", type=int, default=None)
    parser.add_argument(
        "--channels",
        type=str,
        default="email,instagram,tiktok",
        help="Comma-separated channels to run: email,instagram,tiktok",
    )
    parser.add_argument(
        "--ignore-dedupe",
        action="store_true",
        help="Deprecated; dedupe is disabled by default.",
    )
    parser.add_argument(
        "--verbose-summary",
        action="store_true",
        help="Print per-lead channel outcomes after run",
    )
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="Skip writing JSON run report under logs/run-reports",
    )
    parser.add_argument("--dotenv-path", type=str, default=None)
    args = parser.parse_args()

    settings = load_settings(dotenv_path=args.dotenv_path)
    setup_logging(settings.log_level)
    pid_file = _pid_file_path()
    _write_pid_file(pid_file)

    try:
        started_at = datetime.now(UTC)
        explicit_batch = args.batch_size or args.max_leads
        unbounded_mode = explicit_batch is None and args.lead_row_index is None
        effective_batch = explicit_batch or (settings.unbounded_batch_size if unbounded_mode else settings.batch_size)
        dry_run = False if args.live else args.dry_run or settings.dry_run
        enabled_channels = _parse_channels(args.channels)

        sheets_client = SheetsClient(
            service_account_path=settings.google_service_account_json,
            sheet_id=settings.google_sheets_id,
            worksheet_name=settings.raw_leads_sheet_name,
            url_column_name=settings.raw_leads_url_column,
            tier_column_name=settings.raw_leads_tier_column,
            status_column_name=settings.raw_leads_status_column,
        )
        firestore_client = FirestoreClient(
            service_account_path=settings.google_service_account_json,
            project_id=settings.firestore_project_id,
        )
        _run_startup_preflight(
            settings=settings,
            firestore_client=firestore_client,
            enabled_channels=enabled_channels,
            dry_run=dry_run,
        )

        holder = f"{socket.gethostname()}:{datetime.now(UTC).isoformat()}"
        acquired = firestore_client.acquire_run_lock(holder=holder, ttl_seconds=settings.run_lock_ttl_seconds)
        if not acquired:
            print("Run lock already held, exiting")
            return 2

        try:
            scrape_client = _build_scrape_client(settings)
            session_manager = SessionManager(settings.ig_profile_dir, settings.tiktok_profile_dir)
            readiness_fn = _build_account_readiness_checker(
                settings=settings,
                session_manager=session_manager,
            )
            account_router = AccountRouter(
                firestore_client,
                email_handle=settings.email_sender_handle,
                instagram_handle=settings.instagram_sender_handle,
                tiktok_handle=settings.tiktok_sender_handle,
                strict_sender_pinning=settings.strict_sender_pinning,
                tiktok_fill_then_cycle=settings.tiktok_fill_then_cycle,
                is_account_ready=readiness_fn,
            )
            orchestrator = Orchestrator(
                sheets_client=sheets_client,
                scrape_client=scrape_client,
                firestore_client=firestore_client,
                account_router=account_router,
                email_sender=EmailSender(settings),
                ig_sender=InstagramDmSender(
                    session_manager,
                    attach_mode=settings.ig_attach_mode,
                    cdp_url=settings.ig_cdp_url,
                    cdp_url_resolver=_build_ig_cdp_url_resolver(settings),
                    min_seconds_between_sends=settings.ig_min_seconds_between_sends,
                    send_jitter_seconds=settings.ig_send_jitter_seconds,
                ),
                tiktok_sender=TiktokDmSender(
                    session_manager,
                    attach_mode=settings.tiktok_attach_mode,
                    cdp_url=settings.tiktok_cdp_url,
                    cdp_url_resolver=_build_tiktok_cdp_url_resolver(settings),
                    min_seconds_between_sends=settings.tiktok_min_seconds_between_sends,
                    send_jitter_seconds=settings.tiktok_send_jitter_seconds,
                ),
                sender_profile=settings.sender_profile,
                scrape_app=settings.scrape_app,
                enable_email="email" in enabled_channels,
                enable_instagram="instagram" in enabled_channels,
                enable_tiktok="tiktok" in enabled_channels,
                dedupe_enabled=False,
                stop_when_tiktok_exhausted=("tiktok" in enabled_channels),
            )
            try:
                result = orchestrator.run(
                    batch_size=effective_batch,
                    dry_run=dry_run,
                    row_index=args.lead_row_index,
                )
            except KeyboardInterrupt:
                if settings.reset_counters_on_run_exit and not dry_run:
                    reset_count = firestore_client.reset_daily_counters()
                    print(f"reset_accounts_on_exit={reset_count}")
                if not args.no_report:
                    _write_run_report(
                        started_at=started_at,
                        ended_at=datetime.now(UTC),
                        dry_run=dry_run,
                        enabled_channels=enabled_channels,
                        batch_size=effective_batch,
                        row_index=args.lead_row_index,
                        dedupe_enabled=False,
                        result=OrchestratorResult(
                            processed=0,
                            failed=0,
                            skipped=0,
                            failed_tiktok_links=[],
                            tracking_append_failed_links=[],
                            lead_summaries=[
                                LeadRunSummary(
                                    row_index=args.lead_row_index or -1,
                                    url="",
                                    final_status="interrupted",
                                    sender_email=None,
                                    sender_ig=None,
                                    sender_tiktok=None,
                                    email_status="skipped",
                                    email_error="interrupted",
                                    ig_status="skipped",
                                    ig_error="interrupted",
                                    tiktok_status="skipped",
                                    tiktok_error="interrupted",
                                )
                            ],
                        ),
                        extra={"interrupted": True},
                    )
                print("Run interrupted by user (Ctrl+C).")
                return 130
            print(
                f"processed={result.processed} failed={result.failed} skipped={result.skipped} "
                f"dry_run={dry_run} channels={','.join(sorted(enabled_channels))} "
                f"mode={'unbounded' if unbounded_mode else 'bounded'}"
            )
            if result.failed_tiktok_links:
                print("failed_tiktok_links:")
                for url in result.failed_tiktok_links:
                    print(f"- {url}")
            if result.tracking_append_failed_links:
                print("tracking_append_failed_links:")
                for url in result.tracking_append_failed_links:
                    print(f"- {url}")
            if args.verbose_summary and result.lead_summaries:
                print("lead_summaries:")
                for item in result.lead_summaries:
                    print(
                        f"- row={item.row_index} url={item.url} final={item.final_status} "
                        f"sender_email={item.sender_email or '-'} "
                        f"sender_ig={item.sender_ig or '-'} "
                        f"sender_tiktok={item.sender_tiktok or '-'} "
                        f"email={item.email_status}:{item.email_error or 'none'} "
                        f"ig={item.ig_status}:{item.ig_error or 'none'} "
                        f"tiktok={item.tiktok_status}:{item.tiktok_error or 'none'}"
                    )
            route_telemetry = account_router.telemetry()
            if route_telemetry.selected_counts:
                print("account_usage_selected:")
                for key, count in sorted(route_telemetry.selected_counts.items()):
                    print(f"- {key}={count}")
            if route_telemetry.skipped_counts:
                print("account_usage_skips:")
                for key, count in sorted(route_telemetry.skipped_counts.items()):
                    print(f"- {key}={count}")
            if not args.no_report:
                report_path = _write_run_report(
                    started_at=started_at,
                    ended_at=datetime.now(UTC),
                    dry_run=dry_run,
                    enabled_channels=enabled_channels,
                    batch_size=effective_batch,
                    row_index=args.lead_row_index,
                    dedupe_enabled=False,
                    result=result,
                    account_usage_selected=route_telemetry.selected_counts,
                    account_usage_skips=route_telemetry.skipped_counts,
                )
                print(f"run_report={report_path}")
            if settings.reset_counters_on_run_exit and not dry_run:
                reset_count = firestore_client.reset_daily_counters()
                print(f"reset_accounts_on_exit={reset_count}")
            return 0
        finally:
            firestore_client.release_run_lock(holder=holder)
    finally:
        _remove_pid_file(pid_file)


def _install_signal_handlers() -> None:
    def _handle_signal(signum: int, _frame: FrameType | None) -> None:
        raise KeyboardInterrupt(f"received signal {signum}")

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)


def _build_scrape_client(settings: Settings) -> LocalScrapeClient:
    if not settings.searchapi_key:
        raise ValueError("Local scrape backend requires SEARCHAPI_KEY")
    return LocalScrapeClient(
        LocalScrapeSettings(
            searchapi_key=settings.searchapi_key,
            request_timeout_seconds=settings.searchapi_timeout_seconds,
            same_username_fallback=settings.scrape_same_username_fallback,
            templates_dir=settings.local_templates_dir,
            outreach_apps_json=settings.local_outreach_apps_json,
        )
    )


def _run_startup_preflight(
    *,
    settings: Settings,
    firestore_client: FirestoreClient,
    enabled_channels: set[str],
    dry_run: bool,
) -> None:
    _validate_tiktok_mode(settings)
    if not settings.local_templates_dir.exists():
        raise ValueError(f"LOCAL_TEMPLATES_DIR does not exist: {settings.local_templates_dir}")
    app_template = settings.local_templates_dir / f"{settings.scrape_app.lower()}.py"
    if not app_template.exists():
        raise ValueError(
            f"Missing app template file: {app_template}. "
            f"Ensure SCRAPE_APP matches a template in LOCAL_TEMPLATES_DIR."
        )
    if not settings.searchapi_key:
        raise ValueError("Missing SEARCHAPI_KEY for local scrape backend.")

    if dry_run:
        return

    session_manager = SessionManager(settings.ig_profile_dir, settings.tiktok_profile_dir)
    if "email" in enabled_channels:
        _ensure_email_tokens_exist(
            accounts=firestore_client.list_active_accounts(Platform.EMAIL),
            settings=settings,
        )
    if "instagram" in enabled_channels:
        if settings.ig_attach_mode:
            ig_accounts = firestore_client.list_active_accounts(Platform.INSTAGRAM)
            if settings.ig_attach_account_cdp_urls:
                _ensure_ig_attach_account_urls(accounts=ig_accounts, settings=settings)
            else:
                _ensure_ig_attach_available(
                    cdp_url=settings.ig_cdp_url,
                    auto_start=settings.ig_attach_auto_start,
                )
        else:
            _ensure_account_sessions_exist(
                accounts=firestore_client.list_active_accounts(Platform.INSTAGRAM),
                platform=Platform.INSTAGRAM,
                session_manager=session_manager,
            )
    if "tiktok" in enabled_channels:
        if settings.tiktok_attach_mode:
            if settings.tiktok_cycling_mode == "attach_single_browser":
                if not settings.tiktok_sender_handle:
                    raise ValueError(
                        "TIKTOK_ATTACH_MODE=true with attach_single_browser requires TIKTOK_SENDER_HANDLE."
                    )
                _ensure_tiktok_attach_available(
                    cdp_url=settings.tiktok_cdp_url,
                    auto_start=settings.tiktok_attach_auto_start,
                )
            elif settings.tiktok_cycling_mode == "attach_per_account_browser":
                accounts = firestore_client.list_active_accounts(Platform.TIKTOK)
                _ensure_tiktok_attach_account_urls(accounts=accounts, settings=settings)
            else:
                raise ValueError(
                    f"Unsupported attach-mode TikTok cycling mode: {settings.tiktok_cycling_mode}"
                )
        else:
            _ensure_account_sessions_exist(
                accounts=firestore_client.list_active_accounts(Platform.TIKTOK),
                platform=Platform.TIKTOK,
                session_manager=session_manager,
            )


def _ensure_account_sessions_exist(
    *,
    accounts: list[Account],
    platform: Platform,
    session_manager: SessionManager,
) -> None:
    missing: list[str] = []
    for account in accounts:
        handle = account.handle
        if not handle:
            continue
        profile_dir = session_manager.profile_dir_for(platform, handle)
        if not profile_dir.exists():
            missing.append(handle)
    if missing:
        joined = ", ".join(sorted(missing))
        raise ValueError(
            f"Missing {platform.value} sessions for active accounts: {joined}. "
            "Run login bootstrap before live sends."
        )


def _ensure_email_tokens_exist(*, accounts: list[Account], settings: Settings) -> None:
    configured = {conf.email.strip().lower() for conf in settings.gmail_accounts}
    missing: list[str] = []
    for account in accounts:
        handle = account.handle.strip().lower()
        if not handle:
            continue
        if handle not in configured:
            missing.append(account.handle)
    if missing:
        joined = ", ".join(sorted(missing))
        raise ValueError(
            f"Missing Gmail refresh token config for active email accounts: {joined}. "
            "Set matching GMAIL_ACCOUNT_*_EMAIL and GMAIL_ACCOUNT_*_REFRESH_TOKEN entries."
        )


def _parse_channels(raw: str) -> set[str]:
    aliases = {
        "email": "email",
        "mail": "email",
        "ig": "instagram",
        "instagram": "instagram",
        "tt": "tiktok",
        "tiktok": "tiktok",
    }
    requested = {part.strip().lower() for part in raw.split(",") if part.strip()}
    normalized = {aliases[item] for item in requested if item in aliases}
    if not normalized:
        raise ValueError("No valid channels selected. Use email,instagram,tiktok.")
    return normalized


def _validate_tiktok_mode(settings: Settings) -> None:
    mode = getattr(settings, "tiktok_cycling_mode", "per_account_session")
    allowed = {"per_account_session", "attach_single_browser", "attach_per_account_browser"}
    if mode not in allowed:
        raise ValueError(
            f"Unsupported TIKTOK_CYCLING_MODE={mode}. Allowed: {sorted(allowed)}"
        )
    if settings.tiktok_attach_mode and mode == "per_account_session":
        raise ValueError(
            "TIKTOK_ATTACH_MODE=true cannot use TIKTOK_CYCLING_MODE=per_account_session"
        )
    if (not settings.tiktok_attach_mode) and mode in {
        "attach_single_browser",
        "attach_per_account_browser",
    }:
        raise ValueError(
            "TIKTOK_CYCLING_MODE=attach_* requires TIKTOK_ATTACH_MODE=true"
        )


def _build_account_readiness_checker(
    *,
    settings: Settings,
    session_manager: SessionManager,
) -> Callable[[Platform, Account], tuple[bool, str | None]]:
    gmail_handles = {cfg.email.strip().lower() for cfg in settings.gmail_accounts}
    ig_attach_mode = bool(getattr(settings, "ig_attach_mode", False))
    ig_attach_auto_start = bool(getattr(settings, "ig_attach_auto_start", False))
    ig_cdp_url = getattr(settings, "ig_cdp_url", None)
    tiktok_attach_mode = bool(getattr(settings, "tiktok_attach_mode", False))
    tiktok_attach_auto_start = bool(getattr(settings, "tiktok_attach_auto_start", False))

    def _check(platform: Platform, account: Account) -> tuple[bool, str | None]:
        handle_norm = account.handle.strip().lower()
        if platform == Platform.EMAIL:
            if handle_norm not in gmail_handles:
                return False, "missing_refresh_token"
            return True, None
        if platform == Platform.INSTAGRAM:
            if ig_attach_mode:
                account_cdp_url = _ig_cdp_url_for_handle(settings=settings, handle=account.handle)
                if account_cdp_url:
                    parsed = urlparse(account_cdp_url)
                    host = parsed.hostname
                    port = parsed.port
                    if not host or not port:
                        return False, "invalid_ig_account_cdp_url"
                    if _is_cdp_reachable(host, port):
                        return True, None
                    if ig_attach_auto_start:
                        return True, None
                    return False, "ig_cdp_unreachable"
                if ig_cdp_url:
                    parsed = urlparse(ig_cdp_url)
                    host = parsed.hostname
                    port = parsed.port
                    if host and port and _is_cdp_reachable(host, port):
                        return True, None
                    if ig_attach_auto_start:
                        return True, None
                    return False, "ig_cdp_unreachable"
                return False, "missing_ig_cdp_url"
            profile_dir = session_manager.profile_dir_for(platform, account.handle)
            if not profile_dir.exists():
                return False, "missing_session"
            return True, None
        # TikTok
        if tiktok_attach_mode:
            mode = getattr(settings, "tiktok_cycling_mode", "attach_single_browser")
            if mode == "attach_single_browser":
                if not settings.tiktok_sender_handle:
                    return False, "attach_requires_pinned_handle"
                if handle_norm != settings.tiktok_sender_handle.strip().lower():
                    return False, "attach_single_account_mismatch"
                if settings.tiktok_cdp_url:
                    parsed = urlparse(settings.tiktok_cdp_url)
                    host = parsed.hostname
                    port = parsed.port
                    if host and port and _is_cdp_reachable(host, port):
                        return True, None
                if tiktok_attach_auto_start:
                    return True, None
                return False, "cdp_unreachable"
            if mode == "attach_per_account_browser":
                account_cdp_url = _tiktok_cdp_url_for_handle(settings=settings, handle=account.handle)
                if not account_cdp_url:
                    return False, "missing_account_cdp_url"
                parsed = urlparse(account_cdp_url)
                host = parsed.hostname
                port = parsed.port
                if not host or not port:
                    return False, "invalid_account_cdp_url"
                if _is_cdp_reachable(host, port):
                    return True, None
                if tiktok_attach_auto_start:
                    return True, None
                return False, "cdp_unreachable"
            return False, "unsupported_tiktok_mode"
        profile_dir = session_manager.profile_dir_for(platform, account.handle)
        if not profile_dir.exists():
            return False, "missing_session"
        return True, None

    return _check


def _tiktok_cdp_url_for_handle(*, settings: Settings, handle: str) -> str | None:
    normalized = handle.strip().lower()
    if normalized and not normalized.startswith("@"):
        normalized = f"@{normalized}"
    cdp_map = getattr(settings, "tiktok_attach_account_cdp_urls", {})
    return cdp_map.get(normalized)


def _ig_cdp_url_for_handle(*, settings: Settings, handle: str) -> str | None:
    normalized = handle.strip().lower()
    if normalized and not normalized.startswith("@"):
        normalized = f"@{normalized}"
    cdp_map = getattr(settings, "ig_attach_account_cdp_urls", {})
    return cdp_map.get(normalized)


def _build_ig_cdp_url_resolver(settings: Settings) -> Callable[[str], str | None] | None:
    if not settings.ig_attach_mode:
        return None
    if settings.ig_attach_account_cdp_urls:
        return lambda handle: _ig_cdp_url_for_handle(settings=settings, handle=handle)
    return lambda _handle: settings.ig_cdp_url


def _build_tiktok_cdp_url_resolver(settings: Settings) -> Callable[[str], str | None] | None:
    if not settings.tiktok_attach_mode:
        return None
    mode = getattr(settings, "tiktok_cycling_mode", "attach_single_browser")
    if mode == "attach_single_browser":
        return lambda _handle: settings.tiktok_cdp_url
    if mode == "attach_per_account_browser":
        return lambda handle: _tiktok_cdp_url_for_handle(settings=settings, handle=handle)
    return None


def _ensure_ig_attach_available(*, cdp_url: str | None, auto_start: bool) -> None:
    if not cdp_url:
        raise ValueError("IG_ATTACH_MODE=true requires IG_CDP_URL or IG_ATTACH_ACCOUNT_CDP_URLS.")
    parsed = urlparse(cdp_url)
    host = parsed.hostname
    port = parsed.port
    if not host or not port:
        raise ValueError(f"Invalid IG_CDP_URL: {cdp_url}")
    if _is_cdp_reachable(host, port):
        return

    if auto_start:
        _start_chrome_debug(port=port, start_url="https://www.instagram.com/")
        for _ in range(10):
            if _is_cdp_reachable(host, port):
                return
            time.sleep(1)

    raise ValueError(
        f"IG attach mode is enabled but Chrome debugger is unreachable at {cdp_url}. "
        "If auto-start is disabled, enable IG_ATTACH_AUTO_START=true or run "
        f"./ops/start_chrome_debug.sh {port}."
    )


def _ensure_ig_attach_account_urls(*, accounts: list[Account], settings: Settings) -> None:
    missing: list[str] = []
    invalid: list[str] = []
    reachable_count = 0
    for account in accounts:
        cdp_url = _ig_cdp_url_for_handle(settings=settings, handle=account.handle)
        if not cdp_url:
            missing.append(account.handle)
            continue
        parsed = urlparse(cdp_url)
        host = parsed.hostname
        port = parsed.port
        if not host or not port:
            invalid.append(f"{account.handle}={cdp_url}")
            continue
        if not _is_cdp_reachable(host, port):
            if settings.ig_attach_auto_start:
                _start_chrome_debug(
                    port=port,
                    profile_dir=str(settings.ig_profile_dir / account.handle.lstrip("@")),
                    start_url="https://www.instagram.com/",
                )
            if not _is_cdp_reachable(host, port):
                invalid.append(f"{account.handle}={cdp_url} (unreachable)")
            else:
                reachable_count += 1
        else:
            reachable_count += 1
    if missing:
        _LOG.warning(
            "Missing IG attach CDP URL mapping for active accounts",
            extra={"missing_ig_attach_handles": sorted(missing)},
        )
    if invalid:
        _LOG.warning(
            "Some per-account Instagram CDP endpoints are invalid/unreachable",
            extra={"invalid_ig_attach_endpoints": sorted(invalid)},
        )
    if reachable_count == 0:
        raise ValueError(
            "No reachable per-account Instagram CDP endpoints for active accounts. "
            "Start at least one debug Chrome instance or enable IG_ATTACH_AUTO_START=true."
        )


def _ensure_tiktok_attach_available(*, cdp_url: str | None, auto_start: bool) -> None:
    if not cdp_url:
        raise ValueError("TIKTOK_ATTACH_MODE=true requires TIKTOK_CDP_URL.")
    parsed = urlparse(cdp_url)
    host = parsed.hostname
    port = parsed.port
    if not host or not port:
        raise ValueError(f"Invalid TIKTOK_CDP_URL: {cdp_url}")
    if _is_cdp_reachable(host, port):
        return

    if auto_start:
        _start_chrome_debug(port=port, start_url="https://www.tiktok.com")
        for _ in range(10):
            if _is_cdp_reachable(host, port):
                return
            time.sleep(1)

    raise ValueError(
        f"TikTok attach mode is enabled but Chrome debugger is unreachable at {cdp_url}. "
        "If auto-start is disabled, enable TIKTOK_ATTACH_AUTO_START=true or run "
        f"./ops/start_chrome_debug.sh {port}."
    )


def _ensure_tiktok_attach_account_urls(*, accounts: list[Account], settings: Settings) -> None:
    missing: list[str] = []
    invalid: list[str] = []
    reachable_count = 0
    for account in accounts:
        cdp_url = _tiktok_cdp_url_for_handle(settings=settings, handle=account.handle)
        if not cdp_url:
            missing.append(account.handle)
            continue
        parsed = urlparse(cdp_url)
        host = parsed.hostname
        port = parsed.port
        if not host or not port:
            invalid.append(f"{account.handle}={cdp_url}")
            continue
        if not _is_cdp_reachable(host, port):
            if settings.tiktok_attach_auto_start:
                _start_chrome_debug(
                    port=port,
                    profile_dir=str(settings.tiktok_profile_dir / account.handle.lstrip("@")),
                    start_url="https://www.tiktok.com",
                )
            if not _is_cdp_reachable(host, port):
                invalid.append(f"{account.handle}={cdp_url} (unreachable)")
            else:
                reachable_count += 1
        else:
            reachable_count += 1
    if missing:
        _LOG.warning(
            "Missing TikTok attach CDP URL mapping for active accounts",
            extra={"missing_tiktok_attach_handles": sorted(missing)},
        )
    if invalid:
        _LOG.warning(
            "Some per-account TikTok CDP endpoints are invalid/unreachable",
            extra={"invalid_tiktok_attach_endpoints": sorted(invalid)},
        )
    if reachable_count == 0:
        raise ValueError(
            "No reachable per-account TikTok CDP endpoints for active accounts. "
            "Start at least one debug Chrome instance or enable TIKTOK_ATTACH_AUTO_START=true."
        )


def _is_cdp_reachable(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False


def _start_chrome_debug(*, port: int, profile_dir: str | None = None, start_url: str | None = None) -> None:
    project_root = Path(__file__).resolve().parents[2]
    script = project_root / "ops" / "start_chrome_debug.sh"
    if not script.exists():
        return
    args = [str(script), str(port)]
    if profile_dir:
        args.append(profile_dir)
    if start_url:
        args.append(start_url)
    subprocess.run(args, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _pid_file_path() -> Path:
    project_root = Path(__file__).resolve().parents[2]
    return project_root / ".runtime" / "run_once.pid"


def _write_pid_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "pid": os.getpid(),
        "started_at": datetime.now(UTC).isoformat(),
        "hostname": socket.gethostname(),
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _remove_pid_file(path: Path) -> None:
    with contextlib.suppress(Exception):
        path.unlink(missing_ok=True)


def _write_run_report(
    *,
    started_at: datetime,
    ended_at: datetime,
    dry_run: bool,
    enabled_channels: set[str],
    batch_size: int,
    row_index: int | None,
    dedupe_enabled: bool,
    result: OrchestratorResult,
    account_usage_selected: dict[str, int] | None = None,
    account_usage_skips: dict[str, int] | None = None,
    extra: dict[str, object] | None = None,
) -> str:
    report_dir = Path(__file__).resolve().parents[2] / "logs" / "run-reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = ended_at.strftime("%Y%m%d-%H%M%S")
    report_path = report_dir / f"run-{stamp}.json"
    payload: dict[str, object] = {
        "started_at": started_at.isoformat(),
        "ended_at": ended_at.isoformat(),
        "duration_seconds": round((ended_at - started_at).total_seconds(), 2),
        "dry_run": dry_run,
        "channels": sorted(enabled_channels),
        "batch_size": batch_size,
        "row_index": row_index,
        "dedupe_enabled": dedupe_enabled,
        "processed": result.processed,
        "failed": result.failed,
        "skipped": result.skipped,
        "failed_tiktok_links": result.failed_tiktok_links,
        "tracking_append_failed_links": result.tracking_append_failed_links,
        "account_usage_selected": account_usage_selected or {},
        "account_usage_skips": account_usage_skips or {},
        "lead_summaries": [
            {
                "row_index": item.row_index,
                "url": item.url,
                "final_status": item.final_status,
                "sender_email": item.sender_email,
                "sender_instagram": item.sender_ig,
                "sender_tiktok": item.sender_tiktok,
                "email": {"status": item.email_status, "error": item.email_error},
                "instagram": {"status": item.ig_status, "error": item.ig_error},
                "tiktok": {"status": item.tiktok_status, "error": item.tiktok_error},
            }
            for item in result.lead_summaries
        ],
    }
    if extra:
        payload.update(extra)
    report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return str(report_path)


if __name__ == "__main__":
    raise SystemExit(main())
