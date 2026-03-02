from pathlib import Path

from slideshow_machine.db import init_db, tx
from slideshow_machine.exporter import export_draft


def test_export_draft_writes_manifest(tmp_path: Path):
    db = tmp_path / "db.sqlite"
    init_db(db)
    with tx(db) as conn:
        conn.execute(
            "INSERT INTO drafts (draft_id, topic, objective, format_name, predicted_score, rationale_json, caption, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("d_test", "glow", "qualified_virality_proxy", "format alpha", 0.71, '["a"]', "caption", "review", "2026-03-01T00:00:00Z"),
        )
        conn.execute(
            "INSERT INTO draft_slides (draft_id, slide_index, role, text) VALUES (?, ?, ?, ?)",
            ("d_test", 1, "hook", "text"),
        )

    manifest = export_draft(db, "d_test", tmp_path / "out")
    assert manifest.exists()
    assert (manifest.parent / "uploader_row.csv").exists()
