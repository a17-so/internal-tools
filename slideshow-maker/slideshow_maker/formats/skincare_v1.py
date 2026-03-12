from __future__ import annotations

import random

from slideshow_maker.copywriter import pick_line, resolve_style
from slideshow_maker.errors import ValidationError
from slideshow_maker.formats.base import BaseFormat, BuildContext
from slideshow_maker.models import SlidePlan, SlideSpec


class SkincareFormatV1(BaseFormat):
    format_id = "skincare_v1"
    min_slides = 8
    max_slides = 10

    def build_copy_draft(self, context: BuildContext) -> dict:
        rng = random.Random(context.random_seed)
        metadata = context.metadata or {}
        style = resolve_style(context.copy_style)

        total_slides = rng.randint(self.min_slides, self.max_slides)
        product_count = total_slides - 3
        cta_index = self._pick_cta_slide_index(rng, total_slides)

        reviews = metadata.get("product_reviews", {})
        review_defaults = reviews.get("default", []) if isinstance(reviews, dict) else []

        products: list[dict] = []
        for i in range(1, product_count + 1):
            products.append(
                {
                    "slot": i,
                    "title": f"product {i}",
                    "review": _pick(
                        review_defaults,
                        rng,
                        default=pick_line(
                            style,
                            "reviews",
                            rng,
                            "this one made a huge difference for my skin texture",
                        ),
                    ),
                    "score_text": _score_text(rng),
                    "scan_verdict": rng.choice(["GOOD", "BAD"]),
                    "scan_score": str(rng.randint(40, 99)),
                }
            )

        return {
            "format_id": self.format_id,
            "variation_index": context.variation_index,
            "seed": context.random_seed,
            "copy_style": style,
            "total_slides": total_slides,
            "cta_slide_index": cta_index,
            "title": _pick(
                metadata.get("titles"),
                rng,
                default=pick_line(
                    style,
                    "titles",
                    rng,
                    "Sephora products that helped me get glass skin",
                ),
            ),
            "caption": _pick(
                metadata.get("captions"),
                rng,
                default=pick_line(
                    style,
                    "captions",
                    rng,
                    "honest routine breakdown + ratings",
                ),
            ),
            "hook_line": _pick(
                metadata.get("hooks"),
                rng,
                default=pick_line(
                    style,
                    "hooks",
                    rng,
                    "sephora products i would repurchase again",
                ),
            ),
            "before_line": _pick(
                metadata.get("before_lines"),
                rng,
                default=pick_line(
                    style,
                    "before",
                    rng,
                    "i thought it was impossible to fix my skin",
                ),
            ),
            "after_line": _pick(
                metadata.get("after_lines"),
                rng,
                default=pick_line(
                    style,
                    "after",
                    rng,
                    "the right skincare routine changed everything",
                ),
            ),
            "cta_line": _pick(
                metadata.get("cta_lines"),
                rng,
                default=pick_line(
                    style,
                    "cta",
                    rng,
                    "scan this in pretti before you buy",
                ),
            ),
            "products": products,
        }

    def build_plan(self, context: BuildContext) -> SlidePlan:
        rng = random.Random(context.random_seed)
        inventory = context.inventory
        self._validate_inventory(inventory)

        copy = context.approved_copy or self.build_copy_draft(context)
        total_slides = int(copy.get("total_slides", self.min_slides))
        product_count = total_slides - 3
        if product_count <= 0:
            raise ValidationError("Invalid copy draft: product count must be positive")

        if len(inventory.products) < product_count:
            raise ValidationError(
                f"Need at least {product_count} product images for this variation, got {len(inventory.products)}"
            )

        products = rng.sample(inventory.products, k=product_count)

        slides: list[SlideSpec] = [
            SlideSpec(
                index=1,
                role="hook",
                image=rng.choice(inventory.hooks),
                bottom_text=str(copy.get("hook_line", "")),
            ),
            SlideSpec(
                index=2,
                role="before",
                image=rng.choice(inventory.before),
                bottom_text=str(copy.get("before_line", "")),
            ),
            SlideSpec(
                index=3,
                role="after",
                image=rng.choice(inventory.after),
                bottom_text=str(copy.get("after_line", "")),
            ),
        ]

        copy_products = copy.get("products") if isinstance(copy.get("products"), list) else []
        for i, product_image in enumerate(products, start=1):
            slot_copy = copy_products[i - 1] if i - 1 < len(copy_products) else {}
            top_text = str(slot_copy.get("title") or _humanize_name(product_image.id))
            review_text = str(
                slot_copy.get("review")
                or f"{_humanize_name(product_image.id)} is part of my weekly routine and my skin loves it"
            )
            score_text = str(slot_copy.get("score_text") or _score_text(rng))
            scan_verdict = str(slot_copy.get("scan_verdict") or rng.choice(["GOOD", "BAD"]))
            scan_score = str(slot_copy.get("scan_score") or str(rng.randint(40, 99)))

            slides.append(
                SlideSpec(
                    index=i + 3,
                    role="product_review",
                    image=product_image,
                    top_text=top_text,
                    bottom_text=review_text,
                    score_text=score_text,
                    scan_verdict=scan_verdict,
                    scan_score=scan_score,
                )
            )

        cta_index = int(copy.get("cta_slide_index") or self._pick_cta_slide_index(rng, len(slides)))
        for slide in slides:
            if slide.index == cta_index:
                slide.cta = True
                slide.bottom_text = str(copy.get("cta_line") or "scan this in pretti before you buy")
                slide.role = "product_review_cta"
                if context.scan_overlays:
                    slide.scan_overlay = rng.choice(context.scan_overlays)
                break

        plan = SlidePlan(
            format_id=self.format_id,
            variation_index=context.variation_index,
            title=str(copy.get("title", "Sephora products that helped me get glass skin")),
            caption=str(copy.get("caption", "honest routine breakdown + ratings")),
            slides=slides,
        )
        self.validate_plan(plan)
        return plan

    def validate_plan(self, plan: SlidePlan) -> None:
        if len(plan.slides) < self.min_slides or len(plan.slides) > self.max_slides:
            raise ValidationError(
                f"{self.format_id} requires {self.min_slides}-{self.max_slides} slides, "
                f"got {len(plan.slides)}"
            )

        expected_roles = ["hook", "before", "after"]
        for idx, role in enumerate(expected_roles, start=1):
            if plan.slides[idx - 1].role != role:
                raise ValidationError(f"Slide {idx} must be '{role}'")

        cta_slides = [s for s in plan.slides if s.cta]
        if len(cta_slides) != 1:
            raise ValidationError("Exactly one CTA slide is required")

        cta = cta_slides[0]
        if cta.index <= 4:
            raise ValidationError("CTA slide must not be in intro slides 1-4")
        if cta.index == len(plan.slides):
            raise ValidationError("CTA slide must not be the last slide")
        if cta.index not in {5, 6, 7}:
            raise ValidationError("CTA slide index must be 5, 6, or 7")

        for i, slide in enumerate(plan.slides, start=1):
            if slide.index != i:
                raise ValidationError("Slide indexes must be contiguous and 1-based")

    def _validate_inventory(self, inventory) -> None:
        if not inventory.hooks:
            raise ValidationError("Missing hook images")
        if not inventory.before:
            raise ValidationError("Missing before images")
        if not inventory.after:
            raise ValidationError("Missing after images")
        if len(inventory.products) < 5:
            raise ValidationError("Need at least 5 product images")

    def _pick_cta_slide_index(self, rng: random.Random, total_slides: int) -> int:
        eligible = [idx for idx in (5, 6, 7) if idx < total_slides]
        if not eligible:
            raise ValidationError("No eligible CTA slide index available")
        return rng.choice(eligible)


def _pick(options, rng: random.Random, default: str) -> str:
    if isinstance(options, list) and options:
        return str(rng.choice(options))
    return default


def _humanize_name(identifier: str) -> str:
    return identifier.replace("_", " ").replace("-", " ").strip() or "product"


def _score_text(rng: random.Random) -> str:
    presets = ["10/10", "9.5/10", "13/10", "87/10", "25/10", "1/10", "9999/10"]
    return rng.choice(presets)
