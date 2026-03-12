from __future__ import annotations

from abc import ABC, abstractmethod

from slideshow_maker.models import SlidePlan


class BaseFormat(ABC):
    format_id: str
    min_slides: int
    max_slides: int

    @abstractmethod
    def build_plan(self, context: "BuildContext") -> SlidePlan:
        raise NotImplementedError

    @abstractmethod
    def validate_plan(self, plan: SlidePlan) -> None:
        raise NotImplementedError

    @abstractmethod
    def build_copy_draft(self, context: "BuildContext") -> dict:
        raise NotImplementedError


class BuildContext:
    def __init__(
        self,
        variation_index: int,
        random_seed: int,
        inventory: "AssetInventory",
        metadata: dict,
        scan_overlays: list,
        approved_copy: dict | None = None,
        copy_style: str = "balanced",
    ) -> None:
        self.variation_index = variation_index
        self.random_seed = random_seed
        self.inventory = inventory
        self.metadata = metadata
        self.scan_overlays = scan_overlays
        self.approved_copy = approved_copy or {}
        self.copy_style = copy_style
