"""
Configuration for the Pretti Edit Maker tool.
"""
import os
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).parent
ASSETS_DIR = BASE_DIR / "assets"
OUTPUT_DIR = BASE_DIR / "output"

# Asset paths
IMAGES_DIR = ASSETS_DIR / "images"
MUSIC_DIR = ASSETS_DIR / "music"
UI_DIR = ASSETS_DIR / "ui"
FONTS_DIR = BASE_DIR / "fonts"

# Default files
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
IMAGE_DURATION = 1.0  # seconds per image
DEMO_DURATION = 3.0   # seconds for floating UI at end
FADE_DURATION = 0.1   # transition fade
MUSIC_START_TIME = 36.0 # seconds

# Text overlay settings
FONT_SIZE = 48
FONT_COLOR = "white"
STROKE_COLOR = "black"
STROKE_WIDTH = 3
TEXT_POSITION = ("center", 0.85)  # centered, 85% down from top

# Random crop settings
CROP_VARIATION = 0.15  # 15% variation in crop position

# Ensure output directory exists
OUTPUT_DIR.mkdir(exist_ok=True)
