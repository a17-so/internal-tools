from pathlib import Path

from slideshow_machine.assets_normalizer import normalize_assets
from slideshow_machine.db import init_db, tx
from slideshow_machine.drafts import make_drafts
from slideshow_machine.matcher import match_posts
from slideshow_machine.scoring import compute_scores


def seed_assets(assets: Path):
    f1 = assets / "formats" / "format alpha"
    f1.mkdir(parents=True)
    (f1 / "1.1.png").write_bytes(b"x")
    (f1 / "1.2.png").write_bytes(b"x")
    (f1 / "1.3.png").write_bytes(b"x")

    f2 = assets / "formats" / "format beta"
    f2.mkdir(parents=True)
    (f2 / "1.1.png").write_bytes(b"x")
    (f2 / "1.2.png").write_bytes(b"x")
    (f2 / "1.3.png").write_bytes(b"x")
    (f2 / "1.4.png").write_bytes(b"x")


def seed_posts(db: Path):
    with tx(db) as conn:
        conn.execute(
            """
            INSERT INTO crawl_posts
            (post_id, post_url, account_handle, posted_at, caption, views, likes, comments, shares, collected_at, source, confidence)
            VALUES
            ('p1','https://www.tiktok.com/@a/video/1','a',NULL,'alpha makeup glow',10000,1200,150,120,'2026-03-01T00:00:00Z','playwright_public',0.8),
            ('p2','https://www.tiktok.com/@a/video/2','a',NULL,'beta routine',8000,500,60,40,'2026-03-01T00:00:00Z','playwright_public',0.8),
            ('p3','https://www.tiktok.com/@b/video/3','b',NULL,'alpha fast tips',25000,3500,400,500,'2026-03-01T00:00:00Z','playwright_public',0.9)
            """
        )


def test_end_to_end_match_score_and_draft(tmp_path: Path):
    db = tmp_path / "db.sqlite"
    assets = tmp_path / "assets"
    init_db(db)
    seed_assets(assets)

    normalize_assets(db, assets, with_ocr=False)
    seed_posts(db)

    result = match_posts(db, threshold=0.0)
    assert result["auto_matched"] == 3

    score_result = compute_scores(db)
    assert score_result["posts_used"] == 3
    assert score_result["format_account_scores"] >= 1

    drafts = make_drafts(db, topic="soft glam", count=2, account_scope=["a", "b"], explore_ratio=0.0)
    assert len(drafts) == 2
    for d in drafts:
        assert d.caption
        assert d.slides
        assert d.predicted_score >= 0
