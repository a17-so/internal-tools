"""Cooldown helpers for source reuse windows."""
from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import Dict, Iterable, List

from fm.utils.paths import ensure_parent
from fm.utils.time import now_iso, parse_iso


def load_cooldown_store(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_cooldown_store(path: Path, data: Dict[str, str]) -> None:
    ensure_parent(path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def apply_cooldown(rows: Iterable[Dict], store: Dict[str, str], cooldown_days: int) -> List[Dict]:
    now = parse_iso(now_iso())
    out: List[Dict] = []

    for row in rows:
        key = str(row.get("dedupe_hash") or row.get("url") or "").strip()
        if not key:
            row["eligible"] = False
            row["cooldown_until"] = ""
            row["drop_reason"] = row.get("drop_reason") or "missing_cooldown_key"
            out.append(row)
            continue

        existing = store.get(key)
        if existing:
            until = parse_iso(existing)
            if until > now:
                row["eligible"] = False
                row["cooldown_until"] = existing
                row["drop_reason"] = row.get("drop_reason") or "cooldown_active"
                out.append(row)
                continue

        until = now + timedelta(days=cooldown_days)
        until_iso = until.isoformat()
        row["eligible"] = True
        row["cooldown_until"] = until_iso
        store[key] = until_iso
        out.append(row)

    return out
