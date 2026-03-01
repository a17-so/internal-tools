"""Utility functions for the outreach tool."""

import json
import re
from typing import Any, Dict, Optional
from urllib.parse import urlparse, parse_qs


def _log(event: str, **fields: Any) -> None:
    """Lightweight structured logging to stdout for local debugging.

    Avoids leaking secrets while giving visibility into flow.
    """
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
        # Best-effort logging; never raise from logger
        try:
            print(f"LOG({event}) {fields}")
        except Exception:
            pass


def _normalize_category(category: str) -> str:
    """Normalize category names to standard keys."""
    cat_lower = (category or "").strip().lower()
    # Map variations to canonical keys
    if cat_lower in {"macro", "macros"}:
        return "macro"
    if cat_lower in {"micro", "micros"}:
        return "micro"
    if cat_lower in {"submicro", "submicros", "sub-micro", "sub-micros"}:
        return "submicro"
    if cat_lower in {"ambassador", "ambassadors"}:
        return "ambassador"
    if cat_lower in {"themepage", "themepages", "theme-page", "theme-pages", "theme page", "theme pages"}:
        return "themepage"
    if cat_lower in {"rawlead", "rawleads", "raw-lead", "raw-leads", "raw lead", "raw leads"}:
        return "rawlead"
    return cat_lower


def _normalize_creator_tier(tier: str) -> str:
    """Normalize creator tier values to canonical sheet values."""
    tier_lower = (tier or "").strip().lower()
    if tier_lower in {"macro", "macros"}:
        return "Macro"
    if tier_lower in {"micro", "micros"}:
        return "Micro"
    if tier_lower in {"submicro", "submicros", "sub-micro", "sub-micros"}:
        return "Submicro"
    if tier_lower in {"ambassador", "ambassadors"}:
        return "Ambassador"
    if tier_lower in {"themepage", "theme page", "theme-page", "themepages", "theme pages"}:
        return "Themepage"
    return ""


def _clean_url(url: str) -> str:
    """Remove tracking parameters from TikTok/Instagram URLs.
    
    Example:
    https://www.tiktok.com/@user?_r=1&_t=8z... -> https://www.tiktok.com/@user
    """
    if not url:
        return url
    
    try:
        parsed = urlparse(url)
        # For TikTok and Instagram, remove query params and fragments
        if "tiktok.com" in parsed.netloc.lower() or "instagram.com" in parsed.netloc.lower():
            # Reconstruct URL without query and fragment
            clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            # Remove trailing slash if present
            if clean.endswith("/"):
                clean = clean[:-1]
            return clean
        # For other URLs, return as-is
        return url
    except Exception:
        # If parsing fails, return original
        return url


def _get_followup_number_from_status(status: Optional[str]) -> int:
    """Determine the followup number based on current status.
    
    Args:
        status: Current status from the spreadsheet
        
    Returns:
        followup_number: 1 for first followup, 2 for second, 3 for third
    """
    status_lower = (status or "").strip().lower()
    if "third followup" in status_lower:
        return 3  # Already sent 3 followups, this would be 4th (but we cap at 3)
    elif "second followup" in status_lower:
        return 3  # Already sent 2 followups, this is the 3rd
    elif "followup" in status_lower:
        return 2  # Already sent 1 followup, this is the 2nd
    elif status_lower in {"sent", "no email"}:
        return 1  # Initial outreach sent, this is the 1st followup
    else:
        return 1  # Default to first followup


def _get_next_status_from_current(current_status: Optional[str]) -> str:
    """Determine the next status based on current status.
    
    Args:
        current_status: Current status from the spreadsheet
        
    Returns:
        next_status: The status to set after this outreach
    """
    status_lower = (current_status or "").strip().lower()
    if "third followup" in status_lower:
        return "Third Followup Sent"  # Cap at 3 followups
    elif "second followup" in status_lower:
        return "Third Followup Sent"
    elif "followup" in status_lower:
        return "Second Followup Sent"
    elif status_lower in {"sent", "no email"}:
        return "Followup Sent"
    else:
        return "Sent"


def _markdown_to_text(markdown_str: str) -> str:
    """Convert a small subset of Markdown to readable plain text.

    Avoids leaving raw**Asterisks** and [links](url) which can hurt deliverability.
    Best-effort and safe to use for short outreach templates.
    """
    if not markdown_str:
        return ""
    text = markdown_str
    # Remove bold/italic markers
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    text = re.sub(r"_([^_]+)_", r"\1", text)
    # Convert [text](url) -> text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return text
