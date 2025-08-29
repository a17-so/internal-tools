# scrape_profile.py
import asyncio
import json
import re
import sys
from urllib.parse import urlparse

from playwright.async_api import async_playwright

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+(?:\s*\(at\)\s*|@)[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", re.I)


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


async def scrape_tiktok(page, url: str) -> dict:
    await page.goto(url, wait_until="domcontentloaded")
    # Give TT a moment to inject SIGI_STATE
    await page.wait_for_timeout(1200)
    data = {
        "platform": "tiktok",
        "name": "",
        "username": "",
        "followers": 0,
        "email": "",
    }

    # 1) Prefer SIGI_STATE JSON
    try:
        sigi = await page.locator("script#SIGI_STATE").first.text_content(timeout=1500)
        if sigi:
            j = json.loads(sigi)
            users = j.get("UserModule", {}).get("users", {})
            stats_map = j.get("UserModule", {}).get("stats", {})
            for _, u in users.items():
                if not isinstance(u, dict):
                    continue
                data["username"] = data["username"] or u.get("uniqueId") or ""
                data["name"] = data["name"] or u.get("nickname") or ""
                stat = (
                    stats_map.get(str(u.get("id")))
                    or stats_map.get(u.get("uniqueId") or "")
                    or {}
                )
                data["followers"] = int(stat.get("followerCount") or 0)
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

    # Look for IG handle in bio
    ig_patterns = [
        r"(?:ig|insta|instagram):\s*@?([A-Za-z0-9_.]+)",
        r"(?:ig|insta|instagram)\s+@?([A-Za-z0-9_.]+)",
        r"@([A-Za-z0-9_.]+)",
    ]
    for pattern in ig_patterns:
        ig_match = re.search(pattern, html, re.I)
        if ig_match:
            data["ig_handle"] = ig_match.group(1)
            break

    # Followers from various patterns
    follower_patterns = [
        r'"followerCount":\s*(\d+)',
        r'"followers":\s*(\d+)',
        r'"stats":\s*\{"followerCount":(\d+)',
        r'followerCount["\']:\s*["\']?(\d+)',
        r'data-e2e="followers-count"[^>]*>(\d+)',
        r'followers["\']:\s*["\']?(\d+)',
        r'<strong[^>]*>(\d+)</strong>[^<]*[Ff]ollower',
        r'class="[^"]*follower[^"]*"[^>]*>(\d+)',
        r'>(\d+)\s*<[^>]*[Ff]ollower(?!s\s+content)',
    ]
    for pattern in follower_patterns:
        m = re.search(pattern, html, re.I)
        if m:
            followers = parse_int_from_text(m.group(1))
            if followers > 0:
                data["followers"] = followers
                break

    # Emails anywhere on page
    email_match = EMAIL_RE.search(html or "")
    if email_match:
        data["email"] = email_match.group(0).replace("(at)", "@").replace(" ", "")

    return data


async def scrape_instagram(page, url: str) -> dict:
    await page.goto(url, wait_until="domcontentloaded")
    await page.wait_for_timeout(800)

    data = {
        "platform": "instagram",
        "name": "",
        "username": "",
        "followers": 0,
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

    # og:description often contains followers, following, posts
    try:
        desc = await page.locator('meta[property="og:description"]').first.get_attribute("content")
        if desc:
            m = re.search(r"([\d,\.]+)\s+Followers", desc, re.I)
            if m:
                data["followers"] = parse_int_from_text(m.group(1))
    except Exception:
        pass

    # og:title often contains the display name
    try:
        title = await page.locator('meta[property="og:title"]').first.get_attribute("content")
        if title:
            data["name"] = title.split("•")[0].strip()
    except Exception:
        pass

    # Emails anywhere on the page
    html = await page.content()
    email_match = EMAIL_RE.search(html or "")
    if email_match:
        data["email"] = email_match.group(0).replace("(at)", "@").replace(" ", "")

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
            if "tiktok.com" in host:
                data = await scrape_tiktok(page, url)
            elif "instagram.com" in host:
                data = await scrape_instagram(page, url)
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
        "igFollowers": data.get("followers") if data.get("platform") == "instagram" else 0,
        "ttFollowers": data.get("followers") if data.get("platform") == "tiktok" else 0,
        "igProfileUrl": f"https://www.instagram.com/{data.get('ig_handle') or data.get('username')}" if (data.get("ig_handle") or (data.get("platform") == "instagram" and data.get("username"))) else "",
        "ttProfileUrl": f"https://www.tiktok.com/@{data.get('username')}" if data.get("platform") == "tiktok" and data.get("username") else "",
    }

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


