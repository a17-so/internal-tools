from __future__ import annotations

from outreach_automation.sheets_client import SheetColumns, SheetsClient


class _FakeSheet:
    def __init__(self, rows: list[list[str]]) -> None:
        self._rows = rows

    def get_all_values(self) -> list[list[str]]:
        return self._rows


def test_fetch_unprocessed_skips_blank_creator_url_rows() -> None:
    client = SheetsClient.__new__(SheetsClient)
    client._sheet = _FakeSheet(
        [
            ["creator_url", "creator_tier", "status"],
            ["", "Submicro", ""],
            ["https://www.tiktok.com/@valid", "Submicro", ""],
        ]
    )  # type: ignore[assignment]
    client._columns = SheetColumns(creator_url=1, creator_tier=2, status=3, matrix_mode=False)

    rows = client.fetch_unprocessed(batch_size=10)
    assert len(rows) == 1
    assert rows[0].row_index == 3
    assert rows[0].creator_url == "https://www.tiktok.com/@valid"
