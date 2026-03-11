"""Google Sheets operations for the outreach tool."""

import re
from typing import Dict, Any, List, Optional
from datetime import datetime
from zoneinfo import ZoneInfo

from utils import _log
from google_services import _sheets_client


# Cache for sheet IDs to avoid repeated API calls
_SHEET_ID_CACHE: Dict[str, int] = {}
_SHEET_TITLE_CACHE: Dict[str, List[str]] = {}

# Accept common tab naming variants for newer categories.
_SHEET_NAME_ALIASES = {
    "YT Creators": ["YT Creators", "YouTube Creators", "YouTube Creator", "YT Creator"],
    "AI Influencers": ["AI Influencers", "AI influencers", "AI Influencer"],
}


def _hyperlink_formula(url: str, label: str) -> str:
    """Create a Google Sheets HYPERLINK formula."""
    if not url:
        return label or ""
    escaped_url = url.replace('"', '""')
    escaped_label = (label or "").replace('"', '""')
    return f'=HYPERLINK("{escaped_url}", "{escaped_label}")'


def col_num_to_letter(n: int) -> str:
    """Convert 0-based column index to Excel-style letter (0->A, 25->Z, 26->AA)."""
    result = ""
    while n >= 0:
        result = chr(n % 26 + ord('A')) + result
        n = n // 26 - 1
    return result


def _get_sheet_id(service: Any, spreadsheet_id: str, sheet_name: str) -> Optional[int]:
    cache_key = f"{spreadsheet_id}:{sheet_name}"
    cached = _SHEET_ID_CACHE.get(cache_key)
    if cached is not None:
        return cached
    meta = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        fields="sheets(properties(sheetId,title))",
    ).execute()
    for sheet in (meta.get("sheets") or []):
        props = sheet.get("properties") or {}
        if props.get("title") == sheet_name:
            sheet_id = int(props.get("sheetId"))
            _SHEET_ID_CACHE[cache_key] = sheet_id
            return sheet_id
    return None


def _get_sheet_titles(service: Any, spreadsheet_id: str) -> List[str]:
    cache_key = f"{spreadsheet_id}:titles"
    cached = _SHEET_TITLE_CACHE.get(cache_key)
    if cached is not None:
        return cached
    meta = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        fields="sheets(properties(title))",
    ).execute()
    titles = [
        (sheet.get("properties") or {}).get("title", "")
        for sheet in (meta.get("sheets") or [])
    ]
    _SHEET_TITLE_CACHE[cache_key] = titles
    return titles


def _resolve_sheet_name(service: Any, spreadsheet_id: str, requested_sheet_name: str) -> str:
    """Resolve a requested sheet name to an existing tab title (with aliases)."""
    try:
        titles = _get_sheet_titles(service, spreadsheet_id)
        if requested_sheet_name in titles:
            return requested_sheet_name

        # Try known aliases first.
        alias_candidates = _SHEET_NAME_ALIASES.get(requested_sheet_name, [])
        for candidate in alias_candidates:
            if candidate in titles:
                _log(
                    "sheets.resolve_name.alias_match",
                    requested=requested_sheet_name,
                    resolved=candidate,
                )
                return candidate

        # Last resort: case-insensitive exact match.
        requested_lower = requested_sheet_name.lower()
        for title in titles:
            if title.lower() == requested_lower:
                _log(
                    "sheets.resolve_name.casefold_match",
                    requested=requested_sheet_name,
                    resolved=title,
                )
                return title
    except Exception as e:
        _log("sheets.resolve_name.error", requested=requested_sheet_name, error=str(e))

    # Fallback to original so caller gets the normal API error behavior.
    return requested_sheet_name


def _check_creator_exists(spreadsheet_id: str, sheet_name: str, ig_handle: str, tt_handle: str, delegated_user: Optional[str] = None) -> Dict[str, Any]:
    """Check if a creator already exists in the spreadsheet by IG or TT handle.
    
    Returns:
        {
            "exists": bool,
            "row_index": int or None (1-based row number),
            "email_message_id": str or None (for threading),
            "status": str or None (current status in sheet),
            "initial_outreach_date": str or None (date of initial outreach),
            "sent_from_email": str or None (email of sender who did initial outreach)
        }
    """
    service = _sheets_client(delegated_user=delegated_user)
    if not service:
        _log("sheets.check_exists.no_client")
        return {"exists": False, "error": "Sheets client not configured"}
    
    try:
        resolved_sheet_name = _resolve_sheet_name(service, spreadsheet_id, sheet_name)
        # Read all data from the sheet (columns A-K)
        _log("sheets.check_exists.request", spreadsheet_id=spreadsheet_id, sheet_name=resolved_sheet_name, ig=ig_handle, tt=tt_handle)
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"{resolved_sheet_name}!A:K"
        ).execute()
        
        values = result.get("values", [])
        if not values:
            return {"exists": False}
        
        # Normalize handles for comparison
        ig_normalized = (ig_handle or "").strip().lower().lstrip("@")
        tt_normalized = (tt_handle or "").strip().lower().lstrip("@")
        
        # Skip header row (index 0), start from row 1
        for idx, row in enumerate(values[1:], start=2):  # start=2 because row 1 is header, data starts at row 2
            if len(row) < 3:
                continue
            
            # Column B (index 1) is Instagram @, Column C (index 2) is TikTok @
            ig_cell = row[1] if len(row) > 1 else ""
            tt_cell = row[2] if len(row) > 2 else ""
            
            # Extract handle from HYPERLINK formula like =HYPERLINK("url", "@handle")
            ig_match = re.search(r'@([A-Za-z0-9_.]+)', ig_cell)
            tt_match = re.search(r'@([A-Za-z0-9_.]+)', tt_cell)
            
            existing_ig = (ig_match.group(1) if ig_match else "").strip().lower()
            existing_tt = (tt_match.group(1) if tt_match else "").strip().lower()
            
            # Check if either handle matches
            if (ig_normalized and existing_ig == ig_normalized) or (tt_normalized and existing_tt == tt_normalized):
                status = row[6] if len(row) > 6 else ""  # Status is column G (index 6)
                message_id = ""  # No longer tracking message ID
                sent_from_email = row[7] if len(row) > 7 else ""  # Sent from Email is column H (index 7)
                initial_outreach_date = row[10] if len(row) > 10 else ""  # Initial Outreach Date is column K (index 10)
                
                _log("sheets.check_exists.found", row_index=idx, status=status, sent_from_email=sent_from_email)
                return {
                    "exists": True,
                    "row_index": idx,
                    "email_message_id": message_id or None,
                    "status": status or None,
                    "initial_outreach_date": initial_outreach_date or None,
                    "sent_from_email": sent_from_email or None,
                }
        
        _log("sheets.check_exists.not_found")
        return {"exists": False}
    
    except Exception as e:
        _log("sheets.check_exists.error", error=str(e))
        return {"exists": False, "error": str(e)}


def _check_creator_exists_across_all_sheets(spreadsheet_id: str, ig_handle: str, tt_handle: str, delegated_user: Optional[str] = None) -> Dict[str, Any]:
    """Check if a creator already exists in ANY of the subtabs.
    
    Returns:
        {
            "exists": bool,
            "sheet_name": str or None (which sheet the creator was found in),
            "row_index": int or None (1-based row number),
            "email_message_id": str or None (for threading),
            "status": str or None (current status in sheet)
        }
    """
    if not spreadsheet_id:
        return {"exists": False, "error": "No spreadsheet ID provided"}
    
    # Check all subtabs
    all_sheets = [
        "Macros", "Micros", "Submicros", "Ambassadors",
        "Theme Pages", "Raw Leads", "YT Creators", "AI Influencers",
    ]
    
    for sheet_name in all_sheets:
        result = _check_creator_exists(spreadsheet_id, sheet_name, ig_handle, tt_handle, delegated_user)
        if result.get("exists", False):
            result["sheet_name"] = sheet_name
            _log("sheets.check_all_sheets.found", sheet_name=sheet_name, status=result.get("status"))
            return result
    
    _log("sheets.check_all_sheets.not_found")
    return {"exists": False}


def _check_creator_exists_in_raw_leads(spreadsheet_id: str, ig_handle: str, tt_handle: str, delegated_user: Optional[str] = None) -> Dict[str, Any]:
    """Fast duplicate check ONLY in Raw Leads sheet for performance.
    
    Returns:
        {
            "exists": bool,
            "row_index": int or None (1-based row number),
            "email_message_id": str or None (for threading),
            "status": str or None (current status in sheet),
            "initial_outreach_date": str or None (date of initial outreach)
        }
    """
    if not spreadsheet_id:
        return {"exists": False, "error": "No spreadsheet ID provided"}
    
    _log("sheets.check_raw_leads_only.start", ig=ig_handle, tt=tt_handle)
    result = _check_creator_exists(spreadsheet_id, "Raw Leads", ig_handle, tt_handle, delegated_user)
    
    if result.get("exists", False):
        result["sheet_name"] = "Raw Leads"
        _log("sheets.check_raw_leads_only.found", row_index=result.get("row_index"), status=result.get("status"))
    else:
        _log("sheets.check_raw_leads_only.not_found")
    
    return result


def _get_email_from_existing_row(spreadsheet_id: str, sheet_name: str, row_index: int, delegated_user: Optional[str] = None) -> str:
    """Get email address from an existing row in the spreadsheet."""
    service = _sheets_client(delegated_user=delegated_user)
    if not service:
        return ""
    
    try:
        # Read the specific row (column D is email)
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!D{row_index}"
        ).execute()
        
        values = result.get("values", [])
        if values and len(values) > 0 and len(values[0]) > 0:
            return values[0][0] or ""
        return ""
    except Exception as e:
        _log("sheets.get_email.error", error=str(e))
        return ""


def _update_sheet_row(spreadsheet_id: str, sheet_name: str, row_index: int, row_values: List[Any], delegated_user: Optional[str] = None) -> Dict[str, Any]:
    """Update an existing row in the spreadsheet."""
    service = _sheets_client(delegated_user=delegated_user)
    if not service:
        _log("sheets.update.no_client")
        return {"ok": False, "error": "Sheets client not configured"}
    
    body = {"values": [row_values]}
    try:
        _log("sheets.update.request", spreadsheet_id=spreadsheet_id, sheet_name=sheet_name, row_index=row_index)
        resp = service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A{row_index}:K{row_index}",
            valueInputOption="USER_ENTERED",
            body=body,
        ).execute()
        _log("sheets.update.success", updated_cells=resp.get("updatedCells", 0))
        return {"ok": True, "result": resp}
    except Exception as e:
        _log("sheets.update.error", error=str(e))
        return {"ok": False, "error": str(e)}


def _append_url_to_raw_leads_column(
    spreadsheet_id: str,
    url: str,
    sender_name: str,
    creator_tier: str,
    delegated_user: Optional[str] = None,
) -> Dict[str, Any]:
    """Append URL to daily sender column and tier to paired tier column.

    URL header format remains the same as before: "Feb 27 (Abhay)".
    Creator tier is stored in a paired column: "Feb 27 (Abhay) Tier".
    """
    service = _sheets_client(delegated_user=delegated_user)
    if not service:
        _log("rawleads.matrix.no_client")
        return {"ok": False, "error": "Sheets client not configured"}

    now_pst = datetime.now(ZoneInfo("America/Los_Angeles"))
    date_str = now_pst.strftime("%b %d")
    first_name = sender_name.split()[0] if sender_name else "Unknown"
    url_header = f"{date_str} ({first_name})"
    tier_header = f"{url_header} Tier"

    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range="Raw Leads!1:1"
        ).execute()
        headers = result.get("values", [[]])[0] if result.get("values") else []

        url_col_index: int | None = None
        tier_col_index: int | None = None
        for idx, header in enumerate(headers):
            if header == url_header:
                url_col_index = idx
            if header == tier_header:
                tier_col_index = idx

        pending_writes: List[Dict[str, Any]] = []
        if url_col_index is None:
            url_col_index = len(headers)
            pending_writes.append(
                {
                    "range": f"Raw Leads!{col_num_to_letter(url_col_index)}1",
                    "values": [[url_header]],
                }
            )
            headers.append(url_header)

        if tier_col_index is None:
            tier_col_index = len(headers)
            pending_writes.append(
                {
                    "range": f"Raw Leads!{col_num_to_letter(tier_col_index)}1",
                    "values": [[tier_header]],
                }
            )
            headers.append(tier_header)

        if pending_writes:
            service.spreadsheets().values().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"valueInputOption": "USER_ENTERED", "data": pending_writes},
            ).execute()
            sheet_id = _get_sheet_id(service, spreadsheet_id, "Raw Leads")
            if sheet_id is not None:
                header_requests: List[Dict[str, Any]] = []
                for write in pending_writes:
                    a1 = write.get("range", "")
                    m = re.search(r"Raw Leads!([A-Z]+)1", a1)
                    if not m:
                        continue
                    col_letters = m.group(1)
                    col_index = 0
                    for ch in col_letters:
                        col_index = col_index * 26 + (ord(ch) - ord("A") + 1)
                    col_index -= 1
                    header_requests.append(
                        {
                            "repeatCell": {
                                "range": {
                                    "sheetId": sheet_id,
                                    "startRowIndex": 0,
                                    "endRowIndex": 1,
                                    "startColumnIndex": col_index,
                                    "endColumnIndex": col_index + 1,
                                },
                                "cell": {
                                    "userEnteredFormat": {
                                        "textFormat": {
                                            "bold": True
                                        }
                                    }
                                },
                                "fields": "userEnteredFormat.textFormat.bold",
                            }
                        }
                    )
                if header_requests:
                    service.spreadsheets().batchUpdate(
                        spreadsheetId=spreadsheet_id,
                        body={"requests": header_requests},
                    ).execute()

        url_col_letter = col_num_to_letter(url_col_index)
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"Raw Leads!{url_col_letter}:{url_col_letter}"
        ).execute()

        column_values = result.get("values", [])
        next_row = len(column_values) + 1
        for idx, row in enumerate(column_values[1:], start=2):
            cell_value = (row[0] if row else "").strip()
            if cell_value == url:
                _log("rawleads.matrix.duplicate_found", url=url, row=idx, header=url_header)
                return {
                    "ok": False,
                    "error": "Duplicate URL",
                    "message": f"URL already exists in column '{url_header}' at row {idx}",
                    "duplicate_row": idx
                }

        url_cell = f"Raw Leads!{col_num_to_letter(url_col_index)}{next_row}"
        tier_cell = f"Raw Leads!{col_num_to_letter(tier_col_index)}{next_row}"
        writes = [
            {"range": url_cell, "values": [[url]]},
            {"range": tier_cell, "values": [[creator_tier]]},
        ]
        service.spreadsheets().values().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"valueInputOption": "USER_ENTERED", "data": writes},
        ).execute()

        _log(
            "rawleads.matrix.success",
            row=next_row,
            sender=sender_name,
            tier=creator_tier,
            url_header=url_header,
            tier_header=tier_header,
        )
        return {
            "ok": True,
            "column_header": url_header,
            "tier_column_header": tier_header,
            "row_added": next_row,
            "stored_tier": creator_tier,
            "stored_sender": first_name,
        }
    except Exception as e:
        _log("rawleads.matrix.error", error=str(e))
        return {"ok": False, "error": str(e)}


def _append_url_to_subsheet(
    spreadsheet_id: str,
    sheet_name: str,
    url: str,
    sender_name: str,
    delegated_user: Optional[str] = None,
) -> Dict[str, Any]:
    """Append a URL row to a simple list-style sheet (e.g. YT Creators, AI Influencers).

    Sheet layout (auto-created headers on first write):
        A: Date Added  |  B: URL  |  C: Added By

    Duplicate check: rejects if the exact URL already appears in column B.
    """
    service = _sheets_client(delegated_user=delegated_user)
    if not service:
        _log("subsheet.append.no_client", sheet_name=sheet_name)
        return {"ok": False, "error": "Sheets client not configured"}

    now_pst = datetime.now(ZoneInfo("America/Los_Angeles"))
    date_str = now_pst.strftime("%Y-%m-%d %H:%M")
    first_name = sender_name.split()[0] if sender_name else "Unknown"

    try:
        resolved_sheet_name = _resolve_sheet_name(service, spreadsheet_id, sheet_name)
        # Read existing column B to detect duplicates and find length
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"{resolved_sheet_name}!B:B"
        ).execute()
        col_b_values = result.get("values", [])

        # Ensure header row exists
        if not col_b_values or (col_b_values[0] and col_b_values[0][0] != "URL"):
            pending_headers = [
                {"range": f"{resolved_sheet_name}!A1", "values": [["Date Added"]]},
                {"range": f"{resolved_sheet_name}!B1", "values": [["URL"]]},
                {"range": f"{resolved_sheet_name}!C1", "values": [["Added By"]]},
            ]
            service.spreadsheets().values().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"valueInputOption": "USER_ENTERED", "data": pending_headers},
            ).execute()
            # Bold the header row
            sheet_id = _get_sheet_id(service, spreadsheet_id, resolved_sheet_name)
            if sheet_id is not None:
                service.spreadsheets().batchUpdate(
                    spreadsheetId=spreadsheet_id,
                    body={
                        "requests": [{
                            "repeatCell": {
                                "range": {
                                    "sheetId": sheet_id,
                                    "startRowIndex": 0,
                                    "endRowIndex": 1,
                                    "startColumnIndex": 0,
                                    "endColumnIndex": 3,
                                },
                                "cell": {
                                    "userEnteredFormat": {
                                        "textFormat": {"bold": True}
                                    }
                                },
                                "fields": "userEnteredFormat.textFormat.bold",
                            }
                        }]
                    },
                ).execute()
            if not col_b_values:
                col_b_values = [["URL"]]

        # Duplicate check across all rows after header
        for idx, row in enumerate(col_b_values[1:], start=2):
            cell_value = (row[0] if row else "").strip()
            if cell_value == url:
                _log("subsheet.append.duplicate", sheet_name=resolved_sheet_name, url=url, row=idx)
                return {
                    "ok": False,
                    "error": "Duplicate URL",
                    "message": f"URL already exists in '{resolved_sheet_name}' at row {idx}",
                    "duplicate_row": idx,
                }

        next_row = len(col_b_values) + 1
        writes = [
            {"range": f"{resolved_sheet_name}!A{next_row}", "values": [[date_str]]},
            {"range": f"{resolved_sheet_name}!B{next_row}", "values": [[url]]},
            {"range": f"{resolved_sheet_name}!C{next_row}", "values": [[first_name]]},
        ]
        service.spreadsheets().values().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"valueInputOption": "USER_ENTERED", "data": writes},
        ).execute()

        _log(
            "subsheet.append.success",
            sheet_name=resolved_sheet_name,
            row=next_row,
            sender=first_name,
        )
        return {
            "ok": True,
            "sheet_name": resolved_sheet_name,
            "row_added": next_row,
            "stored_sender": first_name,
            "url": url,
        }

    except Exception as e:
        _log("subsheet.append.error", sheet_name=sheet_name, error=str(e))
        return {"ok": False, "error": str(e)}


def _append_to_sheet(spreadsheet_id: str, sheet_name: str, row_values: List[Any], delegated_user: Optional[str] = None) -> Dict[str, Any]:
    """Append a new row to a Google Sheet with data validation for Status column."""
    service = _sheets_client(delegated_user=delegated_user)
    if not service:
        _log("sheets.append.no_client")
        return {"ok": False, "error": "Sheets client not configured"}

    body = {"values": [row_values]}
    try:
        resolved_sheet_name = _resolve_sheet_name(service, spreadsheet_id, sheet_name)
        _log(
            "sheets.append.request",
            spreadsheet_id=spreadsheet_id,
            sheet_name=resolved_sheet_name,
            row_len=len(row_values),
            delegated_user=bool(delegated_user),
        )
        resp = service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f"{resolved_sheet_name}!A:K",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body=body,
        ).execute()
        _log("sheets.append.success", updates=resp.get("updates", {}))
        
        # After a successful append, set data validation dropdown for Status (column G)
        try:
            updates = resp.get("updates", {}) if isinstance(resp, dict) else {}
            updated_range = updates.get("updatedRange") or ""
            # Example: "Macros!A10:K10" → row 10
            m = re.search(r"![A-Z]+(\d+):", updated_range)
            if m:
                appended_row_one_based = int(m.group(1))
                row_index_zero_based = appended_row_one_based - 1

                # Lookup sheetId (cached)
                cache_key = f"{spreadsheet_id}:{resolved_sheet_name}"
                sheet_id = _SHEET_ID_CACHE.get(cache_key)
                if sheet_id is None:
                    meta = service.spreadsheets().get(
                        spreadsheetId=spreadsheet_id,
                        fields="sheets(properties(sheetId,title))",
                    ).execute()
                    for s in (meta.get("sheets") or []):
                        props = s.get("properties") or {}
                        if props.get("title") == resolved_sheet_name:
                            sheet_id = int(props.get("sheetId"))
                            _SHEET_ID_CACHE[cache_key] = sheet_id
                            break
                if sheet_id is not None:
                    # Build setDataValidation request for G column (index 6) - Status
                    request_body = {
                        "requests": [
                            {
                                "setDataValidation": {
                                    "range": {
                                        "sheetId": sheet_id,
                                        "startRowIndex": row_index_zero_based,
                                        "endRowIndex": row_index_zero_based + 1,
                                        "startColumnIndex": 6,
                                        "endColumnIndex": 7,
                                    },
                                    "rule": {
                                        "condition": {
                                            "type": "ONE_OF_LIST",
                                        "values": [
                                            {"userEnteredValue": "Sent"},
                                            {"userEnteredValue": "Followup Sent"},
                                            {"userEnteredValue": "Second Followup Sent"},
                                            {"userEnteredValue": "Third Followup Sent"},
                                            {"userEnteredValue": "Closed"},
                                            {"userEnteredValue": "Not Interested"},
                                            {"userEnteredValue": "No Email"},
                                        ],
                                        },
                                        "strict": True,
                                        "showCustomUi": True,
                                    },
                                }
                            }
                        ]
                    }
                    _log("sheets.dv.set.request", sheetId=sheet_id, row=row_index_zero_based)
                    dv_resp = service.spreadsheets().batchUpdate(
                        spreadsheetId=spreadsheet_id,
                        body=request_body,
                    ).execute()
                    _log("sheets.dv.set.success", replies=(dv_resp or {}).get("replies", []))
        except Exception as e:
            _log("sheets.dv.set.error", error=str(e))

        return {"ok": True, "result": resp}
    except Exception as e:
        _log("sheets.append.error", error=str(e))
        return {"ok": False, "error": str(e)}


def _update_creator_contact_info(
    spreadsheet_id: str,
    sheet_name: str,
    row_index: int,
    email: Optional[str] = None,
    ig_handle: Optional[str] = None,
    delegated_user: Optional[str] = None,
) -> Dict[str, Any]:
    """Update only the email (col D) and/or IG handle (col B) for an existing row.

    This is a targeted update — it only touches the specified cells and leaves
    all other columns unchanged.
    """
    service = _sheets_client(delegated_user=delegated_user)
    if not service:
        _log("sheets.update_contact.no_client")
        return {"ok": False, "error": "Sheets client not configured"}

    if not email and not ig_handle:
        return {"ok": False, "error": "Nothing to update"}

    try:
        updates_made = []

        if email:
            _log("sheets.update_contact.email", row=row_index, email=email)
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"{sheet_name}!D{row_index}",
                valueInputOption="USER_ENTERED",
                body={"values": [[email]]},
            ).execute()
            updates_made.append("email")

        if ig_handle:
            handle_clean = ig_handle.strip().lstrip("@")
            ig_url = f"https://www.instagram.com/{handle_clean}"
            ig_formula = _hyperlink_formula(ig_url, f"@{handle_clean}")
            _log("sheets.update_contact.ig", row=row_index, ig=handle_clean)
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"{sheet_name}!B{row_index}",
                valueInputOption="USER_ENTERED",
                body={"values": [[ig_formula]]},
            ).execute()
            updates_made.append("ig")

        _log("sheets.update_contact.success", updates=updates_made)
        return {"ok": True, "updated": updates_made}

    except Exception as e:
        _log("sheets.update_contact.error", error=str(e))
        return {"ok": False, "error": str(e)}
