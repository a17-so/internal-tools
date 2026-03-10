"""Audio helpers."""
from __future__ import annotations

from moviepy import AudioFileClip


def load_music_clip(path: str, duration: float, volume: float = 1.0) -> AudioFileClip:
    clip = AudioFileClip(path)
    clip = clip.subclipped(0, min(duration, clip.duration))
    return clip.with_volume_scaled(volume)
