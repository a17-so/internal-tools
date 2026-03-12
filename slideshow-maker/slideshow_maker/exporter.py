from __future__ import annotations

import json
from pathlib import Path

from slideshow_maker.models import RenderedSlides, SlidePlan


class Exporter:
    def export(self, out_dir: Path, plan: SlidePlan, rendered: RenderedSlides) -> None:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "debug").mkdir(parents=True, exist_ok=True)

        manifest = {
            "format_id": plan.format_id,
            "variation_index": plan.variation_index,
            "title": plan.title,
            "caption": plan.caption,
            "music": plan.music,
            "slides": [
                {
                    "index": slide.index,
                    "role": slide.role,
                    "image": str(slide.image.path),
                    "image_source": slide.image.source,
                    "image_unresolved": slide.image.unresolved,
                    "top_text": slide.top_text,
                    "bottom_text": slide.bottom_text,
                    "score_text": slide.score_text,
                    "cta": slide.cta,
                    "scan_verdict": slide.scan_verdict,
                    "scan_score": slide.scan_score,
                    "scan_overlay": str(slide.scan_overlay.path) if slide.scan_overlay else None,
                    "rendered_slide": str(rendered.slide_paths[slide.index - 1]),
                }
                for slide in plan.slides
            ],
        }
        (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

        post = {
            "title": plan.title,
            "caption": plan.caption,
            "music": {
                "mode": "add_in_app",
                "notes": "Music should be selected in TikTok app.",
            },
        }
        (out_dir / "post.json").write_text(json.dumps(post, indent=2))

        (out_dir / "debug" / "layout.json").write_text(json.dumps(rendered.debug, indent=2))
