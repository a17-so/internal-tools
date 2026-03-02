from pathlib import Path

from slideshow_machine.assets_normalizer import normalize_assets
from slideshow_machine.db import init_db, tx


def test_normalize_assets_groups_slides_and_flags_issues(tmp_path: Path):
    assets = tmp_path / "assets"
    fmt = assets / "formats" / "format a"
    fmt.mkdir(parents=True)
    (fmt / "1.1.png").write_bytes(b"x")
    (fmt / "1.2.png").write_bytes(b"x")
    (fmt / "Group 99.png").write_bytes(b"x")

    db = tmp_path / "db.sqlite"
    init_db(db)

    result = normalize_assets(db, assets, with_ocr=False)
    assert result.formats == 1
    assert result.examples == 1
    assert result.slides == 2
    assert result.issues == 1

    with tx(db) as conn:
        ex = conn.execute("SELECT slide_count FROM format_examples WHERE format_name='format a' AND example_id='1'").fetchone()
        assert ex["slide_count"] == 2
        issues = conn.execute("SELECT COUNT(*) c FROM normalization_issues").fetchone()["c"]
        assert issues == 1
