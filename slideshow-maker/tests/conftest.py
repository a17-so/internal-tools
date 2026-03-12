from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image


@pytest.fixture
def sample_input_dir(tmp_path: Path) -> Path:
    root = tmp_path / "input"
    for folder in ("hook", "before", "after", "products", "scan_ui"):
        (root / folder).mkdir(parents=True, exist_ok=True)

    def make_img(path: Path, color: str) -> None:
        img = Image.new("RGB", (1200, 1800), color=color)
        img.save(path)

    make_img(root / "hook" / "hook_a.png", "#f2b3a0")
    make_img(root / "before" / "before_a.png", "#cccccc")
    make_img(root / "after" / "after_a.png", "#e6f7ff")

    for i in range(1, 8):
        make_img(root / "products" / f"product_{i}.png", "#d9e0f2")

    overlay = Image.new("RGBA", (500, 300), (255, 255, 255, 220))
    overlay.save(root / "scan_ui" / "scan_1.png")

    (root / "metadata.json").write_text(
        """
{
  "titles": ["ulta skincare products that helped me get glass skin"],
  "captions": ["my honest review list"],
  "hooks": ["sephora products i would repurchase again"],
  "before_lines": ["i thought glass skin was impossible"],
  "after_lines": ["anything is possible with the right skincare"],
  "cta_lines": ["scan this in pretti before buying"]
}
""".strip()
    )

    return root
