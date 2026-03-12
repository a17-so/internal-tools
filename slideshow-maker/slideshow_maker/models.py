from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class RunConfig:
    format_id: str
    count: int
    input_dir: Path
    out_dir: Path
    seed: int | None = None
    source_mode: str = "local"
    copy_review_path: Path | None = None
    copy_style: str = "balanced"


@dataclass
class VariationPolicy:
    allow_product_reorder: bool = True


@dataclass
class SourceConfig:
    input_dir: Path
    profile_dir: Path | None = None
    flow_timeout_seconds: int = 60
    flow_retries: int = 2


@dataclass
class RenderTheme:
    width: int = 1080
    height: int = 1920
    font_size_title: int = 64
    font_size_body: int = 52
    font_size_score: int = 56
    box_padding: int = 24
    box_corner_radius: int = 28
    text_fill: str = "#111111"
    box_fill: str = "#FFFFFF"


@dataclass
class ImageAsset:
    id: str
    path: Path
    source: str
    unresolved: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SlideSpec:
    index: int
    role: str
    image: ImageAsset
    top_text: str = ""
    bottom_text: str = ""
    score_text: str = ""
    cta: bool = False
    scan_verdict: str = ""
    scan_score: str = ""
    scan_overlay: ImageAsset | None = None


@dataclass
class SlidePlan:
    format_id: str
    variation_index: int
    title: str
    caption: str
    slides: list[SlideSpec]
    music: str = "ADD_IN_APP"


@dataclass
class RenderedSlides:
    slide_paths: list[Path]
    debug: dict[str, Any] = field(default_factory=dict)
