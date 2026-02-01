#!/usr/bin/env python3
"""
Script to clean tracking parameters from 'Raw Leads' sheet.

Usage:
    python3 api/clean_tracking_links.py --app pretti --sheet "Raw Leads" --dry-run
    python3 api/clean_tracking_links.py --app pretti --sheet "Raw Leads" --apply
"""

import os
import sys
import json
import argparse
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

# Add parent directory to path to allow importing from api if needed
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import yaml
except ImportError:
    yaml = None

from google.oauth2 import service_account
from googleapiclient.discovery import build

def _log(event: str, **fields: Any) -> None:
    print(json.dumps({"event": event, **fields}))

def _clean_url(url: str) -> str:
    """Remove tracking parameters from TikTok/Instagram URLs."""
    if not url:
        return ""
    
    try:
        # Basic cleanup
        cleaned = url.strip()
        
        # Check if it's a known platform
        lower_url = cleaned.lower()
        if "tiktok.com" in lower_url or "instagram.com" in lower_url:
            # Parse URL
            parsed = urlparse(cleaned)
            
            # Reconstruct without query strings for these platforms
            path = parsed.path
            scheme = parsed.scheme or "https"
            netloc = parsed.netloc
            
            if not netloc and "tiktok.com" in path:
                 pass 
            
            new_url = f"{scheme}://{netloc}{path}"
            return new_url
            
        return cleaned
    except Exception:
        return url

# --- Configuration & Auth Parsing ---

def _load_outreach_apps_config():
    # Attempt to load from api/env.yaml
    base_dir = os.path.dirname(os.path.abspath(__file__))
    env_yaml_path = os.path.join(base_dir, "env.yaml")
    
    if os.path.exists(env_yaml_path) and yaml:
        with open(env_yaml_path, 'r') as f:
            data = yaml.safe_load(f)
            raw = data.get("OUTREACH_APPS_JSON", "")
            if raw:
                try:
                    return json.loads(raw)
                except:
                    pass
    
    # Fallback to env var
    raw = os.environ.get("OUTREACH_APPS_JSON", "")
    if raw:
        try:
             return json.loads(raw)
        except:
             pass
    return {}

def _get_app_config(app_key: str):
    apps = _load_outreach_apps_config()
    cfg = apps.get(app_key, {})
    return cfg

def _get_sheets_client(app_config):
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    
    # 1. Try GOOGLE_SERVICE_ACCOUNT_JSON env var
    sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    creds = None
    if sa_json:
        try:
            creds = service_account.Credentials.from_service_account_info(json.loads(sa_json), scopes=scopes)
        except:
            pass
    
    if not creds:
        # 2. Try service-account.json in api dir
        base_dir = os.path.dirname(os.path.abspath(__file__))
        sa_path = os.path.join(base_dir, "service-account.json")
        if os.path.exists(sa_path):
             creds = service_account.Credentials.from_service_account_file(sa_path, scopes=scopes)
    
    if not creds:
        print("Error: Could not find service account credentials.")
        return None
        
    # Delegate if needed
    delegated_user = app_config.get("delegated_user") or app_config.get("gmail_sender")
    if delegated_user:
        creds = creds.with_subject(delegated_user)
        
    return build("sheets", "v4", credentials=creds, cache_discovery=False)

def main():
    parser = argparse.ArgumentParser(description="Clean tracking links in Raw Leads")
    parser.add_argument("--app", required=True, help="App key (e.g. pretti)")
    parser.add_argument("--sheet", default="Raw Leads", help="Sheet name")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default is dry-run)")
    parser.add_argument("--dry-run", action="store_true", help="Explicit dry-run")
    
    args = parser.parse_args()
    
    # Logic
    is_dry_run = not args.apply
    
    print(f"Loading config for app: {args.app}")
    app_config = _get_app_config(args.app)
    spreadsheet_id = app_config.get("sheets_spreadsheet_id")
    
    # Fallback to env vars if not found in config (for local dev)
    if not spreadsheet_id:
        spreadsheet_id = os.environ.get("SHEETS_SPREADSHEET_ID")
        
    if not spreadsheet_id:
        print("Error: No spreadsheet_id found for this app.")
        sys.exit(1)
        
    print(f"Spreadsheet ID: {spreadsheet_id}")
    
    service = _get_sheets_client(app_config)
    if not service:
        sys.exit(1)
        
    print(f"Reading sheet: {args.sheet}")
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"{args.sheet}!A:Z"
        ).execute()
        rows = result.get("values", [])
    except Exception as e:
        print(f"Error reading sheet: {e}")
        sys.exit(1)
        
    print(f"Found {len(rows)} rows.")
    
    updates = []
    clean_count = 0
    total_links_checked = 0
    
    # Iterate rows and cells
    for r_idx, row in enumerate(rows):
        row_changed = False
        new_row = list(row)
        
        for c_idx, cell in enumerate(row):
            cell_str = str(cell)
            if "tiktok.com" in cell_str or "instagram.com" in cell_str:
                total_links_checked += 1
                cleaned = _clean_url(cell_str)
                if cleaned != cell_str:
                    print(f"[Row {r_idx+1}] Cleaning: {cell_str} -> {cleaned}")
                    new_row[c_idx] = cleaned
                    row_changed = True
                    clean_count += 1
        
        if row_changed:
            updates.append({
                "range": f"{args.sheet}!A{r_idx+1}",
                "values": [new_row]
            })

    print(f"\nChecked {total_links_checked} links.")
    print(f"Found {clean_count} links to clean.")
    
    if is_dry_run:
        print("Dry run finished. No changes made. Run with --apply to execute.")
    else:
        if updates:
            print(f"Applying {len(updates)} row updates...")
            
            data = []
            for u in updates:
                data.append(u)
                
            body = {
                "valueInputOption": "USER_ENTERED",
                "data": data
            }
            
            try:
                resp = service.spreadsheets().values().batchUpdate(
                    spreadsheetId=spreadsheet_id,
                    body=body
                ).execute()
                print("Updates applied successfully!")
            except Exception as e:
                print(f"Error applying updates: {e}")
        else:
            print("No updates needed.")

if __name__ == "__main__":
    main()
