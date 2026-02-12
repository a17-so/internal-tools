"""
Configuration for the Pretti Edit Maker tool.
"""
from pathlib import Path

__all__ = [
    "BASE_DIR", "ASSETS_DIR", "OUTPUT_DIR",
    "IMAGES_DIR", "MUSIC_DIR", "UI_DIR",
    "DEFAULT_MUSIC", "DEFAULT_DEMO", "DEFAULT_UI_IMAGE", "HOOKS_FILE",
    "VIDEO_WIDTH", "VIDEO_HEIGHT", "FPS",
    "MIN_IMAGES", "MAX_IMAGES", "IMAGE_DURATION", "DEMO_DURATION",
    "FADE_DURATION", "MUSIC_START_TIME",
    "FONT_PATH", "FONT_SIZE", "FONT_COLOR", "STROKE_COLOR", "STROKE_WIDTH",
    "TEXT_POSITION", "CROP_VARIATION",
]

# Base paths
BASE_DIR = Path(__file__).parent
ASSETS_DIR = BASE_DIR / "assets"
OUTPUT_DIR = BASE_DIR / "output"

# Asset paths
IMAGES_DIR = ASSETS_DIR / "images"
MUSIC_DIR = ASSETS_DIR / "music"
UI_DIR = ASSETS_DIR / "ui"

# Default files
DEFAULT_MUSIC = MUSIC_DIR / "barnacle boi - don't dwell (slowed) - dreamscape (youtube).mp3"
DEFAULT_DEMO = UI_DIR / "demo_v3.mp4"
DEFAULT_UI_IMAGE = UI_DIR / "pretti_ui.png"
HOOKS_FILE = BASE_DIR / "hooks.json"

# Video settings
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920  # 9:16 vertical
FPS = 30

# Timing settings
MIN_IMAGES = 7
MAX_IMAGES = 11
IMAGE_DURATION = 1.0   # seconds per image
DEMO_DURATION = 3.0    # seconds for floating UI at end
FADE_DURATION = 0.1    # transition fade
MUSIC_START_TIME = 36.0  # seconds into the track to start

# Font settings (macOS system font — update path for other platforms)
FONT_PATH = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
FONT_SIZE = 48
FONT_COLOR = "white"
STROKE_COLOR = "black"
STROKE_WIDTH = 3
TEXT_POSITION = ("center", 0.85)  # centered, 85% down from top

# Random crop settings
CROP_VARIATION = 0.15  # 15% variation in crop position

# Ensure output directory exists
OUTPUT_DIR.mkdir(exist_ok=True)
