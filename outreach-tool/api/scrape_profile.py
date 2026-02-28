
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
INSTAGRAM_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?instagram\.com/(?!p/|reel/|stories/|explore/|direct/|accounts/)"
    r"([A-Za-z0-9_.]+)(?=[^A-Za-z0-9_.]|$)",
    re.I,
)
HANDLE_RE = re.compile(r"^[A-Za-z0-9._]{1,30}$")
_BLOCKED_HANDLES = {"media", "instagram", "com", "www"}
_LINK_CRAWL_TIMEOUT_SECONDS = 5.0
_LINK_CRAWL_MAX_BYTES = 350_000


def _log(event: str, **kwargs) -> None:
    """Simple logging function for debugging"""
    try:
        print(f"LOG({event}) {kwargs}", flush=True)
    except Exception:
        pass


def _is_valid_ig_handle(handle: str) -> bool:
    normalized = (handle or "").strip().lstrip("@")
    if not normalized:
        return False
    lower = normalized.lower()
    if lower in _BLOCKED_HANDLES:
        return False
    if "." in normalized and any(
        tld in lower for tld in [".com", ".org", ".net", ".io", ".co", ".ee", ".ai", ".be", ".bio", ".cc", ".ke"]
    ):
        return False
    return bool(HANDLE_RE.match(normalized))


def _extract_ig_handle_from_text(text: str) -> str:
    if not text:
        return ""
    match = INSTAGRAM_URL_RE.search(text)
    if not match:
        return ""
    handle = (match.group(1) or "").strip().lstrip("@")
    return handle if _is_valid_ig_handle(handle) else ""


def _extract_ig_handle_from_link_page(link_url: str) -> str:
    if requests is None:
        return ""
    raw = (link_url or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"}:
        return ""

    # Fast path for direct Instagram links.
    direct = _extract_ig_handle_from_text(raw)
    if direct:
        return direct

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )
    }
    try:
        response = requests.get(raw, timeout=_LINK_CRAWL_TIMEOUT_SECONDS, headers=headers, allow_redirects=True, stream=True)
        response.raise_for_status()

        chunks: list[bytes] = []
        total = 0
        for chunk in response.iter_content(chunk_size=8192):
            if not chunk:
                continue
            chunks.append(chunk)
            total += len(chunk)
            if total >= _LINK_CRAWL_MAX_BYTES:
                break

        html = b"".join(chunks).decode("utf-8", errors="ignore")
        if not html:
            return ""

        handle = _extract_ig_handle_from_text(html)
        if handle:
            return handle
        # Some link pages embed encoded redirect URLs.
        return _extract_ig_handle_from_text(unquote(html))
    except Exception as exc:
        _log("searchapi.bio_link_crawl_error", link=raw, error=str(exc))
        return ""


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
        
        link_crawl_enabled = os.environ.get("SCRAPE_IG_BIO_LINK_CRAWL_ENABLED", "true").strip().lower() in {"1", "true", "yes", "y"}
        same_username_fallback_enabled = (
            os.environ.get("SCRAPE_IG_SAME_USERNAME_FALLBACK", "false").strip().lower() in {"1", "true", "yes", "y"}
        )

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
            r"(?:^|[\s,;|])(?:ig|insta|instagram)\s*[:\-]\s*@?([A-Za-z0-9_.]{1,30})\b",
            r"(?:^|[\s,;|])(?:ig|insta|instagram)\s+@([A-Za-z0-9_.]{1,30})\b",
            r"@([A-Za-z0-9_.]{1,30})\b",
        ]
        for pattern in ig_patterns:
            ig_match = re.search(pattern, bio, re.I)
            if ig_match:
                handle = (ig_match.group(1) or "").strip().lstrip("@")
                if not _is_valid_ig_handle(handle):
                    continue
                ig_handle = handle
                break
        
        # Also check bio_link for Instagram
        bio_link = profile.get("bio_link", "") or ""
        if not ig_handle and bio_link:
            ig_handle = _extract_ig_handle_from_text(bio_link)

        if not ig_handle and bio_link and link_crawl_enabled:
            ig_handle = _extract_ig_handle_from_link_page(bio_link)
            if ig_handle:
                _log("searchapi.ig_from_link_page", username=clean_username, link=bio_link, ig_handle=ig_handle)

        if not ig_handle and same_username_fallback_enabled and _is_valid_ig_handle(clean_username):
            ig_handle = clean_username
            _log("searchapi.ig_from_same_username", username=clean_username, ig_handle=ig_handle)
        
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
