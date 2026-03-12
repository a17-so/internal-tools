from __future__ import annotations

import json
from pathlib import Path

from slideshow_maker.errors import SourceError
from slideshow_maker.models import ImageAsset, SourceConfig
from slideshow_maker.sources.base import AssetInventory, ImageSource

_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


class LocalFolderSource(ImageSource):
    name = "local-folder"

    def __init__(self, config: SourceConfig) -> None:
        self.config = config
        self.input_dir = config.input_dir

    def load_inventory(self) -> AssetInventory:
        return AssetInventory(
            hooks=self._load_group("hook"),
            before=self._load_group("before"),
            after=self._load_group("after"),
            products=self._load_group("products"),
            scan_ui=self._load_group("scan_ui"),
        )

    def load_metadata(self) -> dict:
        metadata_path = self.input_dir / "metadata.json"
        if not metadata_path.exists():
            return {}
        try:
            return json.loads(metadata_path.read_text())
        except json.JSONDecodeError as exc:
            raise SourceError(f"Invalid metadata.json: {exc}") from exc

    def fetch(self, request: dict) -> ImageAsset:
        path = Path(request["path"])
        if not path.exists():
            raise SourceError(f"Asset does not exist: {path}")
        return ImageAsset(id=path.stem, path=path, source=self.name)

    def _load_group(self, folder: str) -> list[ImageAsset]:
        path = self.input_dir / folder
        if not path.exists() or not path.is_dir():
            return []
        assets: list[ImageAsset] = []
        for file in sorted(path.iterdir()):
            if file.suffix.lower() in _IMAGE_EXTENSIONS and file.is_file():
                assets.append(ImageAsset(id=file.stem, path=file, source=self.name))
        return assets
