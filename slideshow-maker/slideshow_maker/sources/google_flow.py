from __future__ import annotations

import logging
import time
from pathlib import Path

from slideshow_maker.models import ImageAsset, SourceConfig
from slideshow_maker.sources.base import AssetInventory, ImageSource

logger = logging.getLogger(__name__)


class GoogleFlowAutomationSource(ImageSource):
    """Automation adapter for Google Flow-style browser workflows.

    This adapter is intentionally defensive: any failure returns unresolved assets
    rather than crashing the batch.
    """

    name = "google-flow"

    def __init__(self, config: SourceConfig) -> None:
        self.config = config
        self.profile_dir = config.profile_dir or (Path.home() / ".slideshow_maker" / "flow_profile")
        self.timeout = config.flow_timeout_seconds
        self.retries = config.flow_retries

    def load_inventory(self) -> AssetInventory:
        return AssetInventory()

    def fetch(self, request: dict) -> ImageAsset:
        prompt = request.get("prompt", "")
        output_path = Path(request["output_path"])
        output_path.parent.mkdir(parents=True, exist_ok=True)

        for attempt in range(1, self.retries + 1):
            try:
                result = self._run_flow_automation(prompt, output_path)
                if result:
                    return ImageAsset(
                        id=output_path.stem,
                        path=output_path,
                        source=self.name,
                        unresolved=False,
                        metadata={"prompt": prompt},
                    )
            except Exception as exc:  # pragma: no cover - defensive runtime path
                logger.warning("Flow automation attempt %s failed: %s", attempt, exc)
                time.sleep(1)

        return ImageAsset(
            id=output_path.stem,
            path=output_path,
            source=self.name,
            unresolved=True,
            metadata={"prompt": prompt, "error": "flow_automation_failed"},
        )

    def _run_flow_automation(self, prompt: str, output_path: Path) -> bool:
        """Placeholder automation entrypoint.

        Real implementations should:
        1) launch persistent browser context with self.profile_dir
        2) open Flow UI
        3) submit prompt
        4) wait for generation
        5) download image to output_path
        """
        if not prompt:
            return False
        # No-op fallback to keep behavior safe by default.
        return False
