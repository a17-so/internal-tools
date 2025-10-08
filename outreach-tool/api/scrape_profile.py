# scrape_profile.py
import asyncio
import json
import re
import sys
from urllib.parse import urlparse, parse_qs, unquote

from playwright.async_api import async_playwright
from threading import Thread, Lock

# ----------------------------------------------------------------------------
# Shared Playwright browser (for faster requests on Cloud Run)
# ----------------------------------------------------------------------------
_loop = None  # type: ignore
_loop_thread = None  # type: ignore
_playwright = None  # type: ignore
_browser = None  # type: ignore
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
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/121.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1280, "height": 800},
    )
    page = await context.new_page()
    # Keep nav/timeouts bounded to avoid Cloud Run request timeouts
    try:
        page.set_default_navigation_timeout(15000)
        page.set_default_timeout(15000)
    except Exception:
        pass
    try:
        parsed = urlparse(url)
        host = (parsed.netloc or "").lower()
        if "tiktok.com" in host:
            data = await scrape_tiktok(page, url)
        elif "instagram.com" in host:
            data = await scrape_instagram(page, url)
        elif any(domain in host for domain in LINK_AGGREGATOR_DOMAINS):
            data = await scrape_link_aggregator(page, url)
        else:
            data = {"error": "Unsupported URL", "url": url}
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
    """Synchronous wrapper that reuses a persistent Playwright browser.

    - Starts a background event loop on first call
    - Starts Playwright/Chromium once and reuses the browser across requests
    - Opens a fresh context/page per request for isolation
    """
    _ensure_loop()
    fut = asyncio.run_coroutine_threadsafe(_scrape_with_persistent_browser(url), _loop)  # type: ignore[arg-type]
    return fut.result(timeout=timeout_seconds)

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+(?:\s*\(at\)\s*|@)[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", re.I)

# Link aggregator domains to detect
LINK_AGGREGATOR_DOMAINS = [
    "linktr.ee",
    "beacons.ai", 
    "hoo.be",
    "lnk.bio",
    "linkin.bio",
    "taplink.cc",
    "msha.ke",
    "allmylinks.com",
    "bio.link",
    "linkkle.com",
    "campsite.bio"
]


def _log(event: str, **kwargs) -> None:
    """Simple logging function for debugging"""
    try:
        print(f"LOG({event}) {kwargs}")
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


async def scrape_link_aggregator(page, url: str) -> dict:
    """Scrape email and Instagram info from link aggregator services like Linktree, Beacons.ai, Hoo.be"""
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
    except Exception:
        pass
    
    await page.wait_for_timeout(2000)  # Give page time to load
    
    data = {
        "email": "",
        "ig_handle": "",
        "platform": "link_aggregator",
        "source_url": url
    }
    
    html = await page.content()
    
    # Look for email addresses anywhere on the page
    email_match = EMAIL_RE.search(html or "")
    if email_match:
        data["email"] = email_match.group(0).replace("(at)", "@").replace(" ", "")
    
    # Look for Instagram links/mentions
    # Common patterns for Instagram links on these platforms
    ig_patterns = [
        r"instagram\.com/([A-Za-z0-9_.]+)",
        r"@([A-Za-z0-9_.]+)",
        r"instagram.*?([A-Za-z0-9_.]+)",
        r"ig.*?([A-Za-z0-9_.]+)",
    ]
    
    for pattern in ig_patterns:
        ig_matches = re.findall(pattern, html, re.I)
        for match in ig_matches:
            handle = match.strip().lstrip("@").lower()
            # Filter out common false positives
            if handle and handle not in ["media", "instagram", "com", "www"] and len(handle) > 1:
                # Filter out link aggregator domains
                if any(domain in handle for domain in LINK_AGGREGATOR_DOMAINS):
                    _log("link_aggregator.filtered_link_aggregator_as_ig", handle=handle)
                    continue
                # Filter out URLs that contain dots but are likely domains (not IG handles)
                # IG handles can contain dots, but domains typically have TLD patterns
                if "." in handle and not handle.startswith("www."):
                    # Check if it looks like a domain (has common TLDs or link aggregator patterns)
                    if any(tld in handle for tld in [".com", ".org", ".net", ".io", ".co", ".ee", ".ai", ".be", ".bio", ".cc", ".ke"]):
                        _log("link_aggregator.filtered_domain_as_ig", handle=handle)
                        continue
                data["ig_handle"] = handle
                _log("link_aggregator.found_ig_handle", handle=handle)
                break
        if data["ig_handle"]:
            break
    
    # Try to find Instagram links in href attributes specifically
    if not data["ig_handle"]:
        hrefs = re.findall(r'href=["\']([^"\']+)["\']', html)
        for href in hrefs:
            if "instagram.com" in href.lower():
                m = re.search(r"instagram\.com/([A-Za-z0-9_.]+)", href, re.I)
                if m:
                    handle = m.group(1).strip().lstrip("@").lower()
                    if handle and handle not in ["media", "instagram", "com", "www"] and len(handle) > 1:
                        # Filter out link aggregator domains
                        if any(domain in handle for domain in LINK_AGGREGATOR_DOMAINS):
                            _log("link_aggregator.href_filtered_link_aggregator_as_ig", handle=handle)
                            continue
                        # Filter out URLs that contain dots but are likely domains (not IG handles)
                        # IG handles can contain dots, but domains typically have TLD patterns
                        if "." in handle and not handle.startswith("www."):
                            # Check if it looks like a domain (has common TLDs or link aggregator patterns)
                            if any(tld in handle for tld in [".com", ".org", ".net", ".io", ".co", ".ee", ".ai", ".be", ".bio", ".cc", ".ke"]):
                                _log("link_aggregator.href_filtered_domain_as_ig", handle=handle)
                                continue
                        data["ig_handle"] = handle
                        _log("link_aggregator.href_found_ig_handle", handle=handle)
                        break
    
    return data


def detect_link_aggregator_urls(text: str) -> list:
    """Detect link aggregator URLs in text content"""
    if not text:
        return []
    
    urls = []
    # Improved URL pattern that captures more URL formats
    url_patterns = [
        # Standard HTTP/HTTPS URLs
        r'https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.-])*(?:\?(?:[\w&=%.])*)?(?:#(?:[\w.])*)?)?',
        # URLs without protocol (common in bio sections)
        r'(?:^|\s)([a-zA-Z0-9][a-zA-Z0-9-]*[a-zA-Z0-9]*\.(?:linktr\.ee|beacons\.ai|hoo\.be|lnk\.bio|linkin\.bio|taplink\.cc|msha\.ke|allmylinks\.com|bio\.link|linkkle\.com|campsite\.bio)(?:/[^\s]*)?)',
        # Simple domain patterns without protocol (more flexible)
        r'(?:^|\s|"|\')((?:linktr\.ee|beacons\.ai|hoo\.be|lnk\.bio|linkin\.bio|taplink\.cc|msha\.ke|allmylinks\.com|bio\.link|linkkle\.com|campsite\.bio)(?:/[^\s"\'<>]*)?)',
        # URLs in quotes or parentheses
        r'["\'](https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.-])*(?:\?(?:[\w&=%.])*)?(?:#(?:[\w.])*)?)?)["\']',
    ]
    
    all_found_urls = []
    for pattern in url_patterns:
        found_urls = re.findall(pattern, text, re.IGNORECASE)
        all_found_urls.extend(found_urls)
    
    # Remove duplicates and normalize URLs
    seen_urls = set()
    for url in all_found_urls:
        # Clean up the URL
        url = url.strip().rstrip('.,;:!?')
        if not url:
            continue
            
        # Add protocol if missing
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            
        # Check if it's a link aggregator domain
        for domain in LINK_AGGREGATOR_DOMAINS:
            if domain in url.lower() and url not in seen_urls:
                urls.append(url)
                seen_urls.add(url)
                _log("detect_link_aggregator_urls.found", url=url, domain=domain)
                break
    
    _log("detect_link_aggregator_urls.result", found_count=len(urls), urls=urls)
    return urls


async def scrape_tiktok(page, url: str) -> dict:
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
    except Exception:
        # Proceed with whatever we have; we'll try HTML-based fallbacks
        pass
    # Give TT a moment to inject SIGI_STATE
    await page.wait_for_timeout(1200)
    data = {
        "platform": "tiktok",
        "name": "",
        "username": "",
        "email": "",
    }

    # 1) Prefer SIGI_STATE JSON
    sigi_text = ""
    try:
        sigi = await page.locator("script#SIGI_STATE").first.text_content(timeout=1500)
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
                # Filter out link aggregator domains
                if any(domain in handle_lower for domain in LINK_AGGREGATOR_DOMAINS):
                    _log("tiktok.filtered_link_aggregator_as_ig", handle=handle)
                    continue
                # Filter out URLs that contain dots but are likely domains (not IG handles)
                # IG handles can contain dots, but domains typically have TLD patterns
                if "." in handle and not handle_lower.startswith("www."):
                    # Check if it looks like a domain (has common TLDs or link aggregator patterns)
                    if any(tld in handle_lower for tld in [".com", ".org", ".net", ".io", ".co", ".ee", ".ai", ".be", ".bio", ".cc", ".ke"]):
                        _log("tiktok.filtered_domain_as_ig", handle=handle)
                        continue
                data["ig_handle"] = handle
                _log("tiktok.found_ig_handle", handle=handle)
                break


    # Emails anywhere on page
    email_match = EMAIL_RE.search(html or "")
    if email_match:
        data["email"] = email_match.group(0).replace("(at)", "@").replace(" ", "")

    # Look for link aggregator URLs in specific sections and general page content
    link_aggregator_urls = []
    
    # 1. Look for links in specific TikTok bio/link sections using selectors
    try:
        # Common TikTok link selectors - include all link aggregator domains
        link_selectors = [
            'a[data-e2e="user-bio-link"]',  # TikTok bio link
            'a[data-e2e="user-link"]',      # TikTok user link
            '[data-e2e="user-bio"] a',      # Links in bio text
            '.bio a',                       # Bio links
            '.user-bio a',                  # User bio links
        ]
        
        # Add selectors for each link aggregator domain
        for domain in LINK_AGGREGATOR_DOMAINS:
            link_selectors.append(f'a[href*="{domain}"]')
        
        for selector in link_selectors:
            try:
                elements = await page.locator(selector).all()
                for element in elements:
                    href = await element.get_attribute('href')
                    if href:
                        link_aggregator_urls.append(href)
                        _log("tiktok.found_link_selector", selector=selector, href=href)
            except Exception:
                continue
    except Exception as e:
        _log("tiktok.link_selector_error", error=str(e))
    
    # 2. Also check SIGI_STATE JSON for links (TikTok specific)
    if sigi_text:
        sigi_urls = detect_link_aggregator_urls(sigi_text)
        link_aggregator_urls.extend(sigi_urls)
        _log("tiktok.sigi_state_urls", urls=sigi_urls)
    
    # 3. Also check general HTML content with improved detection
    html_urls = detect_link_aggregator_urls(html)
    link_aggregator_urls.extend(html_urls)
    
    # Remove duplicates
    link_aggregator_urls = list(set(link_aggregator_urls))
    
    _log("tiktok.all_link_aggregator_urls", urls=link_aggregator_urls)
    
    # Scrape each found link aggregator URL
    for link_url in link_aggregator_urls:
        try:
            _log("tiktok.scraping_link_aggregator", url=link_url)
            link_data = await scrape_link_aggregator(page, link_url)
            
            # Use email from link aggregator if we don't have one yet
            if not data["email"] and link_data.get("email"):
                data["email"] = link_data["email"]
            
            # Use IG handle from link aggregator if we don't have one yet
            if not data.get("ig_handle") and link_data.get("ig_handle"):
                data["ig_handle"] = link_data["ig_handle"]
                
        except Exception as e:
            _log("tiktok.link_aggregator_error", url=link_url, error=str(e))
            continue

    return data


async def scrape_instagram(page, url: str) -> dict:
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
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
        data["email"] = email_match.group(0).replace("(at)", "@").replace(" ", "")

    # Look for link aggregator URLs in specific sections and general page content
    link_aggregator_urls = []
    
    # 1. Look for links in specific Instagram bio/link sections using selectors
    try:
        # Common Instagram link selectors
        link_selectors = [
            'a[href^="https://l.instagram.com"]',  # Instagram redirect links
            'a[data-e2e="user-bio-link"]',        # Instagram bio link
            '[data-testid="user-bio"] a',         # Bio links
            '.bio a',                             # Bio links
            '.user-bio a',                        # User bio links
            'a[href*="instagram.com/accounts/login"]',  # Instagram login redirects
        ]
        
        # Add selectors for each link aggregator domain
        for domain in LINK_AGGREGATOR_DOMAINS:
            link_selectors.append(f'a[href*="{domain}"]')
        
        for selector in link_selectors:
            try:
                elements = await page.locator(selector).all()
                for element in elements:
                    href = await element.get_attribute('href')
                    if href:
                        # Handle Instagram redirect links
                        if "l.instagram.com" in href or "instagram.com/accounts/login" in href:
                            try:
                                parsed = urlparse(href)
                                q = parse_qs(parsed.query)
                                u_vals = q.get("u") or q.get("url") or q.get("next") or []
                                if u_vals:
                                    target = unquote(u_vals[0])
                                    if not target.startswith(('http://', 'https://')):
                                        target = 'https://' + target
                                    link_aggregator_urls.append(target)
                                    _log("instagram.found_redirect_link", original=href, target=target)
                                    continue
                            except Exception:
                                pass
                        
                        link_aggregator_urls.append(href)
                        _log("instagram.found_link_selector", selector=selector, href=href)
            except Exception:
                continue
    except Exception as e:
        _log("instagram.link_selector_error", error=str(e))
    
    # 2. Also check general HTML content with improved detection
    html_urls = detect_link_aggregator_urls(html)
    link_aggregator_urls.extend(html_urls)
    
    # Remove duplicates
    link_aggregator_urls = list(set(link_aggregator_urls))
    
    _log("instagram.all_link_aggregator_urls", urls=link_aggregator_urls)
    
    # Scrape each found link aggregator URL
    for link_url in link_aggregator_urls:
        try:
            _log("instagram.scraping_link_aggregator", url=link_url)
            link_data = await scrape_link_aggregator(page, link_url)
            
            # Use email from link aggregator if we don't have one yet
            if not data["email"] and link_data.get("email"):
                data["email"] = link_data["email"]
                
        except Exception as e:
            _log("instagram.link_aggregator_error", url=link_url, error=str(e))
            continue

    return data


async def scrape_profile(url: str) -> dict:
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower()
    launch_args = [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
    ]
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=launch_args)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = await context.new_page()
        try:
            page.set_default_navigation_timeout(15000)
            page.set_default_timeout(15000)
        except Exception:
            pass

        try:
            if "tiktok.com" in host:
                data = await scrape_tiktok(page, url)
            elif "instagram.com" in host:
                data = await scrape_instagram(page, url)
            elif any(domain in host for domain in LINK_AGGREGATOR_DOMAINS):
                data = await scrape_link_aggregator(page, url)
            else:
                data = {"error": "Unsupported URL", "url": url}
        finally:
            await context.close()
            await browser.close()

    try:
        print(json.dumps({"rawProfileData": data}, ensure_ascii=False))
    except Exception:
        pass

    # Normalize and add URLs
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

    # Normalize bad IG handle '@media' → treat as not found
    try:
        ig_val = (out.get("ig") or "").strip().lstrip("@")
        if ig_val.lower() == "media":
            out["ig"] = ""
            out["igProfileUrl"] = ""
    except Exception:
        pass

    # Fallback: if TikTok username wasn't found, derive from the provided URL
    try:
        if out.get("platform") == "tiktok" and not out.get("tt"):
            path = (urlparse(url).path or "").strip()
            # Expect formats like /@handle or /@handle/video/...
            m = re.search(r"/@([A-Za-z0-9_.-]+)", path)
            if m:
                handle = m.group(1)
                out["tt"] = handle
                out["ttProfileUrl"] = f"https://www.tiktok.com/@{handle}"
    except Exception:
        pass
    return out


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scrape_profile.py <profile_url>")
        sys.exit(1)
    url = sys.argv[1]
    result = asyncio.run(scrape_profile(url))
    print(json.dumps(result, ensure_ascii=False, indent=2))


