"""Navigation helpers for capture sessions."""
from __future__ import annotations

from typing import List


def normalize_accounts(raw_accounts: List[str]) -> List[str]:
    out = []
    seen = set()
    for account in raw_accounts:
        value = account.strip().lstrip("@").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def account_reels_url(account: str) -> str:
    clean = account.strip().lstrip("@")
    return f"https://www.instagram.com/{clean}/reels/"
