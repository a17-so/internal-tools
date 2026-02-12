"""
Core video generation logic for Pretti Edit Maker.
"""
import random
from pathlib import Path
from typing import List, Tuple
import json

from moviepy import (
    ImageClip, 
    VideoFileClip, 
    AudioFileClip,
    TextClip,
    CompositeVideoClip,
    concatenate_videoclips
)
from moviepy.video.fx import FadeIn, FadeOut, Resize
from PIL import Image
import numpy as np

from config import (
    IMAGES_DIR, OUTPUT_DIR, DEFAULT_MUSIC, DEFAULT_DEMO, DEFAULT_UI_IMAGE, HOOKS_FILE,
    VIDEO_WIDTH, VIDEO_HEIGHT, FPS,
    MIN_IMAGES, MAX_IMAGES, IMAGE_DURATION, DEMO_DURATION, FADE_DURATION, MUSIC_START_TIME,
    FONT_SIZE, FONT_COLOR, STROKE_COLOR, STROKE_WIDTH, TEXT_POSITION,
    CROP_VARIATION
)


def load_hooks() -> dict:
    """Load the hooks database."""
    with open(HOOKS_FILE, 'r') as f:
        return json.load(f)


def get_feature_info(category: str, feature_id: str) -> dict:
    """Get info for a specific feature."""
    hooks_db = load_hooks()
    features = hooks_db.get("features", {})
    category_data = features.get(category, {})
    return category_data.get(feature_id, {})


def list_all_features() -> List[Tuple[str, str, str]]:
    """List all available features with their categories."""
    hooks_db = load_hooks()
    result = []
    for category, features in hooks_db.get("features", {}).items():
        for feature_id, info in features.items():
            result.append((category, feature_id, info.get("hooks", [""])[0]))
    return result


def get_images_from_folder(folder_path: Path, count: int = None) -> List[Path]:
    """Get image paths from a folder, randomly selecting if count specified."""
    if not folder_path.exists():
        raise FileNotFoundError(f"Image folder not found: {folder_path}")
    
    extensions = {'.jpg', '.jpeg', '.png', '.webp'}
    images = [f for f in folder_path.iterdir() 
              if f.suffix.lower() in extensions]
    
    if not images:
        raise ValueError(f"No images found in: {folder_path}")
    
    if count is None:
        count = random.randint(MIN_IMAGES, MAX_IMAGES)
    
    # If we need more images than available, allow repeats
    if len(images) < count:
        selected = random.choices(images, k=count)
    else:
        selected = random.sample(images, count)
    
    random.shuffle(selected)
    return selected


def random_crop_image(img_path: Path, target_width: int, target_height: int, letterbox: bool = True) -> np.ndarray:
    """Load and randomly crop an image to target dimensions with letterbox effect."""
    with Image.open(img_path) as img:
        # Convert to RGB if necessary
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        orig_w, orig_h = img.size
        
        if letterbox:
            # Create letterbox effect: image is more square with black bars
            # Image content takes up ~70% of height, leaving 15% black bars top and bottom
            content_height = int(target_height * 0.70)
            bar_height = (target_height - content_height) // 2
            
            # Resize image to fit width, crop to content_height
            scale = target_width / orig_w
            new_width = target_width
            new_height = int(orig_h * scale)
            
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Random crop vertically with variation
            if new_height > content_height:
                max_y = new_height - content_height
                variation_y = int(max_y * CROP_VARIATION)
                crop_y = random.randint(max(0, max_y//2 - variation_y), 
                                         min(max_y, max_y//2 + variation_y))
                img = img.crop((0, crop_y, new_width, crop_y + content_height))
            elif new_height < content_height:
                # Image is shorter than content area, pad it
                padded = Image.new('RGB', (new_width, content_height), (0, 0, 0))
                paste_y = (content_height - new_height) // 2
                padded.paste(img, (0, paste_y))
                img = padded
            
            # Create final image with black bars
            final_img = Image.new('RGB', (target_width, target_height), (0, 0, 0))
            final_img.paste(img, (0, bar_height))
            
            return np.array(final_img)
        else:
            # Original behavior: fill entire frame
            target_ratio = target_width / target_height
            orig_ratio = orig_w / orig_h
            
            if orig_ratio > target_ratio:
                new_height = target_height
                new_width = int(orig_w * (target_height / orig_h))
            else:
                new_width = target_width
                new_height = int(orig_h * (target_width / orig_w))
            
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            max_x = new_width - target_width
            max_y = new_height - target_height
            
            if max_x > 0:
                variation_x = int(max_x * CROP_VARIATION)
                crop_x = random.randint(max(0, max_x//2 - variation_x), 
                                         min(max_x, max_x//2 + variation_x))
            else:
                crop_x = 0
                
            if max_y > 0:
                variation_y = int(max_y * CROP_VARIATION)
                crop_y = random.randint(max(0, max_y//2 - variation_y), 
                                         min(max_y, max_y//2 + variation_y))
            else:
                crop_y = 0
            
            cropped = img.crop((crop_x, crop_y, 
                               crop_x + target_width, 
                               crop_y + target_height))
            
            return np.array(cropped)


def create_text_overlay(text: str, video_size: Tuple[int, int]) -> TextClip:
    """Create a TikTok-style text overlay."""
    # Use system font path on macOS
    font_path = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
    
    # Add padding via newline to prevent stroke clipping at bottom
    padded_text = text + "\n "
    
    txt_clip = TextClip(
        text=padded_text,
        font_size=FONT_SIZE,
        color=FONT_COLOR,
        stroke_color=STROKE_COLOR,
        stroke_width=STROKE_WIDTH,
        font=font_path,
        text_align="center",
        size=(video_size[0] - 300, None),  # More padding to force line wrapping
        method="caption"
    )
    
    # Force render to static image to guarantee layering
    # This prevents any TextClip compositing issues
    try:
        # Get the first frame (it's static text)
        img_array = txt_clip.get_frame(0)
        mask_array = txt_clip.mask.get_frame(0)
        
        final_clip = ImageClip(img_array)
        final_mask = ImageClip(mask_array, is_mask=True)
        final_clip = final_clip.with_mask(final_mask)
        
        # Position the text centered
        final_clip = final_clip.with_position("center")
        return final_clip
    except Exception as e:
        print(f"Warning: Could not rasterize text ({e}), using TextClip directly.")
        return txt_clip.with_position("center")


def create_pretti_overlay(demo_path: Path, ui_image_path: Path, duration: float, video_size: Tuple[int, int], overlay_text: str = None) -> List:
    """
    Create Pretti app overlay with UI card ABOVE demo video,
    plus overlay text on top of the phone demo.
    Both have a subtle pendulum wobble effect.
    """
    # Load and resize demo video (takes up good chunk of screen)
    # Skip first 1s of demo, then take needed duration
    demo_skip = 1.0
    demo = VideoFileClip(str(demo_path)).subclipped(demo_skip, demo_skip + duration)
    demo_scale = 0.55  # 55% of screen width for bigger presence
    demo_width = int(video_size[0] * demo_scale)
    demo = demo.with_effects([Resize(width=demo_width)])
    # Crop 35px from top and bottom of demo video (reduced height)
    demo = demo.cropped(y1=35, y2=demo.h-35)
    demo_height = demo.h

    # Create rounded mask for demo
    def create_rounded_mask(size, radius):
        from PIL import Image, ImageDraw
        # Create high-res mask for smoothness
        factor = 2
        mask = Image.new('L', (size[0]*factor, size[1]*factor), 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle((0, 0, size[0]*factor, size[1]*factor), radius=radius*factor, fill=255)
        mask = mask.resize(size, Image.Resampling.LANCZOS)
        # Normalize to 0-1 float for MoviePy
        mask_array = np.array(mask) / 255.0
        return ImageClip(mask_array, is_mask=True)

    # Apply rounded mask to demo video to remove black corners (increased radius)
    demo_mask = create_rounded_mask(demo.size, radius=95).with_duration(duration)
    demo = demo.with_mask(demo_mask)

    # Load and resize UI image
    ui_img = Image.open(ui_image_path)
    
    # Scale UI to match demo width first
    ui_scale = demo_width / ui_img.width
    ui_new_width = demo_width
    ui_new_height = int(ui_img.height * ui_scale)
    ui_img = ui_img.resize((ui_new_width, ui_new_height), Image.Resampling.LANCZOS)
    
    if ui_img.mode != 'RGB':
        ui_img = ui_img.convert('RGB')
        
    ui_array = np.array(ui_img)
    ui_clip = ImageClip(ui_array).with_duration(duration)
    
    # Apply rounded mask to UI clip (less radius)
    ui_mask = create_rounded_mask(ui_clip.size, radius=20).with_duration(duration)
    ui_clip = ui_clip.with_mask(ui_mask)
    
    # Gap between UI and demo
    gap = 20
    
    # Position settings — UI is ABOVE demo, shifted down a bit for centering
    final_x = (video_size[0] - demo_width) // 2
    # Total block height = ui_height + gap + demo_height
    total_block_height = ui_new_height + gap + demo_height
    # Center the block vertically, then shift down slightly (+30px)
    block_top = (video_size[1] - total_block_height) // 2 + 30
    
    final_ui_y = block_top                           # UI on top
    final_demo_y = block_top + ui_new_height + gap   # Demo below UI
    
    # Animation settings
    slide_up_duration = 1.0  # Slower fly-in (was 0.5)
    pendulum_freq = 0.5
    sway_amplitude_x = 10
    sway_amplitude_y = 5
    
    def ui_position(t):
        """UI card — slides in from bottom, lands ABOVE demo."""
        if t < slide_up_duration:
            progress = t / slide_up_duration
            ease = 1 - (1 - progress) ** 3
            
            start_y = float(video_size[1])
            y = start_y + (final_ui_y - start_y) * ease
            
            if y >= video_size[1]:
                return (int(final_x), 10000)
            return (int(final_x), int(y))
        else:
            # Chill pendulum wobble
            wobble_t = t - slide_up_duration
            off_x = sway_amplitude_x * np.sin(wobble_t * pendulum_freq * 2 * np.pi)
            off_y = sway_amplitude_y * np.cos(wobble_t * pendulum_freq * 2 * np.pi)
            return (int(final_x + off_x), int(final_ui_y + abs(off_y)))
    
    def demo_position(t):
        """Phone demo — slides in from bottom, lands BELOW UI."""
        if t < slide_up_duration:
             progress = t / slide_up_duration
             ease = 1 - (1 - progress) ** 3
             
             start_y = float(video_size[1])
             y = start_y + (final_demo_y - start_y) * ease
             
             if y >= video_size[1]:
                 return (int(final_x), 10000)
             return (int(final_x), int(y))
        else:
             # Synchronized wobble
             wobble_t = t - slide_up_duration
             off_x = sway_amplitude_x * np.sin(wobble_t * pendulum_freq * 2 * np.pi)
             off_y = sway_amplitude_y * np.cos(wobble_t * pendulum_freq * 2 * np.pi)
             return (int(final_x + off_x), int(final_demo_y + abs(off_y)))

    # Apply positions (demo audio removed)
    demo = demo.with_position(demo_position).without_audio()
    ui_clip = ui_clip.with_position(ui_position)
    
    result_clips = [demo, ui_clip]
    
    # Create overlay text on top of phone demo (same style as hook text)
    # Uses Pillow rendering to support emoji via Apple Color Emoji font
    if overlay_text:
        from PIL import Image as PILImage, ImageDraw, ImageFont
        import textwrap
        
        # Render text with Pillow for emoji support
        font_path = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
        try:
            pil_font = ImageFont.truetype(font_path, FONT_SIZE)
        except Exception:
            pil_font = ImageFont.load_default()
        
        max_text_width = video_size[0] - 300
        
        # Word-wrap the text
        wrapped_lines = []
        for raw_line in overlay_text.split('\n'):
            # Estimate chars per line based on font size
            chars_per_line = max(10, max_text_width // (FONT_SIZE // 2))
            wrapped_lines.extend(textwrap.wrap(raw_line, width=int(chars_per_line)) or [''])
        
        # Measure text dimensions
        dummy_img = PILImage.new('RGBA', (1, 1))
        dummy_draw = ImageDraw.Draw(dummy_img)
        line_bboxes = [dummy_draw.textbbox((0, 0), line, font=pil_font) for line in wrapped_lines]
        line_heights = [bb[3] - bb[1] for bb in line_bboxes]
        line_widths = [bb[2] - bb[0] for bb in line_bboxes]
        
        line_spacing = 8
        total_text_h = sum(line_heights) + line_spacing * (len(wrapped_lines) - 1)
        total_text_w = max(line_widths) if line_widths else 100
        
        # Add padding for stroke
        pad = STROKE_WIDTH * 2 + 4
        canvas_w = total_text_w + pad * 2
        canvas_h = total_text_h + pad * 2
        
        # Draw text with stroke on transparent canvas
        txt_img = PILImage.new('RGBA', (canvas_w, canvas_h), (0, 0, 0, 0))
        txt_draw = ImageDraw.Draw(txt_img)
        
        y_cursor = pad
        for i, line in enumerate(wrapped_lines):
            lw = line_widths[i]
            x = (canvas_w - lw) // 2
            # Stroke
            for dx in range(-STROKE_WIDTH, STROKE_WIDTH + 1):
                for dy in range(-STROKE_WIDTH, STROKE_WIDTH + 1):
                    if dx * dx + dy * dy <= STROKE_WIDTH * STROKE_WIDTH:
                        txt_draw.text((x + dx, y_cursor + dy), line, font=pil_font, fill=(0, 0, 0, 255))
            # Fill
            txt_draw.text((x, y_cursor), line, font=pil_font, fill=(255, 255, 255, 255))
            y_cursor += line_heights[i] + line_spacing
        
        # Convert to MoviePy clip with mask
        txt_array = np.array(txt_img)
        rgb_array = txt_array[:, :, :3]
        alpha_array = txt_array[:, :, 3] / 255.0
        
        overlay_txt = ImageClip(rgb_array)
        overlay_mask = ImageClip(alpha_array, is_mask=True)
        overlay_txt = overlay_txt.with_mask(overlay_mask)
        
        overlay_txt = overlay_txt.with_duration(duration)
        
        # Position overlay text centered on the demo area, moving with it
        # Only show after slide_up_duration to prevent partial-frame clipping errors
        def overlay_text_position(t):
            # Hide text during slide-in animation
            if t < slide_up_duration:
                return (0, 10000)
            demo_x, demo_y = demo_position(t)
            # Extra safety: if demo is off-screen, hide text too
            if demo_y >= video_size[1] or demo_y == 10000:
                return (0, 10000)
            # Center text horizontally on screen, vertically on demo
            text_x = (video_size[0] - overlay_txt.w) // 2
            text_y = demo_y + (demo_height - overlay_txt.h) // 2
            # Clamp to prevent going below frame
            text_y = min(text_y, video_size[1] - overlay_txt.h - 1)
            text_y = max(0, text_y)
            return (int(text_x), int(text_y))
        
        overlay_txt = overlay_txt.with_position(overlay_text_position)
        result_clips.append(overlay_txt)
    
    return result_clips



def generate_video(
    category: str,
    feature_id: str,
    hook_index: int = None,
    output_name: str = None,
    dry_run: bool = False
) -> Path:
    """Generate a complete video for a feature."""
    
    # Get feature info
    info = get_feature_info(category, feature_id)
    if not info:
        raise ValueError(f"Feature not found: {category}/{feature_id}")
    
    folder = info.get("folder")
    hooks = info.get("hooks", [])
    
    if not hooks:
        raise ValueError(f"No hooks defined for: {category}/{feature_id}")
    
    # Select hook
    if hook_index is not None and 0 <= hook_index < len(hooks):
        hook_text = hooks[hook_index]
    else:
        hook_text = random.choice(hooks)
    
    # Get image folder
    image_folder = IMAGES_DIR / folder
    
    if dry_run:
        print(f"\n=== DRY RUN ===")
        print(f"Category: {category}")
        print(f"Feature: {feature_id}")
        print(f"Hook: {hook_text}")
        print(f"Image folder: {image_folder}")
        print(f"Folder exists: {image_folder.exists()}")
        if image_folder.exists():
            images = list(image_folder.glob("*.jpg")) + list(image_folder.glob("*.png"))
            print(f"Images available: {len(images)}")
        print(f"Music: {DEFAULT_MUSIC}")
        print(f"Music exists: {DEFAULT_MUSIC.exists()}")
        print(f"Demo: {DEFAULT_DEMO}")
        print(f"Demo exists: {DEFAULT_DEMO.exists()}")
        return None
    
    # Get random images
    num_images = random.randint(MIN_IMAGES, MAX_IMAGES)
    image_paths = get_images_from_folder(image_folder, num_images)
    
    print(f"Creating video with {len(image_paths)} images...")
    print(f"Hook: {hook_text}")
    
    # Create image clips
    clips = []
    for img_path in image_paths:
        # Random crop the image
        img_array = random_crop_image(img_path, VIDEO_WIDTH, VIDEO_HEIGHT)
        clip = ImageClip(img_array).with_duration(IMAGE_DURATION)
        
        # Add fade transitions
        clip = clip.with_effects([
            FadeIn(FADE_DURATION),
            FadeOut(FADE_DURATION)
        ])
        
        clips.append(clip)
    
    # Concatenate image clips
    slideshow = concatenate_videoclips(clips, method="compose")
    total_duration = slideshow.duration
    
    # Create text overlay — only lasts until demo appears (hook text removed when demo slides in)
    demo_start = max(0, total_duration - 3.0)  # Starts with 3 seconds left
    text_clip = create_text_overlay(hook_text, (VIDEO_WIDTH, VIDEO_HEIGHT))
    text_clip = text_clip.with_duration(demo_start)  # End hook text when demo appears
    
    # Pick a random overlay line for the demo
    hooks_db = load_hooks()
    demo_overlay_lines = hooks_db.get("demo_overlay_lines", [])
    demo_overlay_text = random.choice(demo_overlay_lines) if demo_overlay_lines else None
    
    # Create floating demo for last DEMO_DURATION seconds with overlay text on top
    overlay_duration = total_duration - demo_start
    overlay_clips = create_pretti_overlay(
        DEFAULT_DEMO, DEFAULT_UI_IMAGE, overlay_duration,
        (VIDEO_WIDTH, VIDEO_HEIGHT), overlay_text=demo_overlay_text
    )
    # Set start time for all overlay clips
    overlay_clips = [clip.with_start(demo_start) for clip in overlay_clips]
    
    # Composite all layers:
    # 1. Slideshow (bottom)
    # 2. Hook text (disappears at demo_start)
    # 3. Demo + UI + overlay text (appears at demo_start)
    final = CompositeVideoClip(
        [slideshow, text_clip] + overlay_clips,
        size=(VIDEO_WIDTH, VIDEO_HEIGHT)
    )
    
    # Add music
    audio = AudioFileClip(str(DEFAULT_MUSIC))
    
    # Use fixed start time if specified, otherwise random (but here we want fixed 36s)
    audio_start = MUSIC_START_TIME
    
    # Ensure start time is valid
    if audio_start > audio.duration:
        print(f"Warning: Music start time {audio_start}s is beyond duration {audio.duration}s. Starting from 0.")
        audio_start = 0
        
    audio = audio.subclipped(audio_start, audio_start + total_duration)
    final = final.with_audio(audio)
    
    # Generate output filename
    if output_name is None:
        existing = list(OUTPUT_DIR.glob(f"{feature_id}_*.mp4"))
        next_num = len(existing) + 1
        output_name = f"{feature_id}_{next_num:03d}.mp4"
    
    output_path = OUTPUT_DIR / output_name
    
    print(f"Rendering to: {output_path}")
    
    # Ensure temp directory exists
    temp_dir = Path("temp")
    temp_dir.mkdir(exist_ok=True)
    
    final.write_videofile(
        str(output_path),
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        threads=4,
        preset="medium",
        temp_audiofile=str(temp_dir / f"temp-audio-{output_name}.m4a"),
        remove_temp=True
    )
    
    # Cleanup
    final.close()
    slideshow.close()
    audio.close()
    for clip in clips:
        clip.close()
    
    print(f"Done! Output: {output_path}")
    return output_path
