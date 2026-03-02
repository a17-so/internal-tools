from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .db import tx

WORD_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str | None) -> set[str]:
    if not text:
        return set()
    return set(WORD_RE.findall(text.lower()))


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def build_format_fingerprints(db_path: Path) -> dict[str, dict]:
    with tx(db_path) as conn:
        rows = conn.execute(
            "SELECT format_name, example_id, slide_count FROM format_examples ORDER BY format_name, example_id"
        ).fetchall()
        slide_rows = conn.execute(
            "SELECT format_name, example_id, ocr_text, role FROM format_slides"
        ).fetchall()

    examples = defaultdict(list)
    for r in rows:
        examples[r["format_name"]].append((r["example_id"], r["slide_count"]))

    text_by_format = defaultdict(list)
    roles_by_format = defaultdict(list)
    for r in slide_rows:
        if r["ocr_text"]:
            text_by_format[r["format_name"]].append(r["ocr_text"])
        roles_by_format[r["format_name"]].append(r["role"])

    fingerprints = {}
    for fmt, items in examples.items():
        avg_slide_count = sum(x[1] for x in items) / len(items)
        corpus_text = " ".join(text_by_format.get(fmt, []))
        token_set = tokenize(fmt.replace("_", " ") + " " + corpus_text)
        role_counts = defaultdict(int)
        for role in roles_by_format.get(fmt, []):
            role_counts[role] += 1
        fingerprints[fmt] = {
            "tokens": token_set,
            "avg_slide_count": avg_slide_count,
            "example_ids": [x[0] for x in items],
            "roles": dict(role_counts),
        }
    return fingerprints


def match_posts(db_path: Path, threshold: float = 0.4) -> dict[str, int]:
    fps = build_format_fingerprints(db_path)
    if not fps:
        raise RuntimeError("No normalized format data found. Run ingest-assets first.")

    with tx(db_path) as conn:
        posts = conn.execute(
            "SELECT post_id, caption, views, likes, comments, shares FROM crawl_posts"
        ).fetchall()

    status_counts = defaultdict(int)
    now = datetime.now(timezone.utc).isoformat()

    with tx(db_path) as conn:
        for post in posts:
            caption_tokens = tokenize(post["caption"]) or set()
            engagement_density = _engagement_density(post["views"], post["likes"], post["comments"], post["shares"])

            best_format = None
            best_conf = -1.0
            best_reasons = []

            for format_name, fp in fps.items():
                text_sim = jaccard(caption_tokens, fp["tokens"])
                structure_prior = _structure_prior(engagement_density, fp["avg_slide_count"])
                confidence = max(0.0, min(1.0, (0.75 * text_sim) + (0.25 * structure_prior)))
                if confidence > best_conf:
                    best_conf = confidence
                    best_format = format_name
                    best_reasons = [
                        f"caption_token_similarity={text_sim:.3f}",
                        f"structure_prior={structure_prior:.3f}",
                    ]

            if best_conf < threshold:
                status = "needs_review"
                format_name = None
                example_id = None
            else:
                status = "auto_matched"
                format_name = best_format
                example_id = fps[best_format]["example_ids"][0] if best_format else None

            conn.execute(
                """
                INSERT INTO post_format_matches (post_id, format_name, example_id, confidence, status, reasons_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(post_id) DO UPDATE SET
                  format_name=excluded.format_name,
                  example_id=excluded.example_id,
                  confidence=excluded.confidence,
                  status=excluded.status,
                  reasons_json=excluded.reasons_json,
                  updated_at=excluded.updated_at
                """,
                (
                    post["post_id"],
                    format_name,
                    example_id,
                    best_conf,
                    status,
                    json.dumps(best_reasons, ensure_ascii=True),
                    now,
                ),
            )
            status_counts[status] += 1

    return dict(status_counts)


def _engagement_density(views: int, likes: int, comments: int, shares: int) -> float:
    if views <= 0:
        return 0.0
    return (likes + comments + (2 * shares)) / views


def _structure_prior(engagement_density: float, avg_slide_count: float) -> float:
    # Prefer concise formats for high-density engagement.
    target = 5.0 if engagement_density > 0.08 else 7.0
    diff = abs(avg_slide_count - target)
    return math.exp(-(diff**2) / 9.0)
