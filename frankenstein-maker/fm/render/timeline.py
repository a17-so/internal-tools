"""Timeline planning and variation filters."""
from __future__ import annotations

import random
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Tuple

from moviepy import VideoFileClip

from fm.config import VIDEO_FPS, VIDEO_HEIGHT, VIDEO_WIDTH
from fm.utils.paths import ensure_parent


def pick_duration(start_sec: float, end_sec: float, min_sec: float = 3.0, max_sec: float = 5.0) -> Tuple[float, float]:
    span = max(0.1, end_sec - start_sec)
    if span <= min_sec:
        return start_sec, start_sec + min(span, max_sec)
    target = min(max_sec, max(min_sec, span))
    return start_sec, start_sec + target


def build_variation_profile(style_seed: int | None = None) -> Dict[str, float]:
    rng = random.Random(style_seed)
    return {
        "zoom": rng.uniform(1.01, 1.04),
        "speed": rng.uniform(0.985, 1.015),
        "brightness": rng.uniform(-0.02, 0.02),
        "contrast": rng.uniform(0.98, 1.03),
        "saturation": rng.uniform(0.98, 1.04),
        "hue": rng.uniform(-2.0, 2.0),
        "noise": rng.uniform(0.0, 0.02),
        "time_shift": rng.uniform(0.00, 0.06),
    }


def rewrite_clip_variation(source: Path, out_path: Path, profile: Dict[str, float]) -> Path:
    ensure_parent(out_path)

    vf_parts = [
        f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=cover",
        f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT}",
        f"eq=brightness={profile['brightness']:.4f}:contrast={profile['contrast']:.4f}:saturation={profile['saturation']:.4f}",
        f"hue=h={profile['hue']:.3f}",
    ]
    if profile["noise"] > 0.0:
        vf_parts.append(f"noise=alls={int(profile['noise'] * 100)}:allf=t")

    vf = ",".join(vf_parts)

    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{profile['time_shift']:.3f}",
        "-i",
        str(source),
        "-vf",
        vf,
        "-filter:a",
        f"atempo={profile['speed']:.5f}",
        "-map_metadata",
        "-1",
        "-r",
        str(VIDEO_FPS),
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        str(out_path),
    ]
    subprocess.run(cmd, check=True)
    return out_path


def concat_two_clips(first: Path, second: Path, out_path: Path) -> Path:
    ensure_parent(out_path)
    with tempfile.TemporaryDirectory(prefix="fm-concat-") as td:
        list_file = Path(td) / "inputs.txt"
        list_file.write_text(f"file '{first.as_posix()}'\nfile '{second.as_posix()}'\n", encoding="utf-8")
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-c",
            "copy",
            str(out_path),
        ]
        run = subprocess.run(cmd)
        if run.returncode != 0:
            fallback = [
                "ffmpeg",
                "-y",
                "-i",
                str(first),
                "-i",
                str(second),
                "-filter_complex",
                "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]",
                "-map",
                "[v]",
                "-map",
                "[a]",
                str(out_path),
            ]
            subprocess.run(fallback, check=True)
    return out_path


def load_duration(path: Path) -> float:
    with VideoFileClip(str(path)) as c:
        return c.duration
