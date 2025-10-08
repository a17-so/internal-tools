#!/usr/bin/env python3
"""
Google Sheets Migration Script

Migrates data from old format to new format:
Old format: Name, Instagram @, TikTok @, YouTube @, Followers (Instagram), Followers (TikTok), Followers (YouTube), Total Followers, Email, Status
New format: Name, Instagram @, TikTok @, Email, Average Views (Instagram), Average Views (TikTok), Status, Sent from Email, Sent from IG @, Sent from TT @, Initial Outreach Date

Handles 5 sub-sheets: Macros, Micros, Ambassadors, Theme Pages
"""

import os
import sys
import json
import re
from typing import Dict, Any, List, Optional, Tuple
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Add the current directory to Python path for imports
sys.path.insert(0, os.path.dirname(__file__))

def _log(event: str, **fields: Any) -> None:
    """Lightweight structured logging to stdout for local debugging."""
    try:
        safe_fields: Dict[str, Any] = {}
        for k, v in (fields or {}).items():
            if k.lower() in {"google_service_account_json", "credentials", "raw"}:
                continue
            if k.lower() in {"sheets_spreadsheet_id", "spreadsheet_id"} and isinstance(v, str):
                safe_fields[k] = (v[:6] + "…" + v[-4:]) if len(v) > 12 else "****"
            else:
                safe_fields[k] = v
        print(json.dumps({"event": event, **safe_fields}))
    except Exception:
        try:
            print(f"LOG({event}) {fields}")
        except Exception:
            pass

def _load_service_account_credentials(scopes: List[str], delegated_user: Optional[str] = None):
    """Load service account credentials from env."""
    raw_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")

    creds = None
    if raw_json:
        info = json.loads(raw_json)
        creds = service_account.Credentials.from_service_account_info(info, scopes=scopes)
        _log("auth.sa_json_loaded", delegated=bool(delegated_user))
    elif cred_path:
        creds = service_account.Credentials.from_service_account_file(cred_path, scopes=scopes)
        _log("auth.sa_file_loaded", path=cred_path, delegated=bool(delegated_user))
    else:
        # Fallback to default service account path within repo for local dev
        default_path = os.path.join(os.path.dirname(__file__), "service-account.json")
        try:
            if os.path.exists(default_path):
                creds = service_account.Credentials.from_service_account_file(default_path, scopes=scopes)
                _log("auth.sa_repo_default_loaded", path=default_path, delegated=bool(delegated_user))
            else:
                _log("auth.sa_missing", tried_env=True, tried_default=True)
                return None
        except Exception:
            _log("auth.sa_error_loading_default")
            return None

    if delegated_user:
        creds = creds.with_subject(delegated_user)
    return creds

def _sheets_client(delegated_user: Optional[str] = None):
    """Create Google Sheets client."""
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
    ]
    creds = _load_service_account_credentials(scopes=scopes, delegated_user=delegated_user)
    if not creds:
        _log("sheets.client_unavailable", reason="No credentials")
        return None
    return build("sheets", "v4", credentials=creds, cache_discovery=False)

def _hyperlink_formula(url: str, label: str) -> str:
    """Create Google Sheets HYPERLINK formula."""
    if not url:
        return label or ""
    safe_url = url.replace('"', '""')
    safe_label = (label or "").replace('"', '""')
    return f'=HYPERLINK("{safe_url}", "{safe_label}")'

def extract_handle_from_cell(cell_value: str) -> str:
    """Extract handle from cell value, handling HYPERLINK formulas and plain text."""
    if not cell_value:
        return ""
    
    # Handle HYPERLINK formulas like =HYPERLINK("url", "@handle")
    hyperlink_match = re.search(r'@([A-Za-z0-9_.]+)', cell_value)
    if hyperlink_match:
        return hyperlink_match.group(1)
    
    # Handle plain text handles
    plain_match = re.search(r'@?([A-Za-z0-9_.]+)', cell_value)
    if plain_match:
        return plain_match.group(1)
    
    return cell_value.strip()

def read_old_sheet_data(service, spreadsheet_id: str, sheet_name: str) -> List[List[str]]:
    """Read all data from the old sheet."""
    try:
        _log("sheets.read_old_sheet", sheet_name=sheet_name)
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A:K"  # Read columns A-K
        ).execute()
        
        values = result.get("values", [])
        _log("sheets.read_old_sheet.success", row_count=len(values), sheet_name=sheet_name)
        return values
    except Exception as e:
        _log("sheets.read_old_sheet.error", error=str(e), sheet_name=sheet_name)
        return []

def migrate_row_data(old_row: List[str]) -> List[str]:
    """
    Migrate a single row from old format to new format.
    
    Old format: Name, Instagram @, TikTok @, YouTube @, Followers (Instagram), Followers (TikTok), Followers (YouTube), Total Followers, Email, Status
    New format: Name, Instagram @, TikTok @, Email, Average Views (Instagram), Average Views (TikTok), Status, Sent from Email, Sent from IG @, Sent from TT @, Initial Outreach Date
    """
    # Ensure we have enough columns
    while len(old_row) < 11:
        old_row.append("")
    
    # Extract data from old format
    name = old_row[0] if len(old_row) > 0 else ""
    ig_handle_raw = old_row[1] if len(old_row) > 1 else ""
    tt_handle_raw = old_row[2] if len(old_row) > 2 else ""
    # Skip YouTube @ (old_row[3])
    # Skip Followers columns (old_row[4], old_row[5], old_row[6], old_row[7])
    email = old_row[8] if len(old_row) > 8 else ""
    status = old_row[9] if len(old_row) > 9 else ""
    initial_outreach_date = old_row[10] if len(old_row) > 10 else ""  # Preserve existing date if available
    
    # Extract handles
    ig_handle = extract_handle_from_cell(ig_handle_raw)
    tt_handle = extract_handle_from_cell(tt_handle_raw)
    
    # Create hyperlinks for Instagram and TikTok
    ig_link = _hyperlink_formula(f"https://www.instagram.com/{ig_handle}", f"@{ig_handle}") if ig_handle else ""
    tt_link = _hyperlink_formula(f"https://www.tiktok.com/@{tt_handle}", f"@{tt_handle}") if tt_handle else ""
    
    # New format row
    new_row = [
        name,                    # A: Name
        ig_link,                 # B: Instagram @
        tt_link,                 # C: TikTok @
        email,                   # D: Email
        0,                       # E: Average Views (Instagram) - set to 0 as we don't have this data
        0,                       # F: Average Views (TikTok) - set to 0 as we don't have this data
        status,                  # G: Status
        "",                      # H: Sent from Email - empty for now
        "",                      # I: Sent from IG @ - empty for now
        "",                      # J: Sent from TT @ - empty for now
        initial_outreach_date,   # K: Initial Outreach Date - preserve existing or empty
    ]
    
    return new_row

def write_new_sheet_data(service, spreadsheet_id: str, sheet_name: str, data: List[List[str]]) -> bool:
    """Write migrated data to the new sheet."""
    if not data:
        _log("sheets.write_new_sheet.skip_empty", sheet_name=sheet_name)
        return True
    
    try:
        # Clear existing data in the sheet (except header)
        _log("sheets.write_new_sheet.clear", sheet_name=sheet_name)
        service.spreadsheets().values().clear(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A2:K1000"  # Clear data rows, keep header
        ).execute()
        
        # Write new data
        body = {"values": data[1:]}  # Skip header row
        _log("sheets.write_new_sheet.write", sheet_name=sheet_name, row_count=len(data)-1)
        
        result = service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A2:K",
            valueInputOption="USER_ENTERED",
            body=body,
        ).execute()
        
        _log("sheets.write_new_sheet.success", 
             sheet_name=sheet_name, 
             updated_cells=result.get("updatedCells", 0))
        return True
        
    except Exception as e:
        _log("sheets.write_new_sheet.error", error=str(e), sheet_name=sheet_name)
        return False

def migrate_sheet(service, old_spreadsheet_id: str, new_spreadsheet_id: str, sheet_name: str) -> bool:
    """Migrate a single sheet from old to new format."""
    _log("migrate_sheet.start", sheet_name=sheet_name)
    
    # Read old data
    old_data = read_old_sheet_data(service, old_spreadsheet_id, sheet_name)
    if not old_data:
        _log("migrate_sheet.no_data", sheet_name=sheet_name)
        return True
    
    # Migrate data
    migrated_data = []
    for i, old_row in enumerate(old_data):
        if i == 0:  # Header row
            # Use new format header
            new_header = [
                "Name",
                "Instagram @", 
                "TikTok @",
                "Email",
                "Average Views (Instagram)",
                "Average Views (TikTok)",
                "Status",
                "Sent from Email",
                "Sent from IG @",
                "Sent from TT @",
                "Initial Outreach Date"
            ]
            migrated_data.append(new_header)
        else:
            migrated_row = migrate_row_data(old_row)
            migrated_data.append(migrated_row)
    
    # Write to new sheet
    success = write_new_sheet_data(service, new_spreadsheet_id, sheet_name, migrated_data)
    
    if success:
        _log("migrate_sheet.success", sheet_name=sheet_name, migrated_rows=len(migrated_data)-1)
    else:
        _log("migrate_sheet.failed", sheet_name=sheet_name)
    
    return success

def main():
    """Main migration function."""
    # Sheet IDs
    OLD_SHEET_ID = "1xJtBo5T4hXTGu1kEMdr-GVa1QFLFdcQDtnX9JkOM-Ys"
    NEW_SHEET_ID = "1j6EVDC2k4XML6VIGCjp23m_82gKHTSN8GjPEJPZaX5A"
    
    # Sheet names to migrate
    SHEET_NAMES = ["Macros", "Micros", "Ambassadors", "Theme Pages"]
    
    # Initialize Google Sheets client
    service = _sheets_client()
    if not service:
        print("ERROR: Could not initialize Google Sheets client. Check your credentials.")
        return False
    
    _log("migration.start", old_sheet_id=OLD_SHEET_ID, new_sheet_id=NEW_SHEET_ID)
    
    # Migrate each sheet
    success_count = 0
    for sheet_name in SHEET_NAMES:
        try:
            success = migrate_sheet(service, OLD_SHEET_ID, NEW_SHEET_ID, sheet_name)
            if success:
                success_count += 1
        except Exception as e:
            _log("migration.sheet_error", sheet_name=sheet_name, error=str(e))
    
    _log("migration.complete", 
         total_sheets=len(SHEET_NAMES), 
         successful_sheets=success_count,
         failed_sheets=len(SHEET_NAMES) - success_count)
    
    if success_count == len(SHEET_NAMES):
        print("✅ Migration completed successfully!")
        return True
    else:
        print(f"⚠️  Migration completed with {len(SHEET_NAMES) - success_count} failures.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
