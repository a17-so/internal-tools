"""Shared configuration constants."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = ROOT / "data"
HOOKS_DIR = DATA_DIR / "hooks"
SEEDS_DIR = DATA_DIR / "seeds"
MANIFESTS_DIR = DATA_DIR / "manifests"

OUTPUT_DIR = ROOT / "output"
VIDEOS_DIR = OUTPUT_DIR / "videos"
REPORTS_DIR = OUTPUT_DIR / "reports"

CAPTURED_PATH = HOOKS_DIR / "captured.jsonl"
CANDIDATES_PATH = HOOKS_DIR / "candidates.jsonl"
APPROVED_PATH = HOOKS_DIR / "approved.jsonl"
COOLDOWN_STORE_PATH = HOOKS_DIR / "cooldown_store.json"

SEED_FILE_DEFAULT = SEEDS_DIR / "ig_accounts.txt"
SEED_FILE_EXAMPLE = SEEDS_DIR / "ig_accounts.example.txt"

MANIFEST_DEFAULT = MANIFESTS_DIR / "everest_styles.json"
MANIFEST_EXAMPLE = MANIFESTS_DIR / "everest_styles.example.json"

RENDER_LOG_PATH = REPORTS_DIR / "render_log.jsonl"

VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS = 30

DEFAULT_SESSION_TARGET = 120
DEFAULT_COOLDOWN_DAYS = 21
DEFAULT_HOOK_SECONDS_MIN = 3.0
DEFAULT_HOOK_SECONDS_MAX = 5.0

PHASH_THRESHOLD = 8

SUPPORTED_VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".webm"}
