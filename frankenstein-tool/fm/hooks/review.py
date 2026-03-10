"""Terminal review workflow."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from fm.capture.store import read_jsonl, write_jsonl
from fm.utils.time import now_iso


def run_review(candidates_path: Path, approved_path: Path, reviewer: str = "local_user") -> tuple[int, int]:
    candidates = read_jsonl(candidates_path)
    approved_existing = read_jsonl(approved_path)
    approved_urls = {str(r.get("url") or "") for r in approved_existing}
    approved = list(approved_existing)

    reviewed = 0
    accepted = 0

    for row in candidates:
        if not row.get("eligible", False):
            continue
        url = str(row.get("url") or "")
        if not url or url in approved_urls:
            continue

        print("\n--- Candidate ---")
        print(f"URL: {url}")
        print(f"Seed: {row.get('seed_account', '')}")
        print(f"Captured: {row.get('captured_at', '')}")
        print(f"Screenshot: {row.get('screenshot_path', '')}")
        ans = input("Approve? [y]es / [n]o / [q]uit: ").strip().lower()
        if ans == "q":
            break

        reviewed += 1
        if ans == "y":
            approved_row: Dict = dict(row)
            approved_row["approved_at"] = now_iso()
            approved_row["approved_by"] = reviewer
            approved_row.setdefault("hook_local_path", "")
            approved_row.setdefault("hook_start_sec", 0.0)
            approved_row.setdefault("hook_end_sec", 5.0)
            approved.append(approved_row)
            approved_urls.add(url)
            accepted += 1

    write_jsonl(approved_path, approved)
    return reviewed, accepted
