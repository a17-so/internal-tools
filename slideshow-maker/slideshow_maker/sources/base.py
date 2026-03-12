from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from slideshow_maker.models import ImageAsset


@dataclass
class AssetInventory:
    hooks: list[ImageAsset] = field(default_factory=list)
    before: list[ImageAsset] = field(default_factory=list)
    after: list[ImageAsset] = field(default_factory=list)
    products: list[ImageAsset] = field(default_factory=list)
    scan_ui: list[ImageAsset] = field(default_factory=list)


class ImageSource(ABC):
    name: str

    @abstractmethod
    def load_inventory(self) -> AssetInventory:
        raise NotImplementedError

    @abstractmethod
    def fetch(self, request: dict) -> ImageAsset:
        raise NotImplementedError
