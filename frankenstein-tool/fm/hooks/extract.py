"""Hook extraction helpers."""
from __future__ import annotations

import subprocess
from pathlib import Path

from fm.config import VIDEO_FPS, VIDEO_HEIGHT, VIDEO_WIDTH
from fm.utils.paths import ensure_parent


def extract_hook_segment(
    source_video: Path,
    output_video: Path,
    start_sec: float,
    end_sec: float,
) -> Path:
    duration = max(0.1, end_sec - start_sec)
    ensure_parent(output_video)

    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{start_sec:.3f}",
        "-i",
        str(source_video),
        "-t",
        f"{duration:.3f}",
        "-vf",
        f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=cover,crop={VIDEO_WIDTH}:{VIDEO_HEIGHT}",
        "-r",
        str(VIDEO_FPS),
        "-c:v",
        "libx264",
        "-an",
        str(output_video),
    ]
    subprocess.run(cmd, check=True)
    return output_video
