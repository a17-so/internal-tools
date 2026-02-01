# scrape_profile.py
import asyncio
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

from playwright.async_api import async_playwright
from threading import Thread, Lock

# ----------------------------------------------------------------------------
# Shared Playwright browser (for faster requests on Cloud Run)
# ----------------------------------------------------------------------------
_loop = None  
_loop_thread = None  
_playwright = None  
_browser = None  
_browser_lock: Lock = Lock()

_LAUNCH_ARGS = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
]

def _ensure_loop() -> None:
    global _loop, _loop_thread
    if _loop and _loop.is_running():
        return
    _loop = asyncio.new_event_loop()

    def _runner() -> None:
        asyncio.set_event_loop(_loop)
        _loop.run_forever()

    _loop_thread = Thread(target=_runner, daemon=True)
    _loop_thread.start()


async def _ensure_browser_async() -> None:
    global _playwright, _browser
    # Double-checked locking to avoid race on warm instances
    if _playwright is not None and _browser is not None:
        return
    async with _browser_lock_async():
        if _playwright is None:
            _playwright = await async_playwright().start()
        if _browser is None:
            _browser = await _playwright.chromium.launch(headless=True, args=_LAUNCH_ARGS)


class _AsyncLockWrapper:
    def __init__(self, lock: Lock) -> None:
        self._lock = lock

    async def __aenter__(self):
        await asyncio.get_event_loop().run_in_executor(None, self._lock.acquire)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self._lock.release()


def _browser_lock_async() -> _AsyncLockWrapper:
    return _AsyncLockWrapper(_browser_lock)


async def _scrape_with_persistent_browser(url: str) -> dict:
    await _ensure_browser_async()
    assert _browser is not None
    context = await _browser.new_context(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        viewport={"width": 1920, "height": 1080},
        locale="en-US",
        timezone_id="America/Los_Angeles",
        extra_http_headers={
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        }
    )
    page = await context.new_page()
    # Evasion: remove navigator.webdriver
    await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    # Block heavy resources
    async def block_media(route):
        if route.request.resource_type in ["image", "media", "font", "stylesheet"]:
            await route.abort()
        else:
            await route.continue_()
            
    await page.route("**/*", block_media)
    
    # Keep nav/timeouts bounded to avoid Cloud Run request timeouts
    try:
        page.set_default_navigation_timeout(15000)
        page.set_default_timeout(15000)
    except Exception:
        pass
    try:
        parsed = urlparse(url)
        host = (parsed.netloc or "").lower()
        
        # For TikTok, try SearchAPI.io first
        if "tiktok.com" in host:
            # Extract username from URL
            path = (parsed.path or "").strip()
            username_match = re.search(r"/@([A-Za-z0-9_.-]+)", path)
            if username_match:
                username = username_match.group(1)
                _log("scrape.trying_searchapi", username=username)
                
                # Try SearchAPI.io first
                data = scrape_tiktok_with_searchapi(username)
                
                # If SearchAPI.io fails, fall back to Playwright
                if "error" in data:
                    _log("scrape.searchapi_failed_fallback_to_playwright", error=data.get("error"))
                    data = await scrape_tiktok(page, url)
                else:
                    _log("scrape.searchapi_success", username=username)
            else:
                # No username found in URL, use Playwright
                _log("scrape.no_username_in_url_using_playwright")
                data = await scrape_tiktok(page, url)
        elif "instagram.com" in host:
            data = await scrape_instagram(page, url)
        else:
            data = {"error": "Unsupported URL", "url": url}
        _log("scrape.persistent.raw_data", data=data)
    finally:
        await context.close()

    # Normalize to the same output shape as scrape_profile()
    out = {
        "platform": data.get("platform"),
        "name": data.get("name") or "",
        "email": data.get("email") or "",
        "ig": data.get("ig_handle") or (data.get("username") if data.get("platform") == "instagram" else ""),
        "tt": data.get("username") if data.get("platform") == "tiktok" else "",
        "igProfileUrl": f"https://www.instagram.com/{data.get('ig_handle') or data.get('username')}" if (data.get("ig_handle") or (data.get("platform") == "instagram" and data.get("username"))) else "",
        "ttProfileUrl": f"https://www.tiktok.com/@{data.get('username')}" if data.get("platform") == "tiktok" and data.get("username") else "",
    }
    
    # For link aggregator platforms, add the source URL
    if data.get("platform") == "link_aggregator":
        out["linkAggregatorUrl"] = data.get("source_url") or ""
    # Add average views if present
    if "ttAvgViews" in data:
        out["ttAvgViews"] = data["ttAvgViews"]
    if "igAvgViews" in data:
        out["igAvgViews"] = data["igAvgViews"]

    try:
        if out.get("platform") == "tiktok" and not out.get("tt"):
            path = (urlparse(url).path or "").strip()
            m = re.search(r"/@([A-Za-z0-9_.-]+)", path)
            if m:
                handle = m.group(1)
                out["tt"] = handle
                out["ttProfileUrl"] = f"https://www.tiktok.com/@{handle}"
    except Exception:
        pass
    return out


def scrape_profile_sync(url: str, timeout_seconds: float = 60.0) -> dict:
    """Synchronous wrapper that reuses a persistent Playwright browser."""
    _ensure_loop()
    fut = asyncio.run_coroutine_threadsafe(_scrape_with_persistent_browser(url), _loop)  # type: ignore[arg-type]
    return fut.result(timeout=timeout_seconds)

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+(?:\s*\(at\)\s*|@)[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", re.I)
IGNORE_EMAILS = {"example@example.com", "email@example.com", "your@email.com"}


def _log(event: str, **kwargs) -> None:
    """Simple logging function for debugging"""
    try:
        print(f"LOG({event}) {kwargs}", flush=True)
    except Exception:
        pass


def parse_int_from_text(text: str) -> int:
    if not text:
        return 0
    t = text.lower().replace(",", "").strip()
    m = re.search(r"([\d.]+)\s*([km])?\b", t)
    if not m:
        return 0
    val = float(m.group(1))
    suf = m.group(2)
    if suf == "k":
        val *= 1_000
    elif suf == "m":
        val *= 1_000_000
    return int(round(val))


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
        # Look for patterns like "ig: @username" or "instagram: username"
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
                # Filter out false positives
                if handle_lower in ["media", "instagram", "com", "www"]:
                    continue
                # Filter out domains
                if "." in handle and any(tld in handle_lower for tld in [".com", ".org", ".net", ".io", ".co", ".ee", ".ai", ".be", ".bio", ".cc", ".ke"]):
                    continue
                ig_handle = handle
                break
        
        # Also check bio_link for Instagram
        bio_link = profile.get("bio_link", "") or ""
        if not ig_handle and bio_link:
            # Check if bio_link is an Instagram URL
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


async def scrape_tiktok(page, url: str) -> dict:
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=2000)
    except Exception:
        # Proceed with whatever we have; we'll try HTML-based fallbacks
        pass
    # Give TT a moment to inject SIGI_STATE
    # Reduced from 1200ms -> 200ms as per "fail fast" request
    await page.wait_for_timeout(200)

    data = {
        "platform": "tiktok",
        "name": "",
        "username": "",
        "email": "",
    }

    # 1) Prefer SIGI_STATE JSON
    sigi_text = ""
    try:
        # Reduced from 1500ms -> 200ms since if it's there, it's there.
        sigi = await page.locator("script#SIGI_STATE").first.text_content(timeout=200)
        if sigi:
            j = json.loads(sigi)
            sigi_text = sigi or ""
            users = j.get("UserModule", {}).get("users", {})
            # Set average views to 0 (view scraping disabled)
            data["ttAvgViews"] = 0
            for _, u in users.items():
                if not isinstance(u, dict):
                    continue
                data["username"] = data["username"] or u.get("uniqueId") or ""
                data["name"] = data["name"] or u.get("nickname") or ""
                break
    except Exception:
        pass

    # 2) Fallbacks from HTML
    html = await page.content()

    if not data["username"]:
        m = re.search(r"tiktok\.com\/@([A-Za-z0-9_.]+)", html)
        if m:
            data["username"] = m.group(1)

    if not data["name"]:
        # <title>Nickname (@handle) | TikTok</title>
        m = re.search(r"<title>([^<]+)</title>", html)
        if m:
            title = m.group(1)
            _log("tiktok.html_title", title=title)
            data["name"] = title.split("(")[0].strip()

    # Look for an explicit Instagram profile link on TikTok profile (bio/link section)
    # Covers:
    # - Direct links: https://instagram.com/username
    # - Instagram deep links: instagram://user?username=username
    # - IG login redirect links: https://instagram.com/accounts/login/?next=/username/
    # - IG redirector links: https://l.instagram.com/?u=<encoded instagram url>
    try:
        if not data.get("ig_handle"):
            # instagram:// deep link
            m_deeplink = re.search(r"instagram:\/\/user\?username=([A-Za-z0-9_.]+)", html or "", re.I)
            if m_deeplink:
                handle = (m_deeplink.group(1) or "").strip().lstrip("@")
                if handle and handle.lower() != "media":
                    data["ig_handle"] = handle

        if not data.get("ig_handle"):
            # Extract from hrefs referencing instagram domains (including redirectors)
            hrefs = re.findall(r"href=\"([^\"]+)\"", html or "", re.I)
            for href in hrefs:
                raw_href = href
                try:
                    href_l = raw_href.lower()
                    # l.instagram.com redirector
                    if "l.instagram.com" in href_l:
                        parsed = urlparse(raw_href)
                        q = parse_qs(parsed.query)
                        u_vals = q.get("u") or q.get("url") or []
                        if u_vals:
                            target = unquote(u_vals[0])
                            href_l = target.lower()
                            raw_href = target
                    # instagram login redirect with next=
                    if ("instagram.com/accounts/login" in href_l) and ("next=" in raw_href):
                        parsed = urlparse(raw_href)
                        q = parse_qs(parsed.query)
                        next_vals = q.get("next") or []
                        if next_vals:
                            next_path = unquote(next_vals[0])
                            raw_href = f"https://www.instagram.com{next_path}"
                            href_l = raw_href.lower()
                    # instagram:// deep link surfaced in hrefs
                    if href_l.startswith("instagram://user?username="):
                        handle = raw_href.split("instagram://user?username=")[-1].split("&")[0]
                        handle = (handle or "").strip().lstrip("@").strip()
                        if handle and handle.lower() != "media":
                            data["ig_handle"] = handle
                            break
                    # Direct instagram.com/username
                    m = re.search(
                        r"(?:https?:\/\/)?(?:www\.)?instagram\.com\/(?!p\/|reel\/|stories\/|explore\/|direct\/|accounts\/)([A-Za-z0-9_.]+)(?:[\/?#]|$)",
                        raw_href,
                        re.I,
                    )
                    if m:
                        handle = (m.group(1) or "").strip().lstrip("@")
                        if handle and handle.lower() != "media":
                            data["ig_handle"] = handle
                            break
                except Exception:
                    continue

        # Also consider any links present inside SIGI_STATE JSON when multiple links exist
        if not data.get("ig_handle") and sigi_text:
            try:
                # Collect candidate URLs found in the JSON blob
                json_urls = re.findall(r"(?:https?:\/\/|instagram\.com\/)[^\"\s]+", sigi_text or "", re.I)
                for href in json_urls:
                    raw_href = href
                    href_l = raw_href.lower()
                    # l.instagram.com redirector
                    if "l.instagram.com" in href_l:
                        parsed = urlparse(raw_href)
                        q = parse_qs(parsed.query)
                        u_vals = q.get("u") or q.get("url") or []
                        if u_vals:
                            target = unquote(u_vals[0])
                            href_l = target.lower()
                            raw_href = target
                    # instagram login redirect with next=
                    if ("instagram.com/accounts/login" in href_l) and ("next=" in raw_href):
                        parsed = urlparse(raw_href)
                        q = parse_qs(parsed.query)
                        next_vals = q.get("next") or []
                        if next_vals:
                            next_path = unquote(next_vals[0])
                            raw_href = f"https://www.instagram.com{next_path}"
                            href_l = raw_href.lower()
                    # instagram:// deep link
                    if href_l.startswith("instagram://user?username="):
                        handle = raw_href.split("instagram://user?username=")[-1].split("&")[0]
                        handle = (handle or "").strip().lstrip("@").strip()
                        if handle and handle.lower() != "media":
                            data["ig_handle"] = handle
                            break
                    # Direct instagram.com/username
                    m = re.search(
                        r"(?:https?:\/\/)?(?:www\.)?instagram\.com\/(?!p\/|reel\/|stories\/|explore\/|direct\/|accounts\/)([A-Za-z0-9_.]+)(?:[\/?#]|$)",
                        raw_href,
                        re.I,
                    )
                    if m:
                        handle = (m.group(1) or "").strip().lstrip("@")
                        if handle and handle.lower() != "media":
                            data["ig_handle"] = handle
                            break
            except Exception:
                pass

        if not data.get("ig_handle"):
            # Last-resort regex anywhere in HTML (may catch IG in JSON/script text)
            ig_link_match = re.search(
                r"(?:https?:\/\/)?(?:www\.)?instagram\.com\/(?!p\/|reel\/|stories\/|explore\/|direct\/|accounts\/)([A-Za-z0-9_.]+)(?:[\/?#]|$)",
                html or "",
                re.I,
            )
            if ig_link_match:
                handle = (ig_link_match.group(1) or "").strip().lstrip("@")
                if handle and handle.lower() not in {"media"}:
                    data["ig_handle"] = handle
    except Exception:
        pass

    # Look for IG handle in bio text as a fallback
    if not data.get("ig_handle"):
        ig_patterns = [
            r"(?:ig|insta|instagram):\s*@?([A-Za-z0-9_.]+)",
            r"(?:ig|insta|instagram)\s+@?([A-Za-z0-9_.]+)",
            r"@([A-Za-z0-9_.]+)",
        ]
        for pattern in ig_patterns:
            ig_match = re.search(pattern, html, re.I)
            if ig_match:
                handle = (ig_match.group(1) or "").strip().lstrip("@")
                # Filter out known false positives
                handle_lower = handle.lower()
                if handle_lower in ["media", "instagram", "com", "www"]:
                    continue
                # Filter out URLs that contain dots but are likely domains (not IG handles)
                # IG handles can contain dots, but domains typically have TLD patterns
                if "." in handle and not handle_lower.startswith("www."):
                    # Check if it looks like a domain (has common TLDs)
                    if any(tld in handle_lower for tld in [".com", ".org", ".net", ".io", ".co", ".ee", ".ai", ".be", ".bio", ".cc", ".ke"]):
                        _log("tiktok.filtered_domain_as_ig", handle=handle)
                        continue
                data["ig_handle"] = handle
                _log("tiktok.found_ig_handle", handle=handle)
                break


    # Emails anywhere on page
    email_match = EMAIL_RE.search(html or "")
    if email_match:
        extracted = email_match.group(0).replace("(at)", "@").replace(" ", "")
        if extracted.lower() not in IGNORE_EMAILS:
            data["email"] = extracted

    return data


async def scrape_instagram(page, url: str) -> dict:
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=5000)
    except Exception:
        pass
    await page.wait_for_timeout(800)

    data = {
        "platform": "instagram",
        "name": "",
        "username": "",
        "email": "",
    }

    # Canonical link → username
    try:
        canon = await page.locator('link[rel="canonical"]').first.get_attribute("href")
        if canon:
            m = re.search(r"instagram\.com/([^/?#]+)/?", canon)
            if m:
                data["username"] = m.group(1)
    except Exception:
        pass


    # og:title often contains the display name
    try:
        title = await page.locator('meta[property="og:title"]').first.get_attribute("content")
        if title:
            data["name"] = title.split("•")[0].strip()
    except Exception:
        pass

    # Set average views to 0 (view scraping disabled)
    data["igAvgViews"] = 0

    # Emails anywhere on the page
    html = await page.content()
    email_match = EMAIL_RE.search(html or "")
    if email_match:
        extracted = email_match.group(0).replace("(at)", "@").replace(" ", "")
        if extracted.lower() not in IGNORE_EMAILS:
            data["email"] = extracted

    return data




if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scrape_profile.py <profile_url>")
        sys.exit(1)
    url = sys.argv[1]
    # Use the persistent browser approach for CLI usage
    result = scrape_profile_sync(url)
    print(json.dumps(result, ensure_ascii=False, indent=2))





