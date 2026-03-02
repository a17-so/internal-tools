from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .db import tx


def export_draft(db_path: Path, draft_id: str, output_root: Path) -> Path:
    output_dir = output_root / draft_id
    output_dir.mkdir(parents=True, exist_ok=True)

    with tx(db_path) as conn:
        draft = conn.execute(
            "SELECT draft_id, topic, objective, format_name, predicted_score, rationale_json, caption, status, created_at FROM drafts WHERE draft_id = ?",
            (draft_id,),
        ).fetchone()
        if not draft:
            raise ValueError(f"Draft not found: {draft_id}")

        slides = conn.execute(
            "SELECT slide_index, role, text FROM draft_slides WHERE draft_id = ? ORDER BY slide_index",
            (draft_id,),
        ).fetchall()

    manifest = {
        "draft_id": draft["draft_id"],
        "topic": draft["topic"],
        "objective": draft["objective"],
        "format_name": draft["format_name"],
        "predicted_score": draft["predicted_score"],
        "rationale": json.loads(draft["rationale_json"]),
        "caption": draft["caption"],
        "status": draft["status"],
        "slides": [
            {"index": s["slide_index"], "role": s["role"], "text": s["text"]}
            for s in slides
        ],
    }

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=True))

    # Create uploader handoff CSV row format.
    csv_path = output_dir / "uploader_row.csv"
    csv_path.write_text(
        "file_type,account_id,mode,caption,video_path,image_paths,platform,client_ref\n"
        f"slideshow,,draft,\"{_escape_csv(draft['caption'])}\",,\"\",tiktok,{draft_id}\n"
    )

    now = datetime.now(timezone.utc).isoformat()
    with tx(db_path) as conn:
        conn.execute(
            "INSERT INTO exports (draft_id, output_dir, manifest_path, created_at) VALUES (?, ?, ?, ?)",
            (draft_id, str(output_dir), str(manifest_path), now),
        )

    return manifest_path


def _escape_csv(value: str) -> str:
    return value.replace('"', '""')
