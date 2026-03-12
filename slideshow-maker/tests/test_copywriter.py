from __future__ import annotations

import random

from slideshow_maker.copywriter import STYLES, pick_line, resolve_style


def test_resolve_style_falls_back_to_balanced():
    assert resolve_style("unknown") == "balanced"
    assert resolve_style(None) == "balanced"


def test_pick_line_returns_bucket_value_for_known_style():
    rng = random.Random(123)
    line = pick_line("bold", "hooks", rng, "fallback")
    assert isinstance(line, str)
    assert line != "fallback"


def test_styles_set_contains_expected_presets():
    assert {"safe", "balanced", "bold", "expert"}.issubset(STYLES)
