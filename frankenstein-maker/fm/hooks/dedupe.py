"""Deduplication helpers using URL + perceptual hash."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from PIL import Image


def hash_url(url: str) -> str:
    return hashlib.sha1(url.strip().encode("utf-8")).hexdigest()


def dhash_image(path: Path, size: int = 8) -> int | None:
    if not path or not path.exists():
        return None
    try:
        img = Image.open(path).convert("L").resize((size + 1, size), Image.Resampling.LANCZOS)
    except Exception:
        return None
    pixels = list(img.getdata())
    width = size + 1
    bits = 0
    for row in range(size):
        for col in range(size):
            left = pixels[row * width + col]
            right = pixels[row * width + col + 1]
            bits = (bits << 1) | (1 if left > right else 0)
    return bits


def hamming_distance(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def dedupe_rows(rows: Iterable[Dict], phash_threshold: int = 8) -> Tuple[List[Dict], List[Dict]]:
    seen_urls = set()
    seen_hashes: List[int] = []
    unique: List[Dict] = []
    dropped: List[Dict] = []

    for row in rows:
        url = str(row.get("url") or "").strip()
        if not url:
            row["drop_reason"] = "missing_url"
            dropped.append(row)
            continue

        uhash = hash_url(url)
        if uhash in seen_urls:
            row["drop_reason"] = "duplicate_url"
            dropped.append(row)
            continue

        screenshot = Path(str(row.get("screenshot_path") or ""))
        pval = dhash_image(screenshot)
        too_close = False
        if pval is not None:
            for existing in seen_hashes:
                if hamming_distance(existing, pval) <= phash_threshold:
                    too_close = True
                    break

        if too_close:
            row["drop_reason"] = "near_duplicate_phash"
            dropped.append(row)
            continue

        seen_urls.add(uhash)
        if pval is not None:
            seen_hashes.append(pval)
        row["dedupe_hash"] = uhash
        unique.append(row)

    return unique, dropped
