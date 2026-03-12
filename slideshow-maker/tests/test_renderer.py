from __future__ import annotations

from pathlib import Path

from slideshow_maker.formats import get_format
from slideshow_maker.pipeline import GenerationPipeline
from slideshow_maker.renderer import Renderer


def test_overlay_bounds_stay_in_canvas(tmp_path: Path, sample_input_dir: Path):
    fmt = get_format("skincare_v1")
    pipeline = GenerationPipeline(fmt)

    from slideshow_maker.models import RunConfig

    out_dir = tmp_path / "out"
    pipeline.generate(
        RunConfig(
            format_id="skincare_v1",
            count=1,
            input_dir=sample_input_dir,
            out_dir=out_dir,
            seed=10,
            source_mode="local",
        )
    )

    layout_path = out_dir / "variation_001" / "debug" / "layout.json"
    import json

    layout = json.loads(layout_path.read_text())["layout"]
    theme = Renderer().theme
    for item in layout:
        rect = item.get("scan_overlay_rect")
        if rect:
            assert 0 <= rect["x"] <= theme.width
            assert 0 <= rect["y"] <= theme.height
            assert rect["x"] + rect["w"] <= theme.width
            assert rect["y"] + rect["h"] <= theme.height
