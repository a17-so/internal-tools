"""Overlay rendering helpers."""
from __future__ import annotations

from pathlib import Path
from typing import Tuple

import numpy as np
from moviepy import ImageClip
from PIL import Image, ImageDraw, ImageFont


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/SFNS.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ]
    for c in candidates:
        p = Path(c)
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def top_bar_overlay(
    width: int,
    height: int,
    hook_text: str,
    cta_text: str,
    bar_height: int = 220,
) -> ImageClip:
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    draw.rectangle((0, 0, width, bar_height), fill=(255, 255, 255, 245))

    font_main = _load_font(56)
    font_cta = _load_font(44)

    hook_text = hook_text.strip() or "stop doomscrolling"
    cta_text = cta_text.strip() or "download everest"

    draw.text((width // 2, 70), hook_text, fill=(0, 0, 0, 255), font=font_main, anchor="mm")
    draw.text((width // 2, 150), cta_text, fill=(20, 20, 20, 255), font=font_cta, anchor="mm")

    arr = np.array(img)
    rgb = ImageClip(arr[:, :, :3])
    mask = ImageClip(arr[:, :, 3] / 255.0, is_mask=True)
    return rgb.with_mask(mask)


def icon_overlay(icon_path: str, width: int, height: int, size: int = 130) -> ImageClip:
    icon = Image.open(icon_path).convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
    arr = np.array(icon)
    rgb = ImageClip(arr[:, :, :3])
    mask = ImageClip(arr[:, :, 3] / 255.0, is_mask=True)
    return rgb.with_mask(mask).with_position((width // 2 - size // 2, height // 2 - size // 2))
