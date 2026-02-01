
# scrape_profile.py
import json
import re
import sys
import time
import os
from urllib.parse import urlparse, parse_qs, unquote
try:
    import requests
except ImportError:
    requests = None


def scrape_profile_sync(url: str, timeout_seconds: float = 60.0) -> dict:
    """Synchronous wrapper for scraping profiles (now pure HTTP/API).
    
    Arg timeout_seconds is kept for signature compatibility but mostly unused 
    as requests has its own timeout.
    """
    
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower()
    
    data = {}
    
    try:
        if "tiktok.com" in host:
            # TikTok: Use SearchAPI.io exclusively
            path = (parsed.path or "").strip()
            username_match = re.search(r"/@([A-Za-z0-9_.-]+)", path)
            
            if username_match:
                username = username_match.group(1)
                _log("scrape.trying_searchapi", username=username)
                data = scrape_tiktok_with_searchapi(username)
            else:
                _log("scrape.no_username_in_url")
                data = {"error": "Could not extract username from TikTok URL"}
                
        elif "instagram.com" in host:
            # Instagram: Not supported without Playwright/API
            # (If user wants IG support later, we'll need an API for that too)
            _log("scrape.instagram_not_supported_without_browser")
            data = {"error": "Instagram scraping not supported in lightweight mode"}
            
        else:
            data = {"error": "Unsupported URL", "url": url}
            
    except Exception as e:
        _log("scrape.error", error=str(e))
        data = {"error": f"Scraping failed: {str(e)}"}
        
    _log("scrape.result", data=data)

    # Normalize output
    out = {
        "platform": data.get("platform"),
        "name": data.get("name") or "",
        "email": data.get("email") or "",
        "ig": data.get("ig_handle") or (data.get("username") if data.get("platform") == "instagram" else ""),
        "tt": data.get("username") if data.get("platform") == "tiktok" else "",
        "igProfileUrl": f"https://www.instagram.com/{data.get('ig_handle') or data.get('username')}" if (data.get("ig_handle") or (data.get("platform") == "instagram" and data.get("username"))) else "",
        "ttProfileUrl": f"https://www.tiktok.com/@{data.get('username')}" if data.get("platform") == "tiktok" and data.get("username") else "",
    }
    
    # Add average views if present
    if "ttAvgViews" in data:
        out["ttAvgViews"] = data["ttAvgViews"]
    if "igAvgViews" in data:
        out["igAvgViews"] = data["igAvgViews"]

    # Ensure TT handle is populated if missing in data but present in URL
    if out.get("platform") == "tiktok" and not out.get("tt"):
        path = (urlparse(url).path or "").strip()
        m = re.search(r"/@([A-Za-z0-9_.-]+)", path)
        if m:
            handle = m.group(1)
            out["tt"] = handle
            out["ttProfileUrl"] = f"https://www.tiktok.com/@{handle}"

    return out


EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+(?:\s*\(at\)\s*|@)[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", re.I)
IGNORE_EMAILS = {"example@example.com", "email@example.com", "your@email.com"}


def _log(event: str, **kwargs) -> None:
    """Simple logging function for debugging"""
    try:
        print(f"LOG({event}) {kwargs}", flush=True)
    except Exception:
        pass


def scrape_tiktok_with_searchapi(username: str) -> dict:
    """Scrape TikTok profile using SearchAPI.io API.
    
    Args:
        username: TikTok username (with or without @)
        
    Returns:
        dict with profile data or error information
    """
    if requests is None:
        _log("searchapi.requests_not_available")
        return {"error": "requests library not available"}
    
    # Get API key from environment
    api_key = os.environ.get("SEARCHAPI_KEY", "")
    if not api_key:
        _log("searchapi.no_api_key")
        # FAIL FAST as requested
        return {"error": "SEARCHAPI_KEY not configured"}
    
    # Clean username (remove @ if present)
    clean_username = username.strip().lstrip("@")
    if not clean_username:
        return {"error": "Invalid username"}
    
    try:
        _log("searchapi.request_start", username=clean_username)
        
        # Make API request
        url = "https://www.searchapi.io/api/v1/search"
        params = {
            "engine": "tiktok_profile",
            "username": clean_username,
            "api_key": api_key
        }
        
        response = requests.get(url, params=params, timeout=10)
        # Check for 401/403 specifically to fail fast on bad key
        if response.status_code in [401, 403]:
             _log("searchapi.auth_error", status=response.status_code)
             return {"error": "Invalid SEARCHAPI_KEY"}
             
        response.raise_for_status()
        
        result = response.json()
        _log("searchapi.request_success", username=clean_username, status=result.get("search_metadata", {}).get("status"))
        
        # Extract profile data from response
        profile = result.get("profile", {})
        if not profile:
            _log("searchapi.no_profile_data", username=clean_username)
            return {"error": "No profile data in API response"}
        
        # Parse bio for email and Instagram handle
        bio = profile.get("bio", "") or ""
        email = ""
        ig_handle = ""
        
        # Extract email from bio
        email_match = EMAIL_RE.search(bio)
        if email_match:
            extracted = email_match.group(0).replace("(at)", "@").replace(" ", "")
            if extracted.lower() not in IGNORE_EMAILS:
                email = extracted
        
        # Extract Instagram handle from bio
        ig_patterns = [
            r"(?:ig|insta|instagram):\s*@?([A-Za-z0-9_.]+)",
            r"(?:ig|insta|instagram)\s+@?([A-Za-z0-9_.]+)",
            r"@([A-Za-z0-9_.]+)",
        ]
        for pattern in ig_patterns:
            ig_match = re.search(pattern, bio, re.I)
            if ig_match:
                handle = (ig_match.group(1) or "").strip().lstrip("@")
                handle_lower = handle.lower()
                if handle_lower in ["media", "instagram", "com", "www"]:
                    continue
                if "." in handle and any(tld in handle_lower for tld in [".com", ".org", ".net", ".io", ".co", ".ee", ".ai", ".be", ".bio", ".cc", ".ke"]):
                    continue
                ig_handle = handle
                break
        
        # Also check bio_link for Instagram
        bio_link = profile.get("bio_link", "") or ""
        if not ig_handle and bio_link:
            ig_link_match = re.search(
                r"(?:https?://)?(?:www\.)?instagram\.com/(?!p/|reel/|stories/|explore/|direct/|accounts/)([A-Za-z0-9_.]+)(?:[/?#]|$)",
                bio_link,
                re.I
            )
            if ig_link_match:
                handle = (ig_link_match.group(1) or "").strip().lstrip("@")
                if handle and handle.lower() not in {"media"}:
                    ig_handle = handle
        
        data = {
            "platform": "tiktok",
            "name": profile.get("name", ""),
            "username": profile.get("username", clean_username),
            "email": email,
            "ig_handle": ig_handle,
            "followers": profile.get("followers", 0),
            "following": profile.get("following", 0),
            "posts": profile.get("posts", 0),
            "hearts": profile.get("hearts", 0),
            "is_verified": profile.get("is_verified", False),
            "bio": bio,
            "ttAvgViews": 0,  # Not provided by API, set to 0
        }
        
        _log("searchapi.parse_success", username=clean_username, has_email=bool(email), has_ig=bool(ig_handle))
        return data
        
    except requests.exceptions.Timeout:
        _log("searchapi.timeout", username=clean_username)
        return {"error": "API request timeout"}
    except requests.exceptions.RequestException as e:
        _log("searchapi.request_error", username=clean_username, error=str(e))
        return {"error": f"API request failed: {str(e)}"}
    except Exception as e:
        _log("searchapi.unexpected_error", username=clean_username, error=str(e))
        return {"error": f"Unexpected error: {str(e)}"}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scrape_profile.py <profile_url>")
        sys.exit(1)
    url = sys.argv[1]
    result = scrape_profile_sync(url)
    print(json.dumps(result, ensure_ascii=False, indent=2))
