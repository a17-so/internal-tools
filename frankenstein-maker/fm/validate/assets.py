"""Asset validation checks."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple


def validate_manifest_assets(data: Dict) -> Tuple[List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []

    styles = data.get("styles", {})
    for style_name, cfg in styles.items():
        clip_pools = cfg.get("clip_pools", [])
        if not clip_pools:
            warnings.append(f"Style {style_name} has empty clip_pools")
        for p in clip_pools:
            pp = Path(str(p))
            if not pp.exists():
                warnings.append(f"Missing clip pool file: {pp}")

        icon_path = Path(str(cfg.get("icon", {}).get("path", "")))
        if str(icon_path) and not icon_path.exists():
            warnings.append(f"Missing icon path: {icon_path}")

        music_path = Path(str(cfg.get("music", {}).get("path", "")))
        if str(music_path) and not music_path.exists():
            warnings.append(f"Missing music path: {music_path}")

    return errors, warnings
