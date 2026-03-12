from __future__ import annotations

import json
import random
from dataclasses import asdict
from pathlib import Path

from slideshow_maker.errors import ValidationError
from slideshow_maker.exporter import Exporter
from slideshow_maker.formats.base import BuildContext
from slideshow_maker.models import ImageAsset, RunConfig, SourceConfig
from slideshow_maker.renderer import Renderer
from slideshow_maker.sources.google_flow import GoogleFlowAutomationSource
from slideshow_maker.sources.local_folder import LocalFolderSource


class GenerationPipeline:
    def __init__(self, fmt, renderer: Renderer | None = None, exporter: Exporter | None = None) -> None:
        self.fmt = fmt
        self.renderer = renderer or Renderer()
        self.exporter = exporter or Exporter()

    def generate(self, config: RunConfig) -> list[dict]:
        inventory, metadata, flow = self._load_inputs(config)
        copy_map = self._load_copy_review(config.copy_review_path) if config.copy_review_path else {}

        base_seed = config.seed if config.seed is not None else random.randint(1, 1_000_000_000)
        summaries: list[dict] = []

        for i in range(1, config.count + 1):
            variation_seed = base_seed + i
            approved_copy = copy_map.get(i)
            context = BuildContext(
                variation_index=i,
                random_seed=variation_seed,
                inventory=inventory,
                metadata=metadata,
                scan_overlays=inventory.scan_ui,
                approved_copy=approved_copy,
                copy_style=config.copy_style,
            )
            plan = self.fmt.build_plan(context)
            self.fmt.validate_plan(plan)

            variation_dir = config.out_dir / f"variation_{i:03d}"
            slides_dir = variation_dir / "slides"
            rendered = self.renderer.render(plan, slides_dir)
            self.exporter.export(variation_dir, plan, rendered)

            summaries.append(
                {
                    "variation": i,
                    "seed": variation_seed,
                    "slide_count": len(plan.slides),
                    "title": plan.title,
                    "caption": plan.caption,
                    "out_dir": str(variation_dir),
                    "flow_enabled": flow is not None,
                    "copy_source": "reviewed_json" if approved_copy else "auto_generated",
                }
            )
        return summaries

    def draft_copy(self, config: RunConfig, draft_path: Path | None = None) -> dict:
        inventory, metadata, _ = self._load_inputs(config)

        base_seed = config.seed if config.seed is not None else random.randint(1, 1_000_000_000)
        variations: list[dict] = []

        for i in range(1, config.count + 1):
            variation_seed = base_seed + i
            context = BuildContext(
                variation_index=i,
                random_seed=variation_seed,
                inventory=inventory,
                metadata=metadata,
                scan_overlays=inventory.scan_ui,
                copy_style=config.copy_style,
            )
            variations.append(self.fmt.build_copy_draft(context))

        draft = {
            "format_id": config.format_id,
            "count": config.count,
            "base_seed": base_seed,
            "copy_style": config.copy_style,
            "variations": variations,
            "instructions": "Edit copy fields, keep total_slides and cta_slide_index valid. Then pass this file to --copy-review.",
        }

        target = draft_path or (config.out_dir / "copy_draft.temp.json")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(draft, indent=2))
        return {"path": str(target), "draft": draft}

    def generate_batch(self, configs: list[RunConfig]) -> dict:
        generated: list[dict] = []
        failed: list[dict] = []
        for cfg in configs:
            try:
                summaries = self.generate(cfg)
                generated.append(
                    {
                        "format_id": cfg.format_id,
                        "count": cfg.count,
                        "out_dir": str(cfg.out_dir),
                        "variations": summaries,
                    }
                )
            except Exception as exc:
                failed.append(
                    {
                        "format_id": cfg.format_id,
                        "count": cfg.count,
                        "out_dir": str(cfg.out_dir),
                        "error": str(exc),
                    }
                )
        return {"generated": generated, "failed": failed}

    def preview(self, seed: int = 42) -> dict:
        inventory = self._mock_inventory()
        context = BuildContext(
            variation_index=1,
            random_seed=seed,
            inventory=inventory,
            metadata={},
            scan_overlays=inventory.scan_ui,
            copy_style="balanced",
        )
        plan = self.fmt.build_plan(context)
        self.fmt.validate_plan(plan)
        return {
            "format_id": plan.format_id,
            "slide_count": len(plan.slides),
            "title": plan.title,
            "caption": plan.caption,
            "slides": [asdict(slide) for slide in plan.slides],
        }

    def _load_inputs(self, config: RunConfig):
        source_cfg = SourceConfig(input_dir=config.input_dir)
        local = LocalFolderSource(source_cfg)
        inventory = local.load_inventory()
        metadata = local.load_metadata()

        flow = None
        if config.source_mode in {"flow", "local+flow"}:
            flow_cfg = SourceConfig(
                input_dir=config.input_dir,
                profile_dir=config.input_dir / ".flow_profile",
                flow_timeout_seconds=60,
                flow_retries=2,
            )
            flow = GoogleFlowAutomationSource(flow_cfg)
            inventory = self._top_up_inventory_with_flow(inventory, flow, config.out_dir)
        return inventory, metadata, flow

    def _load_copy_review(self, path: Path) -> dict[int, dict]:
        if not path.exists():
            raise ValidationError(f"Copy review file does not exist: {path}")

        payload = json.loads(path.read_text())
        variations = payload.get("variations") if isinstance(payload, dict) else None
        if not isinstance(variations, list):
            raise ValidationError("Copy review JSON must include 'variations' array")

        copy_map: dict[int, dict] = {}
        for entry in variations:
            if not isinstance(entry, dict):
                continue
            idx = entry.get("variation_index")
            if isinstance(idx, int) and idx > 0:
                copy_map[idx] = entry
        return copy_map

    def _mock_inventory(self):
        def fake_asset(group: str, idx: int) -> ImageAsset:
            return ImageAsset(id=f"{group}_{idx}", path=Path(f"/{group}_{idx}.png"), source="mock")

        from slideshow_maker.sources.base import AssetInventory

        return AssetInventory(
            hooks=[fake_asset("hook", 1), fake_asset("hook", 2)],
            before=[fake_asset("before", 1)],
            after=[fake_asset("after", 1)],
            products=[fake_asset("product", i) for i in range(1, 10)],
            scan_ui=[fake_asset("scan", i) for i in range(1, 6)],
        )

    def _top_up_inventory_with_flow(self, inventory, flow: GoogleFlowAutomationSource, out_dir: Path):
        targets = {
            "hooks": 1,
            "before": 1,
            "after": 1,
            "products": 5,
        }
        flow_cache = out_dir / "_flow_cache"
        flow_cache.mkdir(parents=True, exist_ok=True)

        for group, minimum in targets.items():
            current: list[ImageAsset] = getattr(inventory, group)
            missing = max(0, minimum - len(current))
            for m in range(1, missing + 1):
                prompt = f"skincare {group} image for tiktok slideshow"
                output_path = flow_cache / f"{group}_{len(current) + m}.png"
                asset = flow.fetch({"prompt": prompt, "output_path": str(output_path)})
                current.append(asset)
        return inventory


def validate_format_definition(fmt) -> dict:
    if not getattr(fmt, "format_id", None):
        raise ValidationError("Format missing format_id")
    if getattr(fmt, "min_slides", 0) <= 0:
        raise ValidationError("Format min_slides must be positive")
    if getattr(fmt, "max_slides", 0) < getattr(fmt, "min_slides", 0):
        raise ValidationError("Format max_slides must be >= min_slides")
    return {
        "format_id": fmt.format_id,
        "min_slides": fmt.min_slides,
        "max_slides": fmt.max_slides,
    }
