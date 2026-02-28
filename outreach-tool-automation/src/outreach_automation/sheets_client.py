from __future__ import annotations

from dataclasses import dataclass

import google.auth
import gspread
from google.oauth2.service_account import Credentials
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from outreach_automation.models import LeadRow

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]


@dataclass(slots=True)
class SheetColumns:
    creator_url: int | None
    creator_tier: int | None
    status: int | None
    matrix_mode: bool = False


class SheetsClient:
    def __init__(
        self,
        service_account_path: str | None,
        sheet_id: str,
        worksheet_name: str,
        *,
        url_column_name: str | None = None,
        tier_column_name: str | None = None,
        status_column_name: str | None = None,
    ) -> None:
        if service_account_path:
            creds = Credentials.from_service_account_file(  # type: ignore[no-untyped-call]
                service_account_path,
                scopes=_SCOPES,
            )
        else:
            creds, _ = google.auth.default(scopes=_SCOPES)
        self._gc = gspread.authorize(creds)
        self._sheet = self._gc.open_by_key(sheet_id).worksheet(worksheet_name)
        self._columns = self._discover_columns(
            url_column_name=url_column_name,
            tier_column_name=tier_column_name,
            status_column_name=status_column_name,
        )

    def _discover_columns(
        self,
        *,
        url_column_name: str | None,
        tier_column_name: str | None,
        status_column_name: str | None,
    ) -> SheetColumns:
        header = self._sheet.row_values(1)
        lower = [h.strip().lower() for h in header]

        def idx(candidates: list[str], label: str) -> int:
            for candidate in candidates:
                normalized = candidate.strip().lower()
                if not normalized:
                    continue
                if normalized in lower:
                    return lower.index(normalized) + 1
            raise ValueError(f"Missing required column for {label}. Tried: {candidates}")

        def idx_optional(candidates: list[str]) -> int | None:
            for candidate in candidates:
                normalized = candidate.strip().lower()
                if not normalized:
                    continue
                if normalized in lower:
                    return lower.index(normalized) + 1
            return None

        url_candidates = [url_column_name] if url_column_name else []
        url_candidates.extend(["creator_url", "url", "tiktok_url", "creator link"])

        tier_candidates = [tier_column_name] if tier_column_name else []
        tier_candidates.extend(["creator_tier", "tier", "category", "creator_type", "type"])

        status_candidates = [status_column_name] if status_column_name else ["status"]

        creator_url_col = idx_optional(url_candidates)
        status_col = idx_optional(status_candidates)
        matrix_mode = creator_url_col is None
        return SheetColumns(
            creator_url=creator_url_col,
            creator_tier=idx_optional(tier_candidates),
            status=status_col,
            matrix_mode=matrix_mode,
        )

    @retry(
        reraise=True,
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type(gspread.exceptions.APIError),
    )
    def fetch_unprocessed(self, batch_size: int, row_index: int | None = None) -> list[LeadRow]:
        rows = self._sheet.get_all_values()
        if self._columns.matrix_mode:
            return self._fetch_matrix_urls(rows=rows, batch_size=batch_size, row_index=row_index)

        data_rows = rows[1:]
        out: list[LeadRow] = []
        for offset, row in enumerate(data_rows, start=2):
            if row_index is not None and offset != row_index:
                continue

            status = self._get_cell(row, self._columns.status)
            if status.strip().lower() == "processed":
                continue

            creator_url = self._get_cell(row, self._columns.creator_url)
            creator_tier = self._get_cell(row, self._columns.creator_tier)
            out.append(
                LeadRow(
                    row_index=offset,
                    creator_url=creator_url,
                    creator_tier=creator_tier,
                    status=status,
                )
            )
            if len(out) >= batch_size:
                break
        return out

    def update_status(self, row_index: int, status: str) -> None:
        if self._columns.status is None:
            return
        self._sheet.update_cell(row_index, self._columns.status, status)

    @staticmethod
    def _get_cell(row: list[str], col_index_one_based: int | None) -> str:
        if col_index_one_based is None:
            return ""
        idx = col_index_one_based - 1
        if idx >= len(row):
            return ""
        return row[idx]

    def append_note(self, row_index: int, note: str) -> None:
        _ = (row_index, note)
        # Hook for future expansion if notes/comments column gets added.
        return None

    def _fetch_matrix_urls(
        self,
        *,
        rows: list[list[str]],
        batch_size: int,
        row_index: int | None,
    ) -> list[LeadRow]:
        target_col = self._find_first_link_column(rows)
        if target_col is None:
            return []

        out: list[LeadRow] = []
        seen: set[str] = set()
        for r_idx, row in enumerate(rows[1:], start=2):
            if row_index is not None and r_idx != row_index:
                continue
            value = self._get_cell(row, target_col).strip()
            if not value:
                continue
            lower = value.lower()
            if not (lower.startswith("http://") or lower.startswith("https://")):
                continue
            if "tiktok.com/" not in lower:
                continue
            if value in seen:
                continue
            seen.add(value)
            out.append(
                LeadRow(
                    row_index=r_idx,
                    col_index=target_col,
                    creator_url=value,
                    creator_tier="",
                    status="",
                )
            )
            if len(out) >= batch_size:
                return out
        return out

    def _find_first_link_column(self, rows: list[list[str]]) -> int | None:
        first_col: int | None = None
        for row in rows[1:]:
            for c_idx, cell in enumerate(row, start=1):
                value = cell.strip().lower()
                if not value:
                    continue
                if not (value.startswith("http://") or value.startswith("https://")):
                    continue
                if "tiktok.com/" not in value:
                    continue
                if first_col is None or c_idx < first_col:
                    first_col = c_idx
        return first_col
