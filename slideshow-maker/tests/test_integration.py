from __future__ import annotations

import json
from pathlib import Path

from slideshow_maker.formats import get_format
from slideshow_maker.models import RunConfig, SourceConfig
from slideshow_maker.pipeline import GenerationPipeline
from slideshow_maker.sources.google_flow import GoogleFlowAutomationSource


def test_local_generation_outputs_expected_files(tmp_path: Path, sample_input_dir: Path):
    pipeline = GenerationPipeline(get_format("skincare_v1"))
    out_dir = tmp_path / "out"

    summaries = pipeline.generate(
        RunConfig(
            format_id="skincare_v1",
            count=2,
            input_dir=sample_input_dir,
            out_dir=out_dir,
            seed=5,
            source_mode="local",
        )
    )

    assert len(summaries) == 2
    for index in (1, 2):
        variation_dir = out_dir / f"variation_{index:03d}"
        assert (variation_dir / "manifest.json").exists()
        assert (variation_dir / "post.json").exists()
        slides = sorted((variation_dir / "slides").glob("slide_*.png"))
        assert 8 <= len(slides) <= 10


def test_flow_adapter_safe_fallback_marks_unresolved(tmp_path: Path):
    flow = GoogleFlowAutomationSource(config=SourceConfig(input_dir=tmp_path))

    result = flow.fetch(
        {
            "prompt": "test prompt",
            "output_path": str(tmp_path / "flow" / "image_1.png"),
        }
    )
    assert result.unresolved is True


def test_batch_run_reports_mixed_valid_invalid(tmp_path: Path, sample_input_dir: Path):
    pipeline = GenerationPipeline(get_format("skincare_v1"))

    valid_out = tmp_path / "valid"
    invalid_input = tmp_path / "bad_input"
    invalid_input.mkdir(parents=True, exist_ok=True)

    batch = pipeline.generate_batch(
        [
            RunConfig(
                format_id="skincare_v1",
                count=1,
                input_dir=sample_input_dir,
                out_dir=valid_out,
                seed=1,
                source_mode="local",
            ),
            RunConfig(
                format_id="skincare_v1",
                count=1,
                input_dir=invalid_input,
                out_dir=tmp_path / "invalid",
                seed=1,
                source_mode="local",
            ),
        ]
    )

    assert len(batch["generated"]) == 1
    assert len(batch["failed"]) == 1
    assert "Missing hook images" in batch["failed"][0]["error"]

    manifest = json.loads((valid_out / "variation_001" / "manifest.json").read_text())
    assert manifest["format_id"] == "skincare_v1"


def test_copy_draft_review_flow(tmp_path: Path, sample_input_dir: Path):
    pipeline = GenerationPipeline(get_format("skincare_v1"))
    out_dir = tmp_path / "out"
    draft_path = tmp_path / "copy.temp.json"

    draft_result = pipeline.draft_copy(
        RunConfig(
            format_id="skincare_v1",
            count=1,
            input_dir=sample_input_dir,
            out_dir=out_dir,
            seed=100,
            source_mode="local",
            copy_style="bold",
        ),
        draft_path=draft_path,
    )

    payload = draft_result["draft"]
    payload["variations"][0]["hook_line"] = "custom reviewed hook line"
    payload["variations"][0]["cta_line"] = "custom reviewed cta line"
    draft_path.write_text(json.dumps(payload, indent=2))

    pipeline.generate(
        RunConfig(
            format_id="skincare_v1",
            count=1,
            input_dir=sample_input_dir,
            out_dir=out_dir,
            seed=100,
            source_mode="local",
            copy_review_path=draft_path,
            copy_style="bold",
        )
    )

    manifest = json.loads((out_dir / "variation_001" / "manifest.json").read_text())
    assert manifest["slides"][0]["bottom_text"] == "custom reviewed hook line"
    cta_slide = next(s for s in manifest["slides"] if s["cta"])
    assert cta_slide["bottom_text"] == "custom reviewed cta line"


def test_copy_style_affects_auto_generated_copy(tmp_path: Path, sample_input_dir: Path):
    pipeline = GenerationPipeline(get_format("skincare_v1"))
    out_dir = tmp_path / "out"
    (sample_input_dir / "metadata.json").unlink()

    safe = pipeline.draft_copy(
        RunConfig(
            format_id="skincare_v1",
            count=1,
            input_dir=sample_input_dir,
            out_dir=out_dir / "safe",
            seed=222,
            source_mode="local",
            copy_style="safe",
        )
    )
    bold = pipeline.draft_copy(
        RunConfig(
            format_id="skincare_v1",
            count=1,
            input_dir=sample_input_dir,
            out_dir=out_dir / "bold",
            seed=222,
            source_mode="local",
            copy_style="bold",
        )
    )

    safe_hook = safe["draft"]["variations"][0]["hook_line"]
    bold_hook = bold["draft"]["variations"][0]["hook_line"]
    assert safe["draft"]["copy_style"] == "safe"
    assert bold["draft"]["copy_style"] == "bold"
    assert safe_hook != bold_hook
