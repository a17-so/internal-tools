from __future__ import annotations

from slideshow_maker.errors import ValidationError
from slideshow_maker.formats.base import BuildContext
from slideshow_maker.formats.skincare_v1 import SkincareFormatV1
from slideshow_maker.pipeline import GenerationPipeline


def test_format_preview_has_valid_intro_and_cta_position():
    fmt = SkincareFormatV1()
    pipeline = GenerationPipeline(fmt)

    preview = pipeline.preview(seed=123)
    slides = preview["slides"]

    assert slides[0]["role"] == "hook"
    assert slides[1]["role"] == "before"
    assert slides[2]["role"] == "after"

    cta_slides = [s for s in slides if s["cta"]]
    assert len(cta_slides) == 1
    cta_idx = cta_slides[0]["index"]
    assert cta_idx in {5, 6, 7}
    assert cta_idx < len(slides)


def test_validation_fails_if_cta_is_last_slide():
    fmt = SkincareFormatV1()
    pipeline = GenerationPipeline(fmt)
    plan = fmt.build_plan(
        BuildContext(
            variation_index=1,
            random_seed=999,
            inventory=pipeline._mock_inventory(),
            metadata={},
            scan_overlays=[],
        )
    )
    plan.slides[-1].cta = True
    for slide in plan.slides[:-1]:
        slide.cta = False

    try:
        fmt.validate_plan(plan)
        assert False, "Expected ValidationError"
    except ValidationError as exc:
        assert "must not be the last slide" in str(exc)
