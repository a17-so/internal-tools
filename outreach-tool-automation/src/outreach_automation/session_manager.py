from __future__ import annotations

from pathlib import Path

from outreach_automation.models import Platform


class SessionManager:
    def __init__(self, ig_profile_root: Path, tiktok_profile_root: Path) -> None:
        self._ig_root = ig_profile_root
        self._tt_root = tiktok_profile_root
        self._ig_root.mkdir(parents=True, exist_ok=True)
        self._tt_root.mkdir(parents=True, exist_ok=True)

    def path_for(self, platform: Platform, handle: str) -> Path:
        return self.profile_dir_for(platform, handle)

    def profile_dir_for(self, platform: Platform, handle: str) -> Path:
        safe = handle.replace("@", "").replace("/", "_").strip()
        if not safe:
            raise ValueError("Account handle cannot be empty for profile directory resolution")
        if platform is Platform.INSTAGRAM:
            return self._ig_root / safe
        if platform is Platform.TIKTOK:
            return self._tt_root / safe
        raise ValueError(f"No session path for platform: {platform.value}")
