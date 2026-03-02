from __future__ import annotations

import json
import random
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .db import tx
from .types import DraftBundle, DraftSlide


def make_drafts(
    db_path: Path,
    topic: str,
    count: int,
    account_scope: list[str],
    objective: str = "qualified_virality_proxy",
    explore_ratio: float = 0.2,
    seed: int | None = 42,
) -> list[DraftBundle]:
    if count <= 0:
        raise ValueError("count must be > 0")

    rng = random.Random(seed)
    ranked_formats = _rank_formats(db_path, account_scope)
    if not ranked_formats:
        raise RuntimeError("No ranked formats available. Run score-formats first.")

    bundles: list[DraftBundle] = []
    now = datetime.now(timezone.utc).isoformat()

    with tx(db_path) as conn:
        for i in range(count):
            use_explore = rng.random() < explore_ratio and len(ranked_formats) > 2
            candidate_pool = ranked_formats[2:] if use_explore else ranked_formats[:3]
            format_name, predicted_score = rng.choice(candidate_pool)

            slide_structure = _resolve_slide_structure(conn, format_name)
            slides = _generate_slides(topic, slide_structure, rng)
            caption = _generate_caption(topic, format_name)
            rationale = [
                f"format={format_name}",
                f"mode={'explore' if use_explore else 'exploit'}",
                f"predicted_proxy_score={predicted_score:.3f}",
            ]

            draft_id = f"d_{uuid.uuid4().hex[:12]}"
            conn.execute(
                "INSERT INTO drafts (draft_id, topic, objective, format_name, predicted_score, rationale_json, caption, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, 'review', ?)",
                (
                    draft_id,
                    topic,
                    objective,
                    format_name,
                    predicted_score,
                    json.dumps(rationale, ensure_ascii=True),
                    caption,
                    now,
                ),
            )
            for slide in slides:
                conn.execute(
                    "INSERT INTO draft_slides (draft_id, slide_index, role, text) VALUES (?, ?, ?, ?)",
                    (draft_id, slide.index, slide.role, slide.text),
                )

            bundles.append(
                DraftBundle(
                    draft_id=draft_id,
                    format_name=format_name,
                    topic=topic,
                    caption=caption,
                    predicted_score=predicted_score,
                    rationale=rationale,
                    slides=slides,
                )
            )

    return bundles


def _rank_formats(db_path: Path, account_scope: list[str]) -> list[tuple[str, float]]:
    with tx(db_path) as conn:
        if account_scope:
            placeholders = ",".join(["?"] * len(account_scope))
            rows = conn.execute(
                f"SELECT format_name, proxy_score, sample_size FROM format_scores WHERE account_handle IN ({placeholders})",
                account_scope,
            ).fetchall()
        else:
            rows = conn.execute("SELECT format_name, proxy_score, sample_size FROM format_scores").fetchall()

    score_by_format: dict[str, list[tuple[float, int]]] = {}
    for r in rows:
        score_by_format.setdefault(r["format_name"], []).append((r["proxy_score"], r["sample_size"]))

    ranked = []
    for fmt, vals in score_by_format.items():
        weighted = sum(score * max(1, sample) for score, sample in vals)
        denom = sum(max(1, sample) for _, sample in vals)
        ranked.append((fmt, weighted / denom))

    ranked.sort(key=lambda x: x[1], reverse=True)
    return ranked


def _resolve_slide_structure(conn, format_name: str) -> list[str]:
    rows = conn.execute(
        "SELECT role FROM format_slides WHERE format_name = ? ORDER BY example_id, slide_index",
        (format_name,),
    ).fetchall()
    roles = [r["role"] for r in rows if r["role"]]
    if not roles:
        return ["hook", "setup", "proof", "reveal", "cta"]

    # Use first 6 roles as a canonical v1 structure.
    canonical = roles[:8]
    deduped: list[str] = []
    for role in canonical:
        if not deduped or deduped[-1] != role:
            deduped.append(role)
    canonical = deduped
    if not canonical or canonical[0] != "hook":
        canonical.insert(0, "hook")
    if canonical[-1] != "cta":
        canonical.append("cta")
    return canonical[:8]


def _topic_keywords(topic: str) -> list[str]:
    words = re.findall(r"[a-zA-Z0-9]+", topic.lower())
    unique = []
    for w in words:
        if w in unique:
            continue
        unique.append(w)
    return unique[:5] if unique else ["makeup", "glow"]


def _generate_slides(topic: str, roles: list[str], rng: random.Random) -> list[DraftSlide]:
    kws = _topic_keywords(topic)
    hook_variants = [
        f"Stop scrolling: {topic} in {rng.randint(3, 7)} steps",
        f"Most people mess this up: {topic}",
        f"The {kws[0]} trick that changes everything",
    ]

    texts_by_role = {
        "hook": lambda i: rng.choice(hook_variants),
        "setup": lambda i: f"If you want better {kws[0]} results, start here.",
        "proof": lambda i: f"Do this first: focus on {kws[min(i % len(kws), len(kws)-1)]}.",
        "reveal": lambda i: f"Final transformation: combine {kws[0]} + {kws[-1]}.",
        "cta": lambda i: f"Comment 'guide' and I will post part 2 on {topic}.",
        "list_item": lambda i: f"Step {i}: optimize {kws[min(i % len(kws), len(kws)-1)]}.",
        "comparison": lambda i: f"Before vs after: {kws[0]} with and without this method.",
    }

    slides = []
    for idx, role in enumerate(roles, start=1):
        fn = texts_by_role.get(role, texts_by_role["proof"])
        slides.append(DraftSlide(index=idx, role=role, text=fn(idx)))
    return slides


def _generate_caption(topic: str, format_name: str) -> str:
    return f"{topic} | format: {format_name} #pretti #makeup #tiktoktips"
