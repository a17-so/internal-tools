"""Google Sheets operations for the outreach tool."""

import re
from typing import Dict, Any, List, Optional
from datetime import datetime
from zoneinfo import ZoneInfo

from utils import _log
from google_services import _sheets_client


# Cache for sheet IDs to avoid repeated API calls
_SHEET_ID_CACHE: Dict[str, int] = {}


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
        # Read all data from the sheet (columns A-K)
        _log("sheets.check_exists.request", spreadsheet_id=spreadsheet_id, sheet_name=sheet_name, ig=ig_handle, tt=tt_handle)
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A:K"
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
    all_sheets = ["Macros", "Micros", "Submicros", "Ambassadors", "Theme Pages", "Raw Leads"]
    
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


def _append_url_to_raw_leads_column(spreadsheet_id: str, url: str, sender_name: str, delegated_user: Optional[str] = None) -> Dict[str, Any]:
    """Append URL to a column in Raw Leads sheet with header format 'Jan 17 (Abhay)'.
    
    Creates a new column if one doesn't exist for today + sender.
    Checks for duplicates within the column.
    
    Args:
        spreadsheet_id: Google Sheets spreadsheet ID
        url: The URL to append
        sender_name: Name of the sender (e.g., "Abhay", "Ethan")
        delegated_user: Optional delegated user for service account
        
    Returns:
        {"ok": bool, "column_header": str, "row_added": int, "error": str}
    """
    service = _sheets_client(delegated_user=delegated_user)
    if not service:
        _log("rawleads.column.no_client")
        return {"ok": False, "error": "Sheets client not configured"}
    
    # Generate column header: "Jan 17 (Abhay)"
    now_pst = datetime.now(ZoneInfo("America/Los_Angeles"))
    date_str = now_pst.strftime("%b %d")  # "Jan 17"
    
    # Use only first name as requested
    first_name = sender_name.split()[0] if sender_name else "Unknown"
    column_header = f"{date_str} ({first_name})"
    
    try:
        # Step 1: Read the first row (headers) to find or create the column
        _log("rawleads.column.read_headers", spreadsheet_id=spreadsheet_id, header=column_header)
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range="Raw Leads!1:1"
        ).execute()
        
        headers = result.get("values", [[]])[0] if result.get("values") else []
        
        # Find column index (0-based)
        column_index = None
        for idx, header in enumerate(headers):
            if header == column_header:
                column_index = idx
                break
        
        # If column doesn't exist, create it
        if column_index is None:
            column_index = len(headers)  # Add to the end
            _log("rawleads.column.create_new", column_index=column_index, header=column_header)
            
            col_letter = col_num_to_letter(column_index)
            
            # Write header
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"Raw Leads!{col_letter}1",
                valueInputOption="USER_ENTERED",
                body={"values": [[column_header]]}
            ).execute()
            _log("rawleads.column.header_created", column=col_letter, header=column_header)
        else:
            _log("rawleads.column.found_existing", column_index=column_index, header=column_header)
        
        # Step 2: Read all values in this column to check for duplicates and find next empty row
        col_letter = col_num_to_letter(column_index)
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"Raw Leads!{col_letter}:{col_letter}"
        ).execute()
        
        column_values = result.get("values", [])
        
        # Check for duplicates (skip header row)
        for idx, row in enumerate(column_values[1:], start=2):
            if row and len(row) > 0 and row[0] == url:
                _log("rawleads.column.duplicate_found", url=url, row=idx)
                return {
                    "ok": False,
                    "error": "Duplicate URL",
                    "message": f"URL already exists in column '{column_header}' at row {idx}",
                    "column_header": column_header,
                    "duplicate_row": idx
                }
        
        # Find next empty row
        next_row = len(column_values) + 1
        
        # Step 3: Append URL to the column
        _log("rawleads.column.append_url", column=col_letter, row=next_row, url=url)
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"Raw Leads!{col_letter}{next_row}",
            valueInputOption="USER_ENTERED",
            body={"values": [[url]]}
        ).execute()
        
        _log("rawleads.column.success", column_header=column_header, row=next_row)
        return {
            "ok": True,
            "column_header": column_header,
            "row_added": next_row,
            "column_letter": col_letter
        }
        
    except Exception as e:
        _log("rawleads.column.error", error=str(e))
        return {"ok": False, "error": str(e)}


def _append_to_sheet(spreadsheet_id: str, sheet_name: str, row_values: List[Any], delegated_user: Optional[str] = None) -> Dict[str, Any]:
    """Append a new row to a Google Sheet with data validation for Status column."""
    service = _sheets_client(delegated_user=delegated_user)
    if not service:
        _log("sheets.append.no_client")
        return {"ok": False, "error": "Sheets client not configured"}

    body = {"values": [row_values]}
    try:
        _log(
            "sheets.append.request",
            spreadsheet_id=spreadsheet_id,
            sheet_name=sheet_name,
            row_len=len(row_values),
            delegated_user=bool(delegated_user),
        )
        resp = service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A:K",
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
                cache_key = f"{spreadsheet_id}:{sheet_name}"
                sheet_id = _SHEET_ID_CACHE.get(cache_key)
                if sheet_id is None:
                    meta = service.spreadsheets().get(
                        spreadsheetId=spreadsheet_id,
                        fields="sheets(properties(sheetId,title))",
                    ).execute()
                    for s in (meta.get("sheets") or []):
                        props = s.get("properties") or {}
                        if props.get("title") == sheet_name:
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
