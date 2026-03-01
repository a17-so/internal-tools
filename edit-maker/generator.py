"""
Core video generation logic for the Pretti Edit Maker.

Handles image slideshow creation, text overlays, app demo compositing,
and final video rendering with audio.
"""
import json
import logging
import random
import textwrap
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
from moviepy import (
    AudioFileClip,
    CompositeVideoClip,
    ImageClip,
    TextClip,
    VideoFileClip,
    concatenate_videoclips,
)
from moviepy.video.fx import FadeIn, FadeOut, Resize
from PIL import Image, ImageDraw, ImageFont

from config import (
    CROP_VARIATION,
    DEFAULT_DEMO,
    DEFAULT_MUSIC,
    DEFAULT_UI_IMAGE,
    FADE_DURATION,
    FONT_COLOR,
    FONT_PATH,
    FONT_SIZE,
    FPS,
    HOOKS_FILE,
    IMAGE_DURATION,
    IMAGES_DIR,
    MAX_IMAGES,
    MIN_IMAGES,
    MUSIC_START_TIME,
    OUTPUT_DIR,
    TEMP_DIR,
    STROKE_COLOR,
    STROKE_WIDTH,
    VIDEO_HEIGHT,
    VIDEO_WIDTH,
)

__all__ = [
    "generate_video",
    "get_feature_info",
    "list_all_features",
    "load_hooks",
]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hooks database helpers
# ---------------------------------------------------------------------------


def load_hooks() -> dict:
    """Load the hooks database from disk."""
    with open(HOOKS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def get_feature_info(category: str, feature_id: str) -> dict:
    """Return the config dict for a single feature, or empty dict if missing."""
    hooks_db = load_hooks()
    return hooks_db.get("features", {}).get(category, {}).get(feature_id, {})


def list_all_features() -> List[Tuple[str, str, str]]:
    """Return ``[(category, feature_id, sample_hook), ...]`` for every feature."""
    hooks_db = load_hooks()
    result: List[Tuple[str, str, str]] = []
    for category, features in hooks_db.get("features", {}).items():
        for feature_id, info in features.items():
            result.append((category, feature_id, info.get("hooks", [""])[0]))
    return result


def audit_feature_assets() -> Tuple[List[str], List[str]]:
    """Return ``(errors, warnings)`` for hooks/image asset integrity."""
    hooks_db = load_hooks()
    errors: List[str] = []
    warnings: List[str] = []
    valid_exts = {".jpg", ".jpeg", ".png", ".webp"}

    for category, features in hooks_db.get("features", {}).items():
        for feature_id, info in features.items():
            folder = info.get("folder")
            hooks = info.get("hooks")
            label = f"{category}/{feature_id}"

            if not folder:
                errors.append(f"{label}: missing folder")
                continue

            folder_path = IMAGES_DIR / folder
            if not folder_path.exists():
                errors.append(f"{label}: missing folder path ({folder_path})")
            else:
                images = [
                    p for p in folder_path.iterdir()
                    if p.is_file() and p.suffix.lower() in valid_exts
                ]
                if not images:
                    errors.append(f"{label}: no images in folder")
                else:
                    suspicious = {".jpg", ".jpeg", ".png", ".webp", "\\.jpg", "\\.png"}
                    suspicious_names = [p.name for p in images if p.name.strip().lower() in suspicious]
                    if suspicious_names:
                        warnings.append(f"{label}: suspicious image names {suspicious_names}")

            if not isinstance(hooks, list) or not hooks:
                errors.append(f"{label}: missing hooks array")

    for path, kind in (
        (DEFAULT_MUSIC, "music"),
        (DEFAULT_DEMO, "demo video"),
        (DEFAULT_UI_IMAGE, "ui image"),
    ):
        if not path.exists():
            errors.append(f"Missing default {kind}: {path}")

    return errors, warnings


# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------


def get_images_from_folder(folder_path: Path, count: Optional[int] = None) -> List[Path]:
    """Get *count* random image paths from *folder_path*.

    If *count* exceeds the number of available images, images are repeated.
    """
    if not folder_path.exists():
        raise FileNotFoundError(f"Image folder not found: {folder_path}")

    extensions = {".jpg", ".jpeg", ".png", ".webp"}
    images = [f for f in folder_path.iterdir() if f.suffix.lower() in extensions]

    if not images:
        raise ValueError(f"No images found in: {folder_path}")

    if count is None:
        count = random.randint(MIN_IMAGES, MAX_IMAGES)

    if len(images) < count:
        selected = random.choices(images, k=count)
    else:
        selected = random.sample(images, count)

    random.shuffle(selected)
    return selected


def random_crop_image(
    img_path: Path,
    target_width: int,
    target_height: int,
    letterbox: bool = True,
) -> np.ndarray:
    """Load an image and randomly crop it to *target_width* × *target_height*.

    When *letterbox* is ``True`` the image is placed with black bars top/bottom.
    """
    with Image.open(img_path) as img:
        if img.mode != "RGB":
            img = img.convert("RGB")

        orig_w, orig_h = img.size

        if letterbox:
            return _crop_letterbox(img, orig_w, orig_h, target_width, target_height)
        return _crop_fill(img, orig_w, orig_h, target_width, target_height)


def _crop_letterbox(
    img: Image.Image,
    orig_w: int,
    orig_h: int,
    target_width: int,
    target_height: int,
) -> np.ndarray:
    """Letterboxed crop — image takes ~70 % of height with black bars."""
    content_height = int(target_height * 0.70)
    bar_height = (target_height - content_height) // 2

    scale = target_width / orig_w
    new_width = target_width
    new_height = int(orig_h * scale)

    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

    if new_height > content_height:
        max_y = new_height - content_height
        variation_y = int(max_y * CROP_VARIATION)
        crop_y = random.randint(
            max(0, max_y // 2 - variation_y),
            min(max_y, max_y // 2 + variation_y),
        )
        img = img.crop((0, crop_y, new_width, crop_y + content_height))
    elif new_height < content_height:
        padded = Image.new("RGB", (new_width, content_height), (0, 0, 0))
        paste_y = (content_height - new_height) // 2
        padded.paste(img, (0, paste_y))
        img = padded

    final_img = Image.new("RGB", (target_width, target_height), (0, 0, 0))
    final_img.paste(img, (0, bar_height))
    return np.array(final_img)


def _crop_fill(
    img: Image.Image,
    orig_w: int,
    orig_h: int,
    target_width: int,
    target_height: int,
) -> np.ndarray:
    """Fill-frame crop — scales to cover and randomly offsets."""
    target_ratio = target_width / target_height
    orig_ratio = orig_w / orig_h

    if orig_ratio > target_ratio:
        new_height = target_height
        new_width = int(orig_w * (target_height / orig_h))
    else:
        new_width = target_width
        new_height = int(orig_h * (target_width / orig_w))

    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

    crop_x = _random_offset(new_width - target_width)
    crop_y = _random_offset(new_height - target_height)

    cropped = img.crop((crop_x, crop_y, crop_x + target_width, crop_y + target_height))
    return np.array(cropped)


def _random_offset(max_val: int) -> int:
    """Return a random offset centred around *max_val / 2* with configured variation."""
    if max_val <= 0:
        return 0
    variation = int(max_val * CROP_VARIATION)
    return random.randint(
        max(0, max_val // 2 - variation),
        min(max_val, max_val // 2 + variation),
    )


# ---------------------------------------------------------------------------
# Rounded-rectangle mask (reused across clips)
# ---------------------------------------------------------------------------


def create_rounded_mask(size: Tuple[int, int], radius: int) -> ImageClip:
    """Create a high-resolution rounded-rectangle alpha mask as an ``ImageClip``."""
    factor = 2
    mask = Image.new("L", (size[0] * factor, size[1] * factor), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle(
        (0, 0, size[0] * factor, size[1] * factor),
        radius=radius * factor,
        fill=255,
    )
    mask = mask.resize(size, Image.Resampling.LANCZOS)
    mask_array = np.array(mask) / 255.0
    return ImageClip(mask_array, is_mask=True)


# ---------------------------------------------------------------------------
# Text overlay helpers
# ---------------------------------------------------------------------------


def create_text_overlay(text: str, video_size: Tuple[int, int]) -> ImageClip:
    """Create a TikTok-style text overlay centred on screen.

    The text is rendered to a static ``ImageClip`` to guarantee correct
    compositing order regardless of MoviePy backend quirks.
    """
    padded_text = text + "\n "  # prevents stroke clipping at bottom

    text_kwargs = dict(
        text=padded_text,
        font_size=FONT_SIZE,
        color=FONT_COLOR,
        stroke_color=STROKE_COLOR,
        stroke_width=STROKE_WIDTH,
        text_align="center",
        size=(video_size[0] - 300, None),
        method="caption",
    )
    if FONT_PATH:
        text_kwargs["font"] = FONT_PATH

    txt_clip = TextClip(**text_kwargs)

    try:
        img_array = txt_clip.get_frame(0)
        mask_array = txt_clip.mask.get_frame(0)

        final_clip = ImageClip(img_array)
        final_mask = ImageClip(mask_array, is_mask=True)
        final_clip = final_clip.with_mask(final_mask)
        final_clip = final_clip.with_position("center")
        return final_clip
    except Exception as exc:
        logger.warning("Could not rasterize text (%s), falling back to TextClip.", exc)
        return txt_clip.with_position("center")


def _render_overlay_text(
    overlay_text: str,
    video_size: Tuple[int, int],
) -> Tuple[ImageClip, ImageClip]:
    """Render *overlay_text* to an ``ImageClip`` with a transparent mask.

    Uses Pillow for emoji support via the macOS system font.

    Returns ``(rgb_clip, mask_clip)``.
    """
    try:
        if FONT_PATH:
            pil_font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
        else:
            pil_font = ImageFont.load_default()
    except Exception:
        pil_font = ImageFont.load_default()

    max_text_width = video_size[0] - 300
    chars_per_line = max(10, max_text_width // (FONT_SIZE // 2))

    wrapped_lines: List[str] = []
    for raw_line in overlay_text.split("\n"):
        wrapped_lines.extend(textwrap.wrap(raw_line, width=int(chars_per_line)) or [""])

    # Measure text dimensions
    dummy_img = Image.new("RGBA", (1, 1))
    dummy_draw = ImageDraw.Draw(dummy_img)
    line_bboxes = [dummy_draw.textbbox((0, 0), line, font=pil_font) for line in wrapped_lines]
    line_heights = [bb[3] - bb[1] for bb in line_bboxes]
    line_widths = [bb[2] - bb[0] for bb in line_bboxes]

    line_spacing = 8
    total_text_h = sum(line_heights) + line_spacing * (len(wrapped_lines) - 1)
    total_text_w = max(line_widths) if line_widths else 100

    pad = STROKE_WIDTH * 2 + 4
    canvas_w = total_text_w + pad * 2
    canvas_h = total_text_h + pad * 2

    txt_img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    txt_draw = ImageDraw.Draw(txt_img)

    y_cursor = pad
    for i, line in enumerate(wrapped_lines):
        lw = line_widths[i]
        x = (canvas_w - lw) // 2
        # Draw stroke
        for dx in range(-STROKE_WIDTH, STROKE_WIDTH + 1):
            for dy in range(-STROKE_WIDTH, STROKE_WIDTH + 1):
                if dx * dx + dy * dy <= STROKE_WIDTH * STROKE_WIDTH:
                    txt_draw.text(
                        (x + dx, y_cursor + dy), line,
                        font=pil_font, fill=(0, 0, 0, 255),
                    )
        # Draw fill
        txt_draw.text((x, y_cursor), line, font=pil_font, fill=(255, 255, 255, 255))
        y_cursor += line_heights[i] + line_spacing

    txt_array = np.array(txt_img)
    rgb_clip = ImageClip(txt_array[:, :, :3])
    alpha_clip = ImageClip(txt_array[:, :, 3] / 255.0, is_mask=True)
    return rgb_clip, alpha_clip


# ---------------------------------------------------------------------------
# Pretti overlay (demo + UI card + optional text)
# ---------------------------------------------------------------------------

# Animation constants
_SLIDE_UP_DURATION = 1.0
_PENDULUM_FREQ = 0.5
_SWAY_AMPLITUDE_X = 10
_SWAY_AMPLITUDE_Y = 5
_DEMO_SKIP = 1.0
_DEMO_SCALE = 0.55
_DEMO_CROP_TOP = 35
_DEMO_CROP_BOTTOM = 35
_DEMO_CORNER_RADIUS = 95
_UI_CORNER_RADIUS = 20
_BLOCK_GAP = 20
_BLOCK_Y_OFFSET = 30


def create_pretti_overlay(
    demo_path: Path,
    ui_image_path: Path,
    duration: float,
    video_size: Tuple[int, int],
    overlay_text: Optional[str] = None,
) -> List:
    """Build the Pretti overlay: UI card above the phone demo with wobble.

    Returns a list of clips (demo, ui, and optionally overlay text).
    """
    # --- Demo video ---
    demo = VideoFileClip(str(demo_path)).subclipped(_DEMO_SKIP, _DEMO_SKIP + duration)
    demo_width = int(video_size[0] * _DEMO_SCALE)
    demo = demo.with_effects([Resize(width=demo_width)])
    demo = demo.cropped(y1=_DEMO_CROP_TOP, y2=demo.h - _DEMO_CROP_BOTTOM)
    demo_height = demo.h

    demo_mask = create_rounded_mask(demo.size, radius=_DEMO_CORNER_RADIUS).with_duration(duration)
    demo = demo.with_mask(demo_mask)

    # --- UI card ---
    ui_img = Image.open(ui_image_path)
    ui_scale = demo_width / ui_img.width
    ui_new_width = demo_width
    ui_new_height = int(ui_img.height * ui_scale)
    ui_img = ui_img.resize((ui_new_width, ui_new_height), Image.Resampling.LANCZOS)

    if ui_img.mode != "RGB":
        ui_img = ui_img.convert("RGB")

    ui_clip = ImageClip(np.array(ui_img)).with_duration(duration)
    ui_mask = create_rounded_mask(ui_clip.size, radius=_UI_CORNER_RADIUS).with_duration(duration)
    ui_clip = ui_clip.with_mask(ui_mask)

    # --- Layout ---
    final_x = (video_size[0] - demo_width) // 2
    total_block_height = ui_new_height + _BLOCK_GAP + demo_height
    block_top = (video_size[1] - total_block_height) // 2 + _BLOCK_Y_OFFSET

    final_ui_y = block_top
    final_demo_y = block_top + ui_new_height + _BLOCK_GAP

    # --- Position callbacks with pendulum wobble ---
    def _make_position_fn(final_y: int):
        def position(t):
            if t < _SLIDE_UP_DURATION:
                progress = t / _SLIDE_UP_DURATION
                ease = 1 - (1 - progress) ** 3
                start_y = float(video_size[1])
                y = start_y + (final_y - start_y) * ease
                if y >= video_size[1]:
                    return (int(final_x), 10000)
                return (int(final_x), int(y))
            wobble_t = t - _SLIDE_UP_DURATION
            off_x = _SWAY_AMPLITUDE_X * np.sin(wobble_t * _PENDULUM_FREQ * 2 * np.pi)
            off_y = _SWAY_AMPLITUDE_Y * np.cos(wobble_t * _PENDULUM_FREQ * 2 * np.pi)
            return (int(final_x + off_x), int(final_y + abs(off_y)))
        return position

    demo_position = _make_position_fn(final_demo_y)
    ui_position = _make_position_fn(final_ui_y)

    demo = demo.with_position(demo_position).without_audio()
    ui_clip = ui_clip.with_position(ui_position)

    result_clips = [demo, ui_clip]

    # --- Optional overlay text ---
    if overlay_text:
        rgb_clip, alpha_clip = _render_overlay_text(overlay_text, video_size)
        overlay_txt = rgb_clip.with_mask(alpha_clip).with_duration(duration)

        overlay_w = overlay_txt.w

        def overlay_text_position(t):
            if t < _SLIDE_UP_DURATION:
                return (0, 10000)
            demo_x, demo_y = demo_position(t)
            if demo_y >= video_size[1] or demo_y == 10000:
                return (0, 10000)
            text_x = (video_size[0] - overlay_w) // 2
            text_y = demo_y + (demo_height - overlay_txt.h) // 2
            text_y = max(0, min(text_y, video_size[1] - overlay_txt.h - 1))
            return (int(text_x), int(text_y))

        overlay_txt = overlay_txt.with_position(overlay_text_position)
        result_clips.append(overlay_txt)

    return result_clips


# ---------------------------------------------------------------------------
# Main video generation pipeline
# ---------------------------------------------------------------------------


def generate_video(
    category: str,
    feature_id: str,
    hook_index: Optional[int] = None,
    output_name: Optional[str] = None,
    dry_run: bool = False,
) -> Optional[Path]:
    """Generate a complete short-form video for a feature.

    Returns the output ``Path`` on success, or ``None`` for dry runs.
    """
    info = get_feature_info(category, feature_id)
    if not info:
        raise ValueError(f"Feature not found: {category}/{feature_id}")

    folder = info.get("folder")
    hooks = info.get("hooks", [])

    if not hooks:
        raise ValueError(f"No hooks defined for: {category}/{feature_id}")

    # Select hook
    if hook_index is not None:
        if not 0 <= hook_index < len(hooks):
            raise ValueError(
                f"Hook index out of range for {category}/{feature_id}: "
                f"{hook_index} (valid: 0..{len(hooks) - 1})"
            )
        hook_text = hooks[hook_index]
    else:
        hook_text = random.choice(hooks)

    image_folder = IMAGES_DIR / folder

    # --- Dry run ---
    if dry_run:
        _print_dry_run(category, feature_id, hook_text, image_folder)
        return None

    # --- Build clips ---
    num_images = random.randint(MIN_IMAGES, MAX_IMAGES)
    image_paths = get_images_from_folder(image_folder, num_images)

    logger.info("Creating video with %d images …", len(image_paths))
    logger.info("Hook: %s", hook_text)

    clips: List = []
    slideshow = None
    audio = None
    final = None

    try:
        # Image slideshow
        for img_path in image_paths:
            img_array = random_crop_image(img_path, VIDEO_WIDTH, VIDEO_HEIGHT)
            clip = ImageClip(img_array).with_duration(IMAGE_DURATION)
            clip = clip.with_effects([FadeIn(FADE_DURATION), FadeOut(FADE_DURATION)])
            clips.append(clip)

        slideshow = concatenate_videoclips(clips, method="compose")
        total_duration = slideshow.duration

        # Hook text overlay (visible until demo appears)
        demo_start = max(0, total_duration - 3.0)
        text_clip = create_text_overlay(hook_text, (VIDEO_WIDTH, VIDEO_HEIGHT))
        text_clip = text_clip.with_duration(demo_start)

        # Demo overlay lines
        hooks_db = load_hooks()
        demo_overlay_lines = hooks_db.get("demo_overlay_lines", [])
        demo_overlay_text = random.choice(demo_overlay_lines) if demo_overlay_lines else None

        # Build floating demo overlay
        overlay_duration = total_duration - demo_start
        overlay_clips = create_pretti_overlay(
            DEFAULT_DEMO,
            DEFAULT_UI_IMAGE,
            overlay_duration,
            (VIDEO_WIDTH, VIDEO_HEIGHT),
            overlay_text=demo_overlay_text,
        )
        overlay_clips = [c.with_start(demo_start) for c in overlay_clips]

        # Composite
        final = CompositeVideoClip(
            [slideshow, text_clip] + overlay_clips,
            size=(VIDEO_WIDTH, VIDEO_HEIGHT),
        )

        # Audio
        audio = AudioFileClip(str(DEFAULT_MUSIC))
        audio_start = MUSIC_START_TIME
        if audio_start > audio.duration:
            logger.warning(
                "Music start time %.1fs exceeds track duration %.1fs — starting from 0.",
                audio_start,
                audio.duration,
            )
            audio_start = 0
        audio = audio.subclipped(audio_start, audio_start + total_duration)
        final = final.with_audio(audio)

        # Output path
        if output_name is None:
            output_name = _next_output_name(feature_id)

        output_path = OUTPUT_DIR / output_name

        logger.info("Rendering to: %s", output_path)

        final.write_videofile(
            str(output_path),
            fps=FPS,
            codec="libx264",
            audio_codec="aac",
            threads=4,
            preset="medium",
            temp_audiofile=str(TEMP_DIR / f"temp-audio-{output_name}.m4a"),
            remove_temp=True,
        )

        logger.info("Done! Output: %s", output_path)
        return output_path

    finally:
        # Deterministic resource cleanup
        for c in clips:
            c.close()
        if slideshow is not None:
            slideshow.close()
        if audio is not None:
            audio.close()
        if final is not None:
            final.close()


def _print_dry_run(
    category: str,
    feature_id: str,
    hook_text: str,
    image_folder: Path,
) -> None:
    """Print diagnostic info for a dry-run invocation."""
    print("\n=== DRY RUN ===")
    print(f"Category: {category}")
    print(f"Feature: {feature_id}")
    print(f"Hook: {hook_text}")
    print(f"Image folder: {image_folder}")
    print(f"Folder exists: {image_folder.exists()}")
    if image_folder.exists():
        images = [
            p for p in image_folder.iterdir()
            if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
        ]
        print(f"Images available: {len(images)}")
    print(f"Music: {DEFAULT_MUSIC}")
    print(f"Music exists: {DEFAULT_MUSIC.exists()}")
    print(f"Demo: {DEFAULT_DEMO}")
    print(f"Demo exists: {DEFAULT_DEMO.exists()}")


def _next_output_name(feature_id: str) -> str:
    """Return the next free ``<feature>_NNN.mp4`` name in ``OUTPUT_DIR``."""
    existing_nums = set()
    prefix = f"{feature_id}_"
    for p in OUTPUT_DIR.glob(f"{feature_id}_*.mp4"):
        stem = p.stem
        if not stem.startswith(prefix):
            continue
        suffix = stem[len(prefix):]
        if suffix.isdigit():
            existing_nums.add(int(suffix))

    next_num = 1
    while next_num in existing_nums:
        next_num += 1
    return f"{feature_id}_{next_num:03d}.mp4"
