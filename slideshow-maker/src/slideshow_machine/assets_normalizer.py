from __future__ import annotations

import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .db import tx


FILENAME_RE = re.compile(r"^(?P<example>\d+)\.(?P<slide>\d+)\.png$", re.IGNORECASE)


@dataclass(slots=True)
class NormalizationResult:
    formats: int
    examples: int
    slides: int
    issues: int


def _extract_ocr_text(path: Path) -> str | None:
    """Best-effort OCR: use local tesseract if available; else return None."""
    try:
        proc = subprocess.run(
            ["tesseract", str(path), "stdout", "--dpi", "300"],
            capture_output=True,
            text=True,
            check=False,
            timeout=12,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    text = " ".join(proc.stdout.split())
    return text[:1200] if text else None


def normalize_assets(db_path: Path, assets_root: Path, with_ocr: bool = False) -> NormalizationResult:
    formats_dir = assets_root / "formats"
    if not formats_dir.exists():
        raise FileNotFoundError(f"Missing formats directory: {formats_dir}")

    groups: dict[tuple[str, str], dict[int, Path]] = defaultdict(dict)
    issues = []
    total_slides = 0

    for fmt_dir in sorted([d for d in formats_dir.iterdir() if d.is_dir()]):
        for file in sorted(fmt_dir.glob("*.png")):
            match = FILENAME_RE.match(file.name)
            if not match:
                issues.append((fmt_dir.name, str(file), "non_standard_filename", file.name))
                continue
            example_id = match.group("example")
            slide_index = int(match.group("slide"))
            groups[(fmt_dir.name, example_id)][slide_index] = file
            total_slides += 1

    now = datetime.now(timezone.utc).isoformat()
    with tx(db_path) as conn:
        conn.execute("DELETE FROM format_slides")
        conn.execute("DELETE FROM format_examples")
        conn.execute("DELETE FROM normalization_issues")

        for format_name, file_path, issue_type, detail in issues:
            conn.execute(
                "INSERT INTO normalization_issues (format_name, file_path, issue_type, detail, created_at) VALUES (?, ?, ?, ?, ?)",
                (format_name, file_path, issue_type, detail, now),
            )

        for (format_name, example_id), slides in groups.items():
            ordered = sorted(slides.items())
            conn.execute(
                "INSERT INTO format_examples (format_name, example_id, slide_count) VALUES (?, ?, ?)",
                (format_name, example_id, len(ordered)),
            )
            for slide_index, file in ordered:
                ocr_text = _extract_ocr_text(file) if with_ocr else None
                role = infer_slide_role(slide_index, len(ordered))
                conn.execute(
                    "INSERT INTO format_slides (format_name, example_id, slide_index, file_path, ocr_text, role) VALUES (?, ?, ?, ?, ?, ?)",
                    (format_name, example_id, slide_index, str(file), ocr_text, role),
                )

    return NormalizationResult(
        formats=len({k[0] for k in groups.keys()}),
        examples=len(groups),
        slides=total_slides,
        issues=len(issues),
    )


def infer_slide_role(slide_index: int, slide_count: int) -> str:
    if slide_index == 1:
        return "hook"
    if slide_index == slide_count:
        return "cta"
    if slide_index == 2:
        return "setup"
    if slide_index >= slide_count - 1:
        return "reveal"
    return "proof"
