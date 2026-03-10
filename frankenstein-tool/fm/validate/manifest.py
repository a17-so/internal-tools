"""Manifest validation."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

REQUIRED_STYLES = {"calm_reclaim", "intense_smart"}


def load_manifest(path: Path) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_manifest_data(data: Dict) -> Tuple[List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []

    styles = data.get("styles")
    if not isinstance(styles, dict):
        errors.append("Missing styles object")
        return errors, warnings

    for style in REQUIRED_STYLES:
        if style not in styles:
            errors.append(f"Missing style: {style}")
            continue
        cfg = styles[style]
        if not isinstance(cfg, dict):
            errors.append(f"Style {style} must be object")
            continue

        overlays = cfg.get("overlays", {})
        if "top_bar" not in overlays:
            warnings.append(f"Style {style} missing overlays.top_bar")

        pools = cfg.get("clip_pools", [])
        if not isinstance(pools, list):
            errors.append(f"Style {style} clip_pools must be a list")

    timing = data.get("timing", {})
    if not isinstance(timing, dict):
        errors.append("Missing timing object")
    else:
        for key in ("hook_seconds_min", "hook_seconds_max"):
            if key not in timing:
                warnings.append(f"Missing timing.{key}")

    return errors, warnings


def validate_manifest_file(path: Path) -> Tuple[List[str], List[str], Dict]:
    if not path.exists():
        return [f"Manifest not found: {path}"], [], {}

    data = load_manifest(path)
    errors, warnings = validate_manifest_data(data)
    return errors, warnings, data
