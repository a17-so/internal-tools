from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from outreach_automation.orchestrator import LeadRunSummary, OrchestratorResult
from outreach_automation.run_once import _write_run_report


def test_write_run_report_creates_expected_json(tmp_path: Path, monkeypatch: Any) -> None:
    fake_module_path = tmp_path / "src" / "outreach_automation" / "run_once.py"
    fake_module_path.parent.mkdir(parents=True, exist_ok=True)
    fake_module_path.write_text("# stub", encoding="utf-8")
    monkeypatch.setattr("outreach_automation.run_once.__file__", str(fake_module_path))

    started_at = datetime(2026, 3, 6, 10, 0, 0, tzinfo=UTC)
    ended_at = datetime(2026, 3, 6, 10, 0, 5, tzinfo=UTC)
    result = OrchestratorResult(
        processed=1,
        failed=1,
        skipped=0,
        failed_tiktok_links=["https://www.tiktok.com/@failed"],
        tracking_append_failed_links=["https://www.tiktok.com/@trackfail"],
        lead_summaries=[
            LeadRunSummary(
                row_index=12,
                url="https://www.tiktok.com/@creator",
                final_status="Processed",
                email_status="sent",
                email_error=None,
                ig_status="sent",
                ig_error=None,
                tiktok_status="failed",
                tiktok_error="tiktok_send_failed",
            )
        ],
    )

    report_path = _write_run_report(
        started_at=started_at,
        ended_at=ended_at,
        dry_run=False,
        enabled_channels={"email", "instagram", "tiktok"},
        batch_size=30,
        row_index=None,
        dedupe_enabled=True,
        result=result,
    )

    payload = json.loads(Path(report_path).read_text(encoding="utf-8"))
    assert payload["processed"] == 1
    assert payload["failed"] == 1
    assert payload["duration_seconds"] == 5.0
    assert payload["failed_tiktok_links"] == ["https://www.tiktok.com/@failed"]
    assert payload["tracking_append_failed_links"] == ["https://www.tiktok.com/@trackfail"]
    assert payload["lead_summaries"][0]["row_index"] == 12
