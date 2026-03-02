"""Render execution and logging."""
from __future__ import annotations

import json
import logging
import random
import subprocess
from pathlib import Path
from typing import Dict, List

from moviepy import CompositeVideoClip, VideoFileClip

from fm.config import RENDER_LOG_PATH, VIDEO_HEIGHT, VIDEO_WIDTH
from fm.render.overlay import icon_overlay, top_bar_overlay
from fm.render.timeline import build_variation_profile, concat_two_clips, rewrite_clip_variation
from fm.utils.paths import ensure_parent
from fm.utils.time import now_iso

logger = logging.getLogger(__name__)


def _next_name(videos_dir: Path, style: str) -> str:
    existing = sorted(videos_dir.glob(f"{style}_*.mp4"))
    n = 1
    if existing:
        nums = []
        for p in existing:
            tail = p.stem.split("_")[-1]
            if tail.isdigit():
                nums.append(int(tail))
        if nums:
            n = max(nums) + 1
    return f"{style}_{n:03d}.mp4"


def _strip_metadata_inplace(path: Path) -> None:
    tmp = path.with_suffix(".clean.mp4")
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(path),
        "-map_metadata",
        "-1",
        "-c",
        "copy",
        str(tmp),
    ]
    subprocess.run(cmd, check=True)
    tmp.replace(path)


def render_one(
    style_name: str,
    hook_video: Path,
    second_half_video: Path,
    manifest: Dict,
    videos_dir: Path,
    dry_run: bool = False,
) -> Path:
    name = _next_name(videos_dir, style_name)
    out_path = videos_dir / name

    if dry_run:
        return out_path

    work_dir = videos_dir / ".tmp"
    work_dir.mkdir(parents=True, exist_ok=True)
    varied_hook = work_dir / f"{out_path.stem}.hook.mp4"
    combined = work_dir / f"{out_path.stem}.combined.mp4"

    profile = build_variation_profile(style_seed=random.randint(1, 1_000_000))
    rewrite_clip_variation(hook_video, varied_hook, profile)
    concat_two_clips(varied_hook, second_half_video, combined)

    top_cfg = manifest.get("overlays", {}).get("top_bar", {})
    cta = str(top_cfg.get("cta", "Download Everest"))
    hook_text = str(top_cfg.get("hook", "Still scrolling?"))

    icon_path = str(manifest.get("icon", {}).get("path", ""))

    with VideoFileClip(str(combined)) as base:
        overlays = [base]
        top = top_bar_overlay(VIDEO_WIDTH, VIDEO_HEIGHT, hook_text=hook_text, cta_text=cta)
        top = top.with_duration(base.duration).with_position((0, 0))
        overlays.append(top)

        if icon_path:
            icon_file = Path(icon_path)
            if icon_file.exists():
                icon = icon_overlay(str(icon_file), VIDEO_WIDTH, VIDEO_HEIGHT)
                icon = icon.with_duration(base.duration)
                overlays.append(icon)

        final = CompositeVideoClip(overlays, size=(VIDEO_WIDTH, VIDEO_HEIGHT))
        ensure_parent(out_path)
        final.write_videofile(
            str(out_path),
            codec="libx264",
            audio_codec="aac",
            fps=base.fps or 30,
            threads=4,
            preset="medium",
        )
        final.close()

    _strip_metadata_inplace(out_path)
    return out_path


def append_render_log(payload: Dict) -> None:
    ensure_parent(RENDER_LOG_PATH)
    with open(RENDER_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=True) + "\n")


def render_batch(
    style_name: str,
    hooks: List[Dict],
    manifest: Dict,
    count: int,
    videos_dir: Path,
    dry_run: bool = False,
) -> List[Path]:
    style_cfg = manifest["styles"][style_name]
    clip_pool = [Path(p) for p in style_cfg.get("clip_pools", [])]
    clip_pool = [p for p in clip_pool if p.exists()]

    if not clip_pool:
        raise ValueError(f"No valid clip_pools found for style {style_name}")

    chosen = hooks[:count]
    outputs: List[Path] = []
    for i, hook in enumerate(chosen, start=1):
        hook_path = Path(str(hook.get("hook_local_path") or ""))
        if not hook_path.exists():
            logger.warning("Skipping hook missing local path: %s", hook.get("url", ""))
            continue

        second_half = clip_pool[(i - 1) % len(clip_pool)]
        out = render_one(
            style_name=style_name,
            hook_video=hook_path,
            second_half_video=second_half,
            manifest=style_cfg,
            videos_dir=videos_dir,
            dry_run=dry_run,
        )
        outputs.append(out)

        append_render_log(
            {
                "timestamp": now_iso(),
                "video_path": str(out),
                "style": style_name,
                "hook_url": hook.get("url", ""),
                "hook_local_path": str(hook_path),
                "dry_run": dry_run,
            }
        )

    return outputs
