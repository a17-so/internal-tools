"""Google API service clients (Sheets and Gmail) for the outreach tool."""

import os
import json
from typing import List, Optional, Tuple, Any

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
except Exception:
    service_account = None
    build = None

from utils import _log


def _load_service_account_credentials(scopes: List[str], delegated_user: Optional[str] = None):
    """Load service account credentials from env.

    Accepts either:
    - GOOGLE_SERVICE_ACCOUNT_JSON (raw JSON string)
    - GOOGLE_APPLICATION_CREDENTIALS (path to json file)
    - Fallback to api/service-account.json for local dev

    If delegated_user is provided, returns a delegated credentials object
    (requires domain-wide delegation to be configured in Google Admin).
    """
    if service_account is None or build is None:
        _log("google.credentials.no_library")
        return None

    creds = None
    # 1) Try GOOGLE_SERVICE_ACCOUNT_JSON (raw JSON string)
    sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if sa_json:
        try:
            info = json.loads(sa_json)
            creds = service_account.Credentials.from_service_account_info(info, scopes=scopes)
            _log("google.credentials.from_env_json")
        except Exception as e:
            _log("google.credentials.env_json_error", error=str(e))
            return None
    else:
        # 2) Try GOOGLE_APPLICATION_CREDENTIALS (path to json file)
        sa_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
        if sa_path and os.path.exists(sa_path):
            try:
                creds = service_account.Credentials.from_service_account_file(sa_path, scopes=scopes)
                _log("google.credentials.from_file", path=sa_path)
            except Exception as e:
                _log("google.credentials.file_error", error=str(e), path=sa_path)
                return None
        else:
            # 3) Fallback to service-account.json in api directory for local dev
            api_dir = os.path.dirname(__file__)
            default_path = os.path.join(api_dir, "service-account.json")
            if os.path.exists(default_path):
                try:
                    creds = service_account.Credentials.from_service_account_file(default_path, scopes=scopes)
                    _log("google.credentials.from_default_file", path=default_path)
                except Exception as e:
                    _log("google.credentials.default_file_error", error=str(e), path=default_path)
                    return None

    if creds is None:
        _log("google.credentials.none_found")
        return None

    # If delegated_user is provided, create delegated credentials
    if delegated_user:
        try:
            creds = creds.with_subject(delegated_user)
            _log("google.credentials.delegated", user=delegated_user)
        except Exception as e:
            _log("google.credentials.delegation_error", error=str(e), user=delegated_user)
            return None

    return creds



def _load_default_credentials(scopes: List[str]):
    """Deprecated: ADC disabled. Always return None."""
    return None


def _sheets_client(delegated_user: Optional[str] = None):
    """Get Google Sheets API client."""
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = _load_service_account_credentials(scopes, delegated_user=delegated_user)
    if creds is None:
        _log("sheets.client.no_credentials")
        return None
    try:
        service = build("sheets", "v4", credentials=creds, cache_discovery=False)
        _log("sheets.client.created")
        return service
    except Exception as e:
        _log("sheets.client.error", error=str(e))
        return None


def _gmail_client(delegated_user_override: Optional[str] = None) -> Optional[Tuple[Any, str]]:
    """Get Gmail API client.
    
    Returns:
        Tuple of (gmail_service, user_id) or None
    """
    scopes = ["https://www.googleapis.com/auth/gmail.send"]
    delegated_user = delegated_user_override or os.environ.get("GOOGLE_DELEGATED_USER", "").strip()
    
    creds = _load_service_account_credentials(scopes, delegated_user=delegated_user)
    if creds is None:
        _log("gmail.client.no_credentials")
        return None
    
    try:
        service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        user_id = delegated_user if delegated_user else "me"
        _log("gmail.client.created", user_id=user_id)
        return (service, user_id)
    except Exception as e:
        _log("gmail.client.error", error=str(e))
        return None
