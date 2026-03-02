from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .db import tx


def compute_scores(db_path: Path) -> dict[str, int]:
    with tx(db_path) as conn:
        rows = conn.execute(
            """
            SELECT p.post_id, p.account_handle, p.views, p.likes, p.comments, p.shares, m.format_name, m.status
            FROM crawl_posts p
            JOIN post_format_matches m ON m.post_id = p.post_id
            WHERE m.status IN ('auto_matched', 'approved') AND m.format_name IS NOT NULL
            """
        ).fetchall()

    per_account = defaultdict(list)
    for r in rows:
        per_account[r["account_handle"]].append(r)

    stats = {}
    for account, acc_rows in per_account.items():
        views = [x["views"] for x in acc_rows]
        mu = (sum(views) / len(views)) if views else 0
        sigma = _std(views, mu)
        stats[account] = (mu, sigma)

    by_format_account = defaultdict(list)
    for r in rows:
        key = (r["format_name"], r["account_handle"])
        by_format_account[key].append(r)

    updated = 0
    now = datetime.now(timezone.utc).isoformat()
    with tx(db_path) as conn:
        for (format_name, account), items in by_format_account.items():
            mu, sigma = stats[account]
            normalized_views_vals = []
            shares_k = []
            comments_k = []
            likes_k = []

            for item in items:
                views = max(1, item["views"])
                normalized_views = ((item["views"] - mu) / sigma) if sigma > 0 else 0.0
                normalized_views_vals.append(normalized_views)
                shares_k.append((item["shares"] / views) * 1000)
                comments_k.append((item["comments"] / views) * 1000)
                likes_k.append((item["likes"] / views) * 1000)

            avg_norm_views = _avg(normalized_views_vals)
            avg_shares_k = _avg(shares_k)
            avg_comments_k = _avg(comments_k)
            avg_likes_k = _avg(likes_k)

            proxy_score = (
                0.40 * _squash(avg_norm_views)
                + 0.30 * _squash(avg_shares_k / 20)
                + 0.15 * _squash(avg_comments_k / 20)
                + 0.15 * _squash(avg_likes_k / 100)
            )

            conn.execute(
                """
                INSERT INTO format_scores
                (format_name, account_handle, normalized_views, shares_per_1k, comments_per_1k, likes_per_1k, proxy_score, sample_size, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(format_name, account_handle) DO UPDATE SET
                  normalized_views=excluded.normalized_views,
                  shares_per_1k=excluded.shares_per_1k,
                  comments_per_1k=excluded.comments_per_1k,
                  likes_per_1k=excluded.likes_per_1k,
                  proxy_score=excluded.proxy_score,
                  sample_size=excluded.sample_size,
                  updated_at=excluded.updated_at
                """,
                (
                    format_name,
                    account,
                    avg_norm_views,
                    avg_shares_k,
                    avg_comments_k,
                    avg_likes_k,
                    proxy_score,
                    len(items),
                    now,
                ),
            )
            updated += 1

    return {"format_account_scores": updated, "posts_used": len(rows)}


def _avg(values: list[float]) -> float:
    return (sum(values) / len(values)) if values else 0.0


def _std(values: list[float], mean: float) -> float:
    if len(values) < 2:
        return 0.0
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return variance ** 0.5


def _squash(x: float) -> float:
    # Keep all features in a stable [0,1] range with diminishing returns.
    if x <= 0:
        return 0.0
    return x / (1 + x)
