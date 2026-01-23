#!/usr/bin/env python3
"""
Unified sheet cleanup script.

This script can:
1. Remove duplicates within a sheet (internal duplicates)
2. Remove duplicates against tracked sheets (Macros, Micros, Submicros, Ambassadors, Theme Pages)
3. Consolidate leads into a single column (Column A)
4. Filter out dates and metadata
5. Work on any sheet name

Usage:
    python3 cleanup_sheet.py --app pretti --sheet "Raw Leads Old" --remove-internal-duplicates --remove-tracked-duplicates --consolidate
"""

import os
import sys
import yaml
import json
import argparse
import re
from typing import Dict, Any, List, Set, Optional, Tuple
from google.oauth2 import service_account
from googleapiclient.discovery import build

sys.path.insert(0, os.path.dirname(__file__))

try:
    import yaml
except ImportError:
    yaml = None


def _log(event: str, **fields: Any) -> None:
    """Lightweight structured logging."""
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
        pass


def _load_outreach_apps_config() -> Dict[str, Dict[str, str]]:
    """Load outreach apps configuration from env.yaml file."""
    if yaml is None:
        return {}
    
    try:
        env_yaml_path = os.path.join(os.path.dirname(__file__), "env.yaml")
        if not os.path.exists(env_yaml_path):
            return {}
        
        with open(env_yaml_path, 'r') as f:
            yaml_data = yaml.safe_load(f)
        
        raw_config = yaml_data.get("OUTREACH_APPS_JSON", "")
        if not raw_config or not raw_config.strip():
            return {}
        
        data = json.loads(raw_config)
        if isinstance(data, dict):
            result = {str(k): (v if isinstance(v, dict) else {}) for k, v in data.items()}
            return result
    except Exception:
        pass
    
    return {}


def _get_app_config(app_key: str) -> Dict[str, str]:
    """Get app configuration."""
    key = (app_key or "").strip().lower()
    if not key:
        return {}
    
    _OUTREACH_APPS = _load_outreach_apps_config()
    specific_cfg = _OUTREACH_APPS.get(key, {})
    
    if not specific_cfg.get("sheets_spreadsheet_id"):
        legacy_sheet = os.environ.get("SHEETS_SPREADSHEET_ID") or ""
        if legacy_sheet:
            specific_cfg["sheets_spreadsheet_id"] = legacy_sheet
    if not specific_cfg.get("delegated_user"):
        legacy_delegated = os.environ.get("GOOGLE_DELEGATED_USER") or specific_cfg.get("gmail_sender") or ""
        if legacy_delegated:
            specific_cfg["delegated_user"] = legacy_delegated
    
    specific_cfg["app_key"] = key
    return specific_cfg


def _load_service_account_credentials(scopes: List[str], delegated_user: str = None):
    """Load service account credentials from env."""
    try:
        from google.oauth2 import service_account
    except ImportError:
        return None

    raw_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")

    creds = None
    if raw_json:
        info = json.loads(raw_json)
        creds = service_account.Credentials.from_service_account_info(info, scopes=scopes)
    elif cred_path:
        creds = service_account.Credentials.from_service_account_file(cred_path, scopes=scopes)
    else:
        default_path = os.path.join(os.path.dirname(__file__), "service-account.json")
        try:
            if os.path.exists(default_path):
                creds = service_account.Credentials.from_service_account_file(default_path, scopes=scopes)
        except Exception:
            pass

    if delegated_user:
        creds = creds.with_subject(delegated_user)
    return creds


def _sheets_client(delegated_user: str = None):
    """Create Google Sheets client."""
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
    ]
    creds = _load_service_account_credentials(scopes=scopes, delegated_user=delegated_user)
    if not creds:
        return None
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def extract_usernames_from_cell(cell_value: str) -> Set[str]:
    """Extract all usernames from a cell value (handles URLs, @handles, etc.)."""
    if not cell_value:
        return set()
    
    cell_str = str(cell_value).strip()
    if not cell_str:
        return set()
    
    usernames = set()
    
    # Extract from URLs
    url_patterns = [
        r'https?://(?:www\.)?(?:tiktok|instagram)\.com/@([a-zA-Z0-9_.-]+)',
        r'https?://(?:www\.)?(?:tiktok|instagram)\.com/([a-zA-Z0-9_.-]+)',
        r'tiktok\.com/@([a-zA-Z0-9_.-]+)',
        r'instagram\.com/([a-zA-Z0-9_.-]+)',
    ]
    
    for pattern in url_patterns:
        matches = re.findall(pattern, cell_str, re.IGNORECASE)
        for match in matches:
            username = match.lower().strip().rstrip('?').rstrip('/')
            if username and len(username) > 1:
                usernames.add(username)
    
    # Extract @handles
    handle_pattern = r'@([a-zA-Z0-9_.-]+)'
    handles = re.findall(handle_pattern, cell_str)
    for handle in handles:
        username = handle.lower().strip().rstrip('?').rstrip('/')
        if username and len(username) > 1:
            usernames.add(username)
    
    # If cell looks like a plain username (no @, no URL), add it
    if not any(char in cell_str for char in ['@', '/', 'http', '.com']):
        # Check if it looks like a username (alphanumeric, underscores, dots, hyphens)
        if re.match(r'^[a-zA-Z0-9_.-]+$', cell_str) and len(cell_str) > 1:
            usernames.add(cell_str.lower().strip())
    
    return usernames


def extract_all_usernames_from_row(row: List[str]) -> Set[str]:
    """Extract all usernames from all cells in a row."""
    all_usernames = set()
    for cell in row:
        if cell:
            usernames = extract_usernames_from_cell(str(cell))
            all_usernames.update(usernames)
    return all_usernames


def looks_like_date(text: str) -> bool:
    """Check if text looks like a date."""
    if not text:
        return False
    text_lower = str(text).lower().strip()
    # Common date patterns
    date_patterns = [
        r'^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}(st|nd|rd|th)?',
        r'^\d{1,2}(st|nd|rd|th)?\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)',
        r'\d{4}$',  # Ends with year
        r'\(abhay\)', r'\(ad\)', r'\(ethan\)',  # Metadata tags
        r'^(mon|tue|wed|thu|fri|sat|sun)',
    ]
    for pattern in date_patterns:
        if re.search(pattern, text_lower):
            return True
    return False


def is_valid_lead(text: str) -> bool:
    """Check if text looks like a valid lead (not metadata or date)."""
    if not text or not str(text).strip():
        return False
    text = str(text).strip()
    # Skip dates
    if looks_like_date(text):
        return False
    # Skip very short text
    if len(text) < 3:
        return False
    # Keep URLs
    if text.startswith('http://') or text.startswith('https://'):
        return True
    # Keep text with @ symbol (handles)
    if '@' in text:
        return True
    # Keep text that looks like a name or username (has letters, reasonable length)
    if re.search(r'[a-zA-Z]', text) and len(text) > 3:
        return True
    return False


def normalize_lead(lead: str) -> str:
    """Normalize a lead for comparison."""
    if not lead:
        return ""
    return str(lead).strip().lower()


def get_all_tracked_usernames(
    service,
    spreadsheet_id: str,
    tracked_sheets: List[str],
    delegated_user: Optional[str] = None
) -> Set[str]:
    """Get all usernames from tracked sheets."""
    all_usernames = set()
    
    for sheet_name in tracked_sheets:
        try:
            result = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=f"{sheet_name}!A:Z"
            ).execute()
            
            values = result.get("values", [])
            for row in values:
                usernames = extract_all_usernames_from_row(row)
                all_usernames.update(usernames)
        except Exception as e:
            # Sheet might not exist, skip it
            print(f"   Warning: Could not read sheet '{sheet_name}': {e}")
            continue
    
    return all_usernames


def cleanup_sheet(
    service,
    spreadsheet_id: str,
    sheet_name: str,
    tracked_sheets: List[str],
    delegated_user: Optional[str] = None,
    remove_internal_duplicates: bool = False,
    remove_tracked_duplicates: bool = False,
    consolidate: bool = False,
    dry_run: bool = False
) -> Dict[str, Any]:
    """Clean up a sheet: remove duplicates, consolidate, etc."""
    _log("cleanup.start", 
         sheet_name=sheet_name,
         remove_internal=remove_internal_duplicates,
         remove_tracked=remove_tracked_duplicates,
         consolidate=consolidate,
         dry_run=dry_run)
    
    print(f"\n{'='*60}")
    print(f"CLEANING UP SHEET: {sheet_name}")
    print(f"{'='*60}")
    
    # Read the sheet
    try:
        print(f"\nStep 1: Reading sheet '{sheet_name}'...")
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A:Z"
        ).execute()
        
        values = result.get("values", [])
        if not values:
            return {
                "success": True,
                "total_rows": 0,
                "internal_duplicates": 0,
                "tracked_duplicates": 0,
                "final_leads": 0,
                "message": "Sheet is empty"
            }
        
        print(f"   Found {len(values)} rows")
    except Exception as e:
        _log("cleanup.read_error", error=str(e))
        return {
            "success": False,
            "error": str(e)
        }
    
    # Extract all leads from all columns
    print(f"\nStep 2: Extracting leads from all columns...")
    all_leads: List[str] = []
    leads_by_row: List[Dict[str, Any]] = []  # Store row info for tracking
    
    for row_idx, row in enumerate(values):
        row_leads = []
        for col_idx, cell in enumerate(row):
            if cell and is_valid_lead(str(cell)):
                lead = str(cell).strip()
                row_leads.append(lead)
                all_leads.append(lead)
        
        if row_leads:
            leads_by_row.append({
                "row_index": row_idx,
                "original_row": row,
                "leads": row_leads
            })
    
    print(f"   Extracted {len(all_leads)} total leads from {len(leads_by_row)} rows")
    
    # Step 3: Remove internal duplicates
    internal_duplicates = 0
    unique_leads = []
    seen_normalized = set()
    
    if remove_internal_duplicates:
        print(f"\nStep 3: Checking for internal duplicates...")
        for item in leads_by_row:
            row_leads = item["leads"]
            row_is_duplicate = False
            
            for lead in row_leads:
                normalized = normalize_lead(lead)
                if normalized in seen_normalized:
                    row_is_duplicate = True
                    break
            
            if not row_is_duplicate:
                unique_leads.append(item)
                for lead in row_leads:
                    normalized = normalize_lead(lead)
                    seen_normalized.add(normalized)
            else:
                internal_duplicates += 1
        
        print(f"   Found {internal_duplicates} internal duplicate rows")
        print(f"   {len(unique_leads)} unique rows remaining")
    else:
        unique_leads = leads_by_row
        print(f"\nStep 3: Skipping internal duplicate check (--remove-internal-duplicates not set)")
    
    # Step 4: Remove duplicates against tracked sheets
    tracked_duplicates = 0
    final_leads = []
    
    if remove_tracked_duplicates:
        print(f"\nStep 4: Checking for duplicates against tracked sheets...")
        print(f"   Tracked sheets: {', '.join(tracked_sheets)}")
        
        tracked_usernames = get_all_tracked_usernames(
            service=service,
            spreadsheet_id=spreadsheet_id,
            tracked_sheets=tracked_sheets,
            delegated_user=delegated_user
        )
        
        print(f"   Found {len(tracked_usernames)} unique usernames in tracked sheets")
        
        for item in unique_leads:
            row_usernames = set()
            for lead in item["leads"]:
                usernames = extract_usernames_from_cell(lead)
                row_usernames.update(usernames)
            
            # Check if any username in this row matches tracked usernames
            is_duplicate = bool(row_usernames & tracked_usernames)
            
            if not is_duplicate:
                final_leads.append(item)
            else:
                tracked_duplicates += 1
                matched = row_usernames & tracked_usernames
                print(f"   Row {item['row_index'] + 1}: DUPLICATE - Matched usernames: {list(matched)[:3]}")
        
        print(f"   Found {tracked_duplicates} duplicates against tracked sheets")
        print(f"   {len(final_leads)} unique rows remaining")
    else:
        final_leads = unique_leads
        print(f"\nStep 4: Skipping tracked duplicate check (--remove-tracked-duplicates not set)")
    
    # Step 5: Consolidate to single column if requested
    if consolidate:
        print(f"\nStep 5: Consolidating leads to Column A...")
        consolidated_leads = []
        seen_consolidated = set()
        
        for item in final_leads:
            for lead in item["leads"]:
                normalized = normalize_lead(lead)
                if normalized not in seen_consolidated:
                    consolidated_leads.append(lead)
                    seen_consolidated.add(normalized)
        
        print(f"   Consolidated to {len(consolidated_leads)} unique leads in Column A")
        final_output = [[lead] for lead in consolidated_leads]
    else:
        # Keep original row structure, just filter out duplicates
        final_output = [item["original_row"] for item in final_leads]
        print(f"\nStep 5: Keeping original row structure")
    
    # Step 6: Write back to sheet
    if dry_run:
        print(f"\n⚠️  DRY RUN - No changes will be made to the sheet")
        print(f"\nSummary:")
        print(f"   Total rows: {len(values)}")
        print(f"   Internal duplicates: {internal_duplicates}")
        print(f"   Tracked duplicates: {tracked_duplicates}")
        print(f"   Final unique leads/rows: {len(final_output)}")
        return {
            "success": True,
            "dry_run": True,
            "total_rows": len(values),
            "internal_duplicates": internal_duplicates,
            "tracked_duplicates": tracked_duplicates,
            "final_leads": len(final_output)
        }
    
    print(f"\nStep 6: Writing cleaned data back to sheet...")
    try:
        # Clear the sheet
        service.spreadsheets().values().clear(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A:Z"
        ).execute()
        
        # Write cleaned data
        if final_output:
            body = {"values": final_output}
            result = service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"{sheet_name}!A1:Z",
                valueInputOption="USER_ENTERED",
                body=body,
            ).execute()
        
        print(f"   Successfully wrote {len(final_output)} rows to sheet")
        _log("cleanup.success",
             internal_duplicates_removed=internal_duplicates,
             tracked_duplicates_removed=tracked_duplicates,
             final_rows=len(final_output))
        
        return {
            "success": True,
            "total_rows": len(values),
            "internal_duplicates": internal_duplicates,
            "tracked_duplicates": tracked_duplicates,
            "final_leads": len(final_output)
        }
    except Exception as e:
        _log("cleanup.write_error", error=str(e))
        return {
            "success": False,
            "error": str(e)
        }


def inspect_sheet(
    service,
    spreadsheet_id: str,
    sheet_name: str,
    delegated_user: Optional[str] = None
) -> Dict[str, Any]:
    """Inspect a sheet and show statistics."""
    print(f"\n{'='*60}")
    print(f"INSPECTING SHEET: {sheet_name}")
    print(f"{'='*60}")
    
    try:
        # Read the sheet
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A:Z"
        ).execute()
        
        values = result.get("values", [])
        if not values:
            print("Sheet is empty")
            return {"success": True, "total_rows": 0}
        
        print(f"\nTotal rows: {len(values)}")
        
        # Count non-empty cells per column
        max_cols = max(len(row) for row in values) if values else 0
        column_counts = [0] * max_cols
        column_samples = [None] * max_cols
        
        for row in values:
            for col_idx in range(min(len(row), max_cols)):
                cell_value = row[col_idx] if col_idx < len(row) else ""
                if cell_value and str(cell_value).strip():
                    column_counts[col_idx] += 1
                    if column_samples[col_idx] is None:
                        column_samples[col_idx] = str(cell_value)[:50]
        
        print(f"\nColumn statistics:")
        print("-" * 60)
        for col_idx in range(max_cols):
            if column_counts[col_idx] > 0:
                col_letter = chr(65 + col_idx) if col_idx < 26 else f"{chr(65 + (col_idx-26)//26)}{chr(65 + (col_idx-26)%26)}"
                count = column_counts[col_idx]
                sample = column_samples[col_idx] or "(empty)"
                print(f"  Column {col_letter} ({col_idx:2d}): {count:4d} non-empty cells | Sample: {sample}")
        
        print(f"\nSummary:")
        print(f"  Total columns with data: {sum(1 for c in column_counts if c > 0)}")
        if max(column_counts) > 0:
            max_col_idx = column_counts.index(max(column_counts))
            col_letter = chr(65 + max_col_idx) if max_col_idx < 26 else f"{chr(65 + (max_col_idx-26)//26)}{chr(65 + (max_col_idx-26)%26)}"
            print(f"  Column with most data: {col_letter} ({max(column_counts)} cells)")
        
        # Count unique leads
        all_leads = []
        for row in values:
            for cell in row:
                if cell and is_valid_lead(str(cell)):
                    all_leads.append(str(cell).strip())
        
        unique_leads = len(set(normalize_lead(lead) for lead in all_leads))
        print(f"  Total valid leads: {len(all_leads)}")
        print(f"  Unique leads: {unique_leads}")
        
        return {
            "success": True,
            "total_rows": len(values),
            "total_columns": max_cols,
            "columns_with_data": sum(1 for c in column_counts if c > 0),
            "total_leads": len(all_leads),
            "unique_leads": unique_leads
        }
    except Exception as e:
        print(f"ERROR: {e}")
        return {"success": False, "error": str(e)}


def list_sheets(
    service,
    spreadsheet_id: str,
    delegated_user: Optional[str] = None
) -> List[str]:
    """List all sheets in the spreadsheet."""
    try:
        result = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        sheets = result.get('sheets', [])
        sheet_names = [sheet['properties']['title'] for sheet in sheets]
        return sheet_names
    except Exception as e:
        print(f"ERROR listing sheets: {e}")
        return []


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Unified sheet cleanup and inspection script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all sheets
  python3 cleanup_sheet.py --app pretti --list-sheets
  
  # Inspect a sheet (show statistics)
  python3 cleanup_sheet.py --app pretti --sheet "Raw Leads Old" --inspect
  
  # Check for duplicates (dry run)
  python3 cleanup_sheet.py --app pretti --sheet "Raw Leads Old" --dry-run --remove-internal-duplicates --remove-tracked-duplicates
  
  # Remove internal duplicates only
  python3 cleanup_sheet.py --app pretti --sheet "Raw Leads Old" --remove-internal-duplicates
  
  # Remove duplicates against tracked sheets
  python3 cleanup_sheet.py --app pretti --sheet "Raw Leads" --remove-tracked-duplicates
  
  # Full cleanup: remove all duplicates and consolidate to single column
  python3 cleanup_sheet.py --app pretti --sheet "Raw Leads Old" --remove-internal-duplicates --remove-tracked-duplicates --consolidate
        """
    )
    parser.add_argument(
        "--app",
        required=True,
        choices=["pretti", "lifemaxx", "hardmaxx"],
        help="App name (pretti, lifemaxx, or hardmaxx)"
    )
    parser.add_argument(
        "--sheet",
        help="Name of the sheet to clean up (required unless --list-sheets is used)"
    )
    parser.add_argument(
        "--list-sheets",
        action="store_true",
        help="List all sheets in the spreadsheet"
    )
    parser.add_argument(
        "--inspect",
        action="store_true",
        help="Inspect sheet and show statistics (no modifications)"
    )
    parser.add_argument(
        "--remove-internal-duplicates",
        action="store_true",
        help="Remove duplicate leads within the sheet itself"
    )
    parser.add_argument(
        "--remove-tracked-duplicates",
        action="store_true",
        help="Remove duplicates that exist in tracked sheets (Macros, Micros, Submicros, Ambassadors, Theme Pages)"
    )
    parser.add_argument(
        "--consolidate",
        action="store_true",
        help="Consolidate all leads into Column A (one lead per row)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode - don't actually modify the sheet, just report"
    )
    parser.add_argument(
        "--tracked-sheets",
        nargs="+",
        default=["Macros", "Micros", "Submicros", "Ambassadors", "Theme Pages"],
        help="List of tracked sheets to check against (default: Macros Micros Submicros Ambassadors 'Theme Pages')"
    )
    
    args = parser.parse_args()
    
    # Get app configuration
    app_config = _get_app_config(args.app)
    if not app_config:
        print(f"ERROR: Could not load configuration for app '{args.app}'")
        sys.exit(1)
    
    spreadsheet_id = app_config.get("sheets_spreadsheet_id")
    delegated_user = app_config.get("delegated_user") or app_config.get("gmail_sender")
    
    if not spreadsheet_id:
        print(f"ERROR: No spreadsheet ID configured for app '{args.app}'")
        sys.exit(1)
    
    print(f"App: {args.app}")
    print(f"Spreadsheet ID: {spreadsheet_id[:6]}...{spreadsheet_id[-4:]}")
    
    # Initialize Google Sheets client
    service = _sheets_client(delegated_user=delegated_user)
    if not service:
        print("ERROR: Could not initialize Google Sheets client. Check your credentials.")
        sys.exit(1)
    
    # Handle list-sheets mode
    if args.list_sheets:
        print(f"\nListing all sheets in {args.app.upper()} spreadsheet...")
        sheet_names = list_sheets(service, spreadsheet_id, delegated_user)
        if sheet_names:
            print(f"\nFound {len(sheet_names)} sheets:")
            for name in sheet_names:
                print(f"  - {name}")
        else:
            print("No sheets found or error listing sheets")
        return
    
    # Sheet name is required for other operations
    if not args.sheet:
        print("ERROR: --sheet is required unless --list-sheets is used")
        sys.exit(1)
    
    print(f"Sheet: {args.sheet}")
    
    # Handle inspect mode
    if args.inspect:
        result = inspect_sheet(
            service=service,
            spreadsheet_id=spreadsheet_id,
            sheet_name=args.sheet,
            delegated_user=delegated_user
        )
        if not result.get("success"):
            print(f"❌ Error: {result.get('error', 'Unknown error')}")
            sys.exit(1)
        return
    
    # If no cleanup operations requested, just do a dry-run inspection
    if not args.remove_internal_duplicates and not args.remove_tracked_duplicates and not args.consolidate:
        print("No cleanup operations specified. Running inspection...")
        result = inspect_sheet(
            service=service,
            spreadsheet_id=spreadsheet_id,
            sheet_name=args.sheet,
            delegated_user=delegated_user
        )
        if not result.get("success"):
            print(f"❌ Error: {result.get('error', 'Unknown error')}")
            sys.exit(1)
        print(f"\n💡 Tip: Use --remove-internal-duplicates, --remove-tracked-duplicates, or --consolidate to clean up the sheet")
        return
    
    print(f"Dry Run: {args.dry_run}")
    
    # Cleanup the sheet
    result = cleanup_sheet(
        service=service,
        spreadsheet_id=spreadsheet_id,
        sheet_name=args.sheet,
        tracked_sheets=args.tracked_sheets,
        delegated_user=delegated_user,
        remove_internal_duplicates=args.remove_internal_duplicates,
        remove_tracked_duplicates=args.remove_tracked_duplicates,
        consolidate=args.consolidate,
        dry_run=args.dry_run
    )
    
    # Print final results
    print(f"\n{'='*60}")
    print("FINAL RESULTS")
    print(f"{'='*60}")
    
    if result.get("success"):
        print(f"✅ Success!")
        print(f"Total rows processed: {result.get('total_rows', 0)}")
        print(f"Internal duplicates found: {result.get('internal_duplicates', 0)}")
        print(f"Tracked duplicates found: {result.get('tracked_duplicates', 0)}")
        print(f"Final unique leads/rows: {result.get('final_leads', 0)}")
        
        if args.dry_run:
            print(f"\n⚠️  DRY RUN - No changes were made to the sheet")
            print(f"   Run without --dry-run to apply changes")
        else:
            print(f"\n✅ Sheet has been cleaned up successfully!")
    else:
        print(f"❌ Error: {result.get('error', 'Unknown error')}")
        sys.exit(1)
    
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

