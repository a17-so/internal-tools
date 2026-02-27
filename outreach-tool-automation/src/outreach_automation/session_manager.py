from __future__ import annotations

from pathlib import Path

from outreach_automation.models import Platform


class SessionManager:
    def __init__(self, ig_dir: Path, tiktok_dir: Path) -> None:
        self._ig_dir = ig_dir
        self._tt_dir = tiktok_dir
        self._ig_dir.mkdir(parents=True, exist_ok=True)
        self._tt_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, platform: Platform, handle: str) -> Path:
        safe = handle.replace("@", "").replace("/", "_")
        if platform is Platform.INSTAGRAM:
            return self._ig_dir / f"{safe}.json"
        if platform is Platform.TIKTOK:
            return self._tt_dir / f"{safe}.json"
        raise ValueError(f"No session path for platform: {platform.value}")
