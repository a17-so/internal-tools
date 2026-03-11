from __future__ import annotations

import json
import socket
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from outreach_automation.clients.firestore_client import FirestoreClient
from outreach_automation.clients.sheets_client import SheetsClient
from outreach_automation.models import Account, Platform
from outreach_automation.session_manager import SessionManager
from outreach_automation.settings import Settings, load_settings


@dataclass(slots=True)
class CheckResult:
    name: str
    ok: bool
    detail: str
    blocking: bool = False


def main() -> int:
    settings = load_settings()
    checks = _run_checks(settings)
    payload = {
        "ok": not any(item.blocking and not item.ok for item in checks),
        "checks": [
            {
                "name": item.name,
                "ok": item.ok,
                "detail": item.detail,
                "blocking": item.blocking,
            }
            for item in checks
        ],
    }
    print(json.dumps(payload, indent=2))
    return 0 if payload["ok"] else 2


def _run_checks(settings: Settings) -> list[CheckResult]:
    out: list[CheckResult] = []
    out.extend(_check_local_scrape_config(settings))
    out.append(_check_tiktok_mode(settings))

    sheets = _build_sheets_check(settings)
    out.append(sheets)

    firestore = _build_firestore_check(settings)
    out.append(firestore)

    firestore_client: FirestoreClient | None = None
    if firestore.ok:
        firestore_client = FirestoreClient(
            service_account_path=settings.google_service_account_json,
            project_id=settings.firestore_project_id,
        )
        out.extend(_check_sender_accounts(settings, firestore_client))
        out.extend(_check_sessions(settings, firestore_client))
        out.append(_check_account_readiness_matrix(settings, firestore_client))
    else:
        out.append(CheckResult("accounts", False, "Skipped (Firestore unavailable)", blocking=False))
        out.append(CheckResult("sessions", False, "Skipped (Firestore unavailable)", blocking=False))
        out.append(
            CheckResult("account_readiness_matrix", False, "Skipped (Firestore unavailable)", blocking=False)
        )

    out.append(_check_tiktok_attach(settings))
    out.extend(_check_gmail_config(settings))
    return out


def _check_local_scrape_config(settings: Settings) -> list[CheckResult]:
    out: list[CheckResult] = []
    templates_ok = settings.local_templates_dir.exists()
    out.append(
        CheckResult(
            "templates_dir",
            templates_ok,
            f"{settings.local_templates_dir}",
            blocking=True,
        )
    )
    app_template = settings.local_templates_dir / f"{settings.scrape_app.lower()}.py"
    out.append(
        CheckResult(
            "scrape_app_template",
            app_template.exists(),
            f"{app_template}",
            blocking=True,
        )
    )
    out.append(
        CheckResult(
            "searchapi_key",
            bool(settings.searchapi_key),
            "Configured" if settings.searchapi_key else "Missing",
            blocking=True,
        )
    )
    return out


def _build_sheets_check(settings: Settings) -> CheckResult:
    try:
        client = SheetsClient(
            service_account_path=settings.google_service_account_json,
            sheet_id=settings.google_sheets_id,
            worksheet_name=settings.raw_leads_sheet_name,
            url_column_name=settings.raw_leads_url_column,
            tier_column_name=settings.raw_leads_tier_column,
            status_column_name=settings.raw_leads_status_column,
        )
        rows = client.fetch_unprocessed(batch_size=1)
        return CheckResult("sheets_access", True, f"OK (sample_unprocessed={len(rows)})", blocking=True)
    except Exception as exc:
        return CheckResult("sheets_access", False, str(exc), blocking=True)


def _build_firestore_check(settings: Settings) -> CheckResult:
    try:
        client = FirestoreClient(
            service_account_path=settings.google_service_account_json,
            project_id=settings.firestore_project_id,
        )
        count = (
            len(client.list_active_accounts(Platform.EMAIL))
            + len(client.list_active_accounts(Platform.INSTAGRAM))
            + len(client.list_active_accounts(Platform.TIKTOK))
        )
        return CheckResult("firestore_access", True, f"OK (active_accounts={count})", blocking=True)
    except Exception as exc:
        return CheckResult("firestore_access", False, str(exc), blocking=True)


def _check_sender_accounts(settings: Settings, firestore_client: FirestoreClient) -> list[CheckResult]:
    out: list[CheckResult] = []
    active_email = firestore_client.list_active_accounts(Platform.EMAIL)
    active_ig = firestore_client.list_active_accounts(Platform.INSTAGRAM)
    active_tt = firestore_client.list_active_accounts(Platform.TIKTOK)

    out.append(CheckResult("active_email_accounts", bool(active_email), f"count={len(active_email)}", blocking=True))
    out.append(CheckResult("active_instagram_accounts", bool(active_ig), f"count={len(active_ig)}", blocking=False))
    out.append(CheckResult("active_tiktok_accounts", bool(active_tt), f"count={len(active_tt)}", blocking=False))

    if settings.strict_sender_pinning:
        out.extend(
            [
                _check_pinned_handle("pinned_email_handle", settings.email_sender_handle, active_email),
                _check_pinned_handle("pinned_instagram_handle", settings.instagram_sender_handle, active_ig),
                _check_pinned_handle("pinned_tiktok_handle", settings.tiktok_sender_handle, active_tt),
            ]
        )
    return out


def _check_pinned_handle(name: str, handle: str | None, active_accounts: list[Account]) -> CheckResult:
    if not handle:
        return CheckResult(name, True, "Not set", blocking=False)
    target = handle.strip().lower()
    ok = any(str(acc.handle).strip().lower() == target for acc in active_accounts)
    return CheckResult(name, ok, f"handle={handle}", blocking=not ok)


def _check_sessions(settings: Settings, firestore_client: FirestoreClient) -> list[CheckResult]:
    out: list[CheckResult] = []
    session_manager = SessionManager(settings.ig_profile_dir, settings.tiktok_profile_dir)
    ig_missing = _missing_profile_dirs(session_manager, Platform.INSTAGRAM, firestore_client.list_active_accounts(Platform.INSTAGRAM))
    if settings.tiktok_attach_mode:
        tt_missing: list[str] = []
    else:
        tt_missing = _missing_profile_dirs(session_manager, Platform.TIKTOK, firestore_client.list_active_accounts(Platform.TIKTOK))

    out.append(CheckResult("instagram_sessions", not ig_missing, "missing=" + ",".join(ig_missing) if ig_missing else "OK", blocking=bool(ig_missing)))
    out.append(CheckResult("tiktok_sessions", not tt_missing, "missing=" + ",".join(tt_missing) if tt_missing else "OK", blocking=bool(tt_missing)))
    return out


def _missing_profile_dirs(
    session_manager: SessionManager,
    platform: Platform,
    accounts: list[Account],
) -> list[str]:
    missing: list[str] = []
    for account in accounts:
        handle = str(account.handle or "").strip()
        if not handle:
            continue
        profile_dir = session_manager.profile_dir_for(platform, handle)
        if not Path(profile_dir).exists():
            missing.append(handle)
    return missing


def _check_tiktok_attach(settings: Settings) -> CheckResult:
    if not settings.tiktok_attach_mode:
        return CheckResult("tiktok_attach_mode", True, "Disabled", blocking=False)
    if not settings.tiktok_cdp_url:
        return CheckResult("tiktok_attach_mode", False, "TIKTOK_CDP_URL missing", blocking=True)
    parsed = urlparse(settings.tiktok_cdp_url)
    host = parsed.hostname
    port = parsed.port
    if not host or not port:
        return CheckResult("tiktok_attach_mode", False, f"Invalid CDP URL: {settings.tiktok_cdp_url}", blocking=True)
    ok = _is_socket_reachable(host, port)
    blocking = not ok and not settings.tiktok_attach_auto_start
    return CheckResult(
        "tiktok_attach_mode",
        ok,
        (
            f"{settings.tiktok_cdp_url} reachable={ok}"
            if ok
            else f"{settings.tiktok_cdp_url} unreachable now (auto_start={settings.tiktok_attach_auto_start})"
        ),
        blocking=blocking,
    )


def _is_socket_reachable(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False


def _check_gmail_config(settings: Settings) -> list[CheckResult]:
    out: list[CheckResult] = []
    out.append(
        CheckResult(
            "gmail_client_credentials",
            bool(settings.gmail_client_id and settings.gmail_client_secret),
            "Configured" if settings.gmail_client_id and settings.gmail_client_secret else "Missing",
            blocking=True,
        )
    )
    out.append(
        CheckResult(
            "gmail_account_tokens",
            bool(settings.gmail_accounts),
            f"count={len(settings.gmail_accounts)}",
            blocking=True,
        )
    )
    return out


def _check_tiktok_mode(settings: Settings) -> CheckResult:
    allowed = {"per_account_session", "attach_single_browser"}
    mode = settings.tiktok_cycling_mode
    if mode not in allowed:
        return CheckResult(
            "tiktok_mode",
            False,
            f"Unsupported mode={mode} allowed={sorted(allowed)}",
            blocking=True,
        )
    if settings.tiktok_attach_mode and mode != "attach_single_browser":
        return CheckResult(
            "tiktok_mode",
            False,
            "TIKTOK_ATTACH_MODE=true requires TIKTOK_CYCLING_MODE=attach_single_browser",
            blocking=True,
        )
    if (not settings.tiktok_attach_mode) and mode == "attach_single_browser":
        return CheckResult(
            "tiktok_mode",
            False,
            "TIKTOK_CYCLING_MODE=attach_single_browser requires TIKTOK_ATTACH_MODE=true",
            blocking=True,
        )
    return CheckResult(
        "tiktok_mode",
        True,
        f"mode={mode} attach_mode={settings.tiktok_attach_mode}",
        blocking=False,
    )


def _check_account_readiness_matrix(settings: Settings, firestore_client: FirestoreClient) -> CheckResult:
    session_manager = SessionManager(settings.ig_profile_dir, settings.tiktok_profile_dir)
    gmail_handles = {cfg.email.strip().lower() for cfg in settings.gmail_accounts}
    attach_reachable = False
    attach_endpoint = settings.tiktok_cdp_url or ""
    if settings.tiktok_attach_mode and settings.tiktok_cdp_url:
        parsed = urlparse(settings.tiktok_cdp_url)
        if parsed.hostname and parsed.port:
            attach_reachable = _is_socket_reachable(parsed.hostname, parsed.port)

    entries: list[dict[str, str | bool]] = []
    total_ready = 0
    total = 0

    for platform in (Platform.EMAIL, Platform.INSTAGRAM, Platform.TIKTOK):
        accounts = firestore_client.list_active_accounts(platform)
        for account in accounts:
            total += 1
            ready, reason = _account_readiness(
                settings=settings,
                session_manager=session_manager,
                gmail_handles=gmail_handles,
                platform=platform,
                account=account,
                attach_reachable=attach_reachable,
            )
            if ready:
                total_ready += 1
            entries.append(
                {
                    "platform": platform.value,
                    "handle": account.handle,
                    "ready": ready,
                    "reason": reason or "ok",
                }
            )

    detail = json.dumps(
        {
            "ready_accounts": total_ready,
            "total_accounts": total,
            "tiktok_attach_mode": settings.tiktok_attach_mode,
            "tiktok_cycling_mode": settings.tiktok_cycling_mode,
            "tiktok_cdp_url": attach_endpoint,
            "tiktok_cdp_reachable": attach_reachable,
            "matrix": entries,
        },
        separators=(",", ":"),
    )
    return CheckResult("account_readiness_matrix", True, detail, blocking=False)


def _account_readiness(
    *,
    settings: Settings,
    session_manager: SessionManager,
    gmail_handles: set[str],
    platform: Platform,
    account: Account,
    attach_reachable: bool,
) -> tuple[bool, str | None]:
    handle_norm = account.handle.strip().lower()
    if platform == Platform.EMAIL:
        if handle_norm in gmail_handles:
            return True, None
        return False, "missing_refresh_token"
    if platform == Platform.INSTAGRAM:
        profile_dir = session_manager.profile_dir_for(platform, account.handle)
        if profile_dir.exists():
            return True, None
        return False, "missing_session"
    # TikTok
    if settings.tiktok_attach_mode:
        pinned = (settings.tiktok_sender_handle or "").strip().lower()
        if not pinned:
            return False, "attach_requires_pinned_handle"
        if handle_norm != pinned:
            return False, "attach_single_account_mismatch"
        if attach_reachable or settings.tiktok_attach_auto_start:
            return True, None
        return False, "cdp_unreachable"
    profile_dir = session_manager.profile_dir_for(platform, account.handle)
    if profile_dir.exists():
        return True, None
    return False, "missing_session"


if __name__ == "__main__":
    raise SystemExit(main())
