"""CSV export helpers for tiktok-uploader CLI batch ingestion."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from config import HOOKS_FILE, OUTPUT_DIR

_FILENAME_RE = re.compile(r"^(?P<feature>.+?)_(?P<num>\d{3,})$")


@dataclass
class CsvExportOptions:
    account_id: str
    mode: str = "draft"
    platform: str = "tiktok"
    hashtags: str = ""
    root_dir: Path = OUTPUT_DIR
    absolute_paths: bool = False


def _load_feature_hooks() -> Dict[str, List[str]]:
    with open(HOOKS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    feature_hooks: Dict[str, List[str]] = {}
    features = data.get("features", {})
    for category in features.values():
        if not isinstance(category, dict):
            continue
        for feature_id, payload in category.items():
            hooks = payload.get("hooks", []) if isinstance(payload, dict) else []
            if isinstance(hooks, list):
                feature_hooks[feature_id] = [str(h).strip() for h in hooks if str(h).strip()]

    return feature_hooks


def _infer_feature_and_index(video_path: Path) -> tuple[str, int]:
    stem = video_path.stem
    match = _FILENAME_RE.match(stem)
    if not match:
        return stem, 0

    feature = match.group("feature")
    idx = max(0, int(match.group("num")) - 1)
    return feature, idx


def _derive_caption(video_path: Path, hooks_map: Dict[str, List[str]], hashtags: str) -> str:
    feature_id, hook_idx = _infer_feature_and_index(video_path)
    hooks = hooks_map.get(feature_id, [])

    if hooks:
        hook = hooks[hook_idx] if hook_idx < len(hooks) else hooks[0]
    else:
        hook = feature_id.replace("_", " ").strip().title()

    hashtag_block = hashtags.strip()
    if hashtag_block:
        return f"{hook} {hashtag_block}".strip()
    return hook


def export_uploader_csv(
    video_paths: Iterable[Path],
    output_csv: Path,
    options: CsvExportOptions,
) -> int:
    """Write uploader-compatible CSV for a list of generated videos.

    Returns number of rows written.
    """
    hooks_map = _load_feature_hooks()
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    rows_written = 0
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

        for path in video_paths:
            resolved = path.resolve()
            if not resolved.exists() or resolved.suffix.lower() not in {".mp4", ".mov", ".webm"}:
                continue

            video_value = str(resolved)
            if not options.absolute_paths:
                video_value = str(resolved.relative_to(options.root_dir.resolve()))

            writer.writerow(
                {
                    "file_type": "video",
                    "account_id": options.account_id,
                    "mode": options.mode,
                    "caption": _derive_caption(resolved, hooks_map, options.hashtags),
                    "video_path": video_value,
                    "image_paths": "",
                    "platform": options.platform,
                    "client_ref": resolved.stem,
                }
            )
            rows_written += 1

    return rows_written


def discover_output_videos(root_dir: Path) -> List[Path]:
    """Discover uploadable videos from output directory."""
    return sorted(
        [
            p
            for p in root_dir.glob("*.mp4")
            if p.is_file()
        ],
        key=lambda p: p.name,
    )
