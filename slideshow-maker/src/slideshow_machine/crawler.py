from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

from .db import tx


POST_URL_RE = re.compile(r"https?://(?:www\.)?tiktok\.com/@(?P<handle>[A-Za-z0-9._-]+)/video/(?P<id>\d+)", re.I)


@dataclass(slots=True)
class CrawlSummary:
    accounts: int
    posts_seen: int
    posts_saved: int
    failures: int


def normalize_account(account: str) -> tuple[str, str]:
    account = account.strip()
    if not account:
        raise ValueError("Empty account handle/url")
    if account.startswith("http"):
        parsed = urlparse(account)
        m = re.search(r"/@([A-Za-z0-9._-]+)", parsed.path)
        if not m:
            raise ValueError(f"Could not parse account handle from {account}")
        handle = m.group(1)
    else:
        handle = account.lstrip("@")
    return handle, f"https://www.tiktok.com/@{handle}"


def parse_count(value: str | None) -> int:
    if not value:
        return 0
    cleaned = value.strip().replace(",", "")
    m = re.match(r"^([0-9]+(?:\.[0-9]+)?)([KMB])?$", cleaned, re.I)
    if not m:
        digits = re.sub(r"[^0-9]", "", cleaned)
        return int(digits) if digits else 0
    num = float(m.group(1))
    suffix = (m.group(2) or "").upper()
    factor = {"": 1, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000}[suffix]
    return int(num * factor)


def read_accounts(accounts_file: Path) -> list[str]:
    rows = []
    for line in accounts_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        rows.append(line)
    return rows


async def crawl_accounts(
    db_path: Path,
    accounts: Iterable[str],
    max_posts_per_account: int | None = None,
    headless: bool = True,
) -> CrawlSummary:
    from playwright.async_api import async_playwright

    collected = 0
    saved = 0
    failures = 0
    seen = 0
    now = datetime.now(timezone.utc).isoformat()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context()

        for account in accounts:
            handle, url = normalize_account(account)
            collected += 1
            try:
                page = await context.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
                await page.wait_for_timeout(2000)

                post_links = await _collect_post_links(page, max_posts_per_account)
                seen += len(post_links)

                for post_url in post_links:
                    try:
                        record = await _crawl_post_page(page, post_url, handle)
                        if record is None:
                            continue
                        with tx(db_path) as conn:
                            conn.execute(
                                """
                                INSERT INTO crawl_posts
                                (post_id, post_url, account_handle, posted_at, caption, views, likes, comments, shares, collected_at, source, confidence)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                ON CONFLICT(post_id) DO UPDATE SET
                                  post_url=excluded.post_url,
                                  account_handle=excluded.account_handle,
                                  posted_at=excluded.posted_at,
                                  caption=excluded.caption,
                                  views=excluded.views,
                                  likes=excluded.likes,
                                  comments=excluded.comments,
                                  shares=excluded.shares,
                                  collected_at=excluded.collected_at,
                                  source=excluded.source,
                                  confidence=excluded.confidence
                                """,
                                (
                                    record["post_id"],
                                    record["post_url"],
                                    record["account_handle"],
                                    record["posted_at"],
                                    record["caption"],
                                    record["views"],
                                    record["likes"],
                                    record["comments"],
                                    record["shares"],
                                    now,
                                    "playwright_public",
                                    record["confidence"],
                                ),
                            )
                        saved += 1
                    except Exception as exc:  # noqa: BLE001
                        failures += 1
                        with tx(db_path) as conn:
                            conn.execute(
                                "INSERT INTO crawl_failures (account_handle, post_url, reason, collected_at) VALUES (?, ?, ?, ?)",
                                (handle, post_url, str(exc), now),
                            )
                await page.close()
            except Exception as exc:  # noqa: BLE001
                failures += 1
                with tx(db_path) as conn:
                    conn.execute(
                        "INSERT INTO crawl_failures (account_handle, post_url, reason, collected_at) VALUES (?, ?, ?, ?)",
                        (handle, url, str(exc), now),
                    )

        await context.close()
        await browser.close()

    return CrawlSummary(accounts=collected, posts_seen=seen, posts_saved=saved, failures=failures)


async def _collect_post_links(page, max_posts_per_account: int | None) -> list[str]:
    links: list[str] = []
    seen = set()

    for _ in range(8):
        hrefs = await page.eval_on_selector_all(
            "a[href*='/video/']",
            "els => els.map(e => e.href).filter(Boolean)",
        )
        for href in hrefs:
            match = POST_URL_RE.search(href)
            if not match:
                continue
            url = match.group(0)
            if url in seen:
                continue
            seen.add(url)
            links.append(url)
        if max_posts_per_account and len(links) >= max_posts_per_account:
            return links[:max_posts_per_account]
        await page.mouse.wheel(0, 5000)
        await page.wait_for_timeout(1200)

    return links[:max_posts_per_account] if max_posts_per_account else links


async def _crawl_post_page(page, post_url: str, account_handle: str) -> dict | None:
    m = POST_URL_RE.search(post_url)
    if not m:
        return None
    post_id = m.group("id")

    await page.goto(post_url, wait_until="domcontentloaded", timeout=60_000)
    await page.wait_for_timeout(1500)

    caption = await _extract_caption(page)
    metrics = await _extract_metrics(page)

    return {
        "post_id": post_id,
        "post_url": post_url,
        "account_handle": account_handle,
        "posted_at": None,
        "caption": caption,
        "views": metrics["views"],
        "likes": metrics["likes"],
        "comments": metrics["comments"],
        "shares": metrics["shares"],
        "confidence": metrics["confidence"],
    }


async def _extract_caption(page) -> str | None:
    selectors = [
        'h1[data-e2e="browse-video-desc"]',
        'div[data-e2e="browse-video-desc"]',
        'meta[property="og:description"]',
    ]
    for sel in selectors:
        loc = page.locator(sel).first
        try:
            if await loc.count() == 0:
                continue
            if sel.startswith("meta"):
                value = await loc.get_attribute("content")
            else:
                value = await loc.inner_text()
            if value:
                return " ".join(value.split())[:1000]
        except Exception:
            continue
    return None


async def _extract_metrics(page) -> dict:
    body = await page.content()
    # Best effort: parse tokens around common metric labels.
    views = _extract_number(body, ["playCount", "viewCount", "views"])
    likes = _extract_number(body, ["diggCount", "likeCount", "likes"])
    comments = _extract_number(body, ["commentCount", "comments"])
    shares = _extract_number(body, ["shareCount", "shares"])

    confidence = 0.55
    if any(v > 0 for v in [views, likes, comments, shares]):
        confidence = 0.8
    if views > 0 and likes > 0:
        confidence = 0.9

    return {
        "views": views,
        "likes": likes,
        "comments": comments,
        "shares": shares,
        "confidence": confidence,
    }


def _extract_number(text: str, keys: list[str]) -> int:
    for key in keys:
        patterns = [
            rf'"{re.escape(key)}"\s*:\s*"?([0-9.,KMB]+)"?',
            rf"{re.escape(key)}\s*[:=]\s*([0-9.,KMB]+)",
        ]
        for pat in patterns:
            m = re.search(pat, text, re.I)
            if m:
                return parse_count(m.group(1))
    return 0


def run_crawl(db_path: Path, accounts: list[str], max_posts_per_account: int | None, headless: bool) -> CrawlSummary:
    return asyncio.run(crawl_accounts(db_path, accounts, max_posts_per_account, headless=headless))
