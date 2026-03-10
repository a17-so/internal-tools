from pathlib import Path

from PIL import Image

from fm.hooks.dedupe import dedupe_rows, hamming_distance


def test_hamming_distance():
    assert hamming_distance(0b1010, 0b1000) == 1


def test_dedupe_url_and_phash(tmp_path: Path):
    img1 = tmp_path / "a.jpg"
    img2 = tmp_path / "b.jpg"
    Image.new("RGB", (64, 64), (255, 0, 0)).save(img1)
    Image.new("RGB", (64, 64), (255, 0, 0)).save(img2)

    rows = [
        {"url": "https://x/a", "screenshot_path": str(img1)},
        {"url": "https://x/a", "screenshot_path": str(img1)},
        {"url": "https://x/b", "screenshot_path": str(img2)},
    ]

    unique, dropped = dedupe_rows(rows, phash_threshold=8)
    assert len(unique) == 1
    assert len(dropped) == 2
