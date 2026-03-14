from __future__ import annotations

from outreach_automation.clients.sheets_client import SheetColumns, SheetsClient


class _FakeSheet:
    def __init__(self, rows: list[list[str]]) -> None:
        self._rows = rows

    def get_all_values(self) -> list[list[str]]:
        return self._rows

    def row_values(self, index: int) -> list[str]:
        return self._rows[index - 1]


def test_fetch_unprocessed_skips_blank_creator_url_rows() -> None:
    client = SheetsClient.__new__(SheetsClient)
    client._sheet = _FakeSheet(
        [
            ["creator_url", "creator_tier", "status"],
            ["", "Submicro", ""],
            ["https://www.tiktok.com/@valid", "Submicro", ""],
            ["https://www.instagram.com/valid_ig", "Micro", ""],
            ["https://example.com/unsupported", "Macro", ""],
        ]
    )  # type: ignore[assignment]
    client._columns = SheetColumns(creator_url=1, creator_tier=2, status=3, matrix_mode=False)

    rows = client.fetch_unprocessed(batch_size=10)
    assert len(rows) == 2
    assert rows[0].row_index == 3
    assert rows[0].creator_url == "https://www.tiktok.com/@valid"
    assert rows[1].row_index == 4
    assert rows[1].creator_url == "https://www.instagram.com/valid_ig"


def test_fetch_matrix_reads_all_url_columns_and_tiers() -> None:
    client = SheetsClient.__new__(SheetsClient)
    client._sheet = _FakeSheet(
        [
            ["Feb 27 (Abhay)", "Feb 27 (Abhay) Tier", "Feb 27 (Advaith)", "Feb 27 (Advaith) Tier"],
            ["https://www.tiktok.com/@one", "Macro", "", ""],
            ["", "", "https://www.tiktok.com/@two", "Submicro"],
            ["https://www.instagram.com/three", "Micro", "", ""],
        ]
    )  # type: ignore[assignment]
    client._columns = SheetColumns(creator_url=None, creator_tier=None, status=None, matrix_mode=True)

    rows = client.fetch_unprocessed(batch_size=10)
    assert len(rows) == 3
    observed = {(row.creator_url, row.creator_tier) for row in rows}
    assert observed == {
        ("https://www.tiktok.com/@one", "Macro"),
        ("https://www.tiktok.com/@two", "Submicro"),
        ("https://www.instagram.com/three", "Micro"),
    }


def test_fetch_unprocessed_detects_instagram_url_named_column() -> None:
    client = SheetsClient.__new__(SheetsClient)
    client._sheet = _FakeSheet(
        [
            ["instagram_url", "creator_tier", "status"],
            ["https://www.instagram.com/from_header", "Micro", ""],
        ]
    )  # type: ignore[assignment]
    client._columns = client._discover_columns(url_column_name=None, tier_column_name=None, status_column_name=None)

    rows = client.fetch_unprocessed(batch_size=10)
    assert len(rows) == 1
    assert rows[0].creator_url == "https://www.instagram.com/from_header"
