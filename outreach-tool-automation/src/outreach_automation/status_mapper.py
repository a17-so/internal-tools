from __future__ import annotations

from outreach_automation.models import ChannelResult

_ALLOWED_SKIP_CODES = {
    "email_disabled",
    "missing_email_fields",
    "missing_ig_handle",
    "missing_tiktok_handle",
    "ig_dm_unavailable",
    "tiktok_dm_unavailable",
}


def final_sheet_status(
    email_result: ChannelResult,
    ig_result: ChannelResult,
    tiktok_result: ChannelResult,
) -> str:
    results = [email_result, ig_result, tiktok_result]

    if all(_is_success_equivalent(result) for result in results):
        return "Processed"

    if any(result.status == "pending_tomorrow" for result in results):
        return "pending_tomorrow"

    failed = next((result for result in results if result.status == "failed"), None)
    if failed and failed.error_code:
        return f"failed_{failed.error_code}"

    skipped = next((result for result in results if result.status == "skipped"), None)
    if skipped and skipped.error_code:
        return f"skipped_{skipped.error_code}"

    return "failed_unknown"


def _is_success_equivalent(result: ChannelResult) -> bool:
    if result.status == "sent":
        return True
    return result.status == "skipped" and result.error_code in _ALLOWED_SKIP_CODES
