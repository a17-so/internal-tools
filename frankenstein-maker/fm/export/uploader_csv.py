"""Uploader CSV export utilities."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from fm.utils.paths import ensure_parent


def discover_videos(videos_dir: Path) -> list[Path]:
    return sorted([p for p in videos_dir.glob("*.mp4") if p.is_file()], key=lambda p: p.name)


def caption_from_filename(path: Path, hashtags: str = "") -> str:
    stem = path.stem.replace("_", " ").strip()
    caption = f"{stem}"
    if hashtags.strip():
        caption = f"{caption} {hashtags.strip()}"
    return caption.strip()


def export_csv(
    videos: Iterable[Path],
    output_csv: Path,
    account_id: str,
    hashtags: str = "",
    platform: str = "tiktok",
    mode: str = "draft",
    root_dir: Path | None = None,
    absolute_paths: bool = False,
) -> int:
    ensure_parent(output_csv)
    root = root_dir.resolve() if root_dir else None

    count = 0
    with open(output_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "file_type",
                "account_id",
                "mode",
                "caption",
                "video_path",
                "image_paths",
                "platform",
                "client_ref",
            ],
        )
        writer.writeheader()

        for video in videos:
            resolved = video.resolve()
            if not resolved.exists():
                continue

            vpath = str(resolved)
            if not absolute_paths and root:
                vpath = str(resolved.relative_to(root))

            writer.writerow(
                {
                    "file_type": "video",
                    "account_id": account_id,
                    "mode": mode,
                    "caption": caption_from_filename(resolved, hashtags=hashtags),
                    "video_path": vpath,
                    "image_paths": "",
                    "platform": platform,
                    "client_ref": resolved.stem,
                }
            )
            count += 1
    return count
