from outreach_automation.models import ChannelResult
from outreach_automation.status_mapper import final_sheet_status


def test_status_processed() -> None:
    assert (
        final_sheet_status(
            ChannelResult(status="sent"),
            ChannelResult(status="sent"),
            ChannelResult(status="sent"),
        )
        == "Processed"
    )


def test_status_pending_tomorrow() -> None:
    assert (
        final_sheet_status(
            ChannelResult(status="sent"),
            ChannelResult(status="pending_tomorrow", error_code="no_ig_account"),
            ChannelResult(status="sent"),
        )
        == "pending_tomorrow"
    )


def test_status_failed_with_code() -> None:
    assert (
        final_sheet_status(
            ChannelResult(status="failed", error_code="smtp"),
            ChannelResult(status="sent"),
            ChannelResult(status="sent"),
        )
        == "failed_smtp"
    )


def test_status_processed_when_contact_data_missing() -> None:
    assert (
        final_sheet_status(
            ChannelResult(status="skipped", error_code="missing_email_fields"),
            ChannelResult(status="skipped", error_code="missing_ig_handle"),
            ChannelResult(status="sent"),
        )
        == "Processed"
    )


def test_status_processed_when_dm_is_unavailable() -> None:
    assert (
        final_sheet_status(
            ChannelResult(status="sent"),
            ChannelResult(status="skipped", error_code="ig_dm_unavailable"),
            ChannelResult(status="skipped", error_code="tiktok_dm_unavailable"),
        )
        == "Processed"
    )


def test_status_processed_when_email_disabled() -> None:
    assert (
        final_sheet_status(
            ChannelResult(status="skipped", error_code="email_disabled"),
            ChannelResult(status="sent"),
            ChannelResult(status="sent"),
        )
        == "Processed"
    )
