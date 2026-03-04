"""Manual hook URL ingestion for phone-sourced research."""
from __future__ import annotations

import csv
import uuid
from pathlib import Path
from typing import List

from fm.capture.store import append_jsonl, read_jsonl
from fm.utils.time import now_iso


def _extract_urls_from_text(lines: List[str]) -> List[str]:
    urls: List[str] = []
    for raw in lines:
        value = raw.strip()
        if not value or value.startswith("#"):
            continue
        if value.startswith("http://") or value.startswith("https://"):
            urls.append(value)
    return urls


def parse_urls_file(path: Path) -> List[str]:
    if not path.exists():
        return []

    if path.suffix.lower() == ".csv":
        urls: List[str] = []
        with open(path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                for key in ("url", "reel_url", "link"):
                    value = str(row.get(key) or "").strip()
                    if value.startswith("http://") or value.startswith("https://"):
                        urls.append(value)
                        break
        return urls

    lines = path.read_text(encoding="utf-8").splitlines()
    return _extract_urls_from_text(lines)


def import_urls_to_captured(output_path: Path, urls: List[str], seed_account: str = "") -> int:
    existing = read_jsonl(output_path)
    existing_urls = {str(r.get("url") or "").strip() for r in existing}
    added = 0

    for url in urls:
        clean = url.strip()
        if not clean or clean in existing_urls:
            continue
        row = {
            "capture_id": str(uuid.uuid4()),
            "captured_at": now_iso(),
            "platform": "instagram",
            "url": clean,
            "seed_account": seed_account,
            "notes": "manual_phone_research",
            "raw_metrics_text": "",
            "screenshot_path": "",
            "page_title": "",
        }
        append_jsonl(output_path, row)
        existing_urls.add(clean)
        added += 1

    return added
