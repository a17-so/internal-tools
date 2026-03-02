from pathlib import Path

from fm.export.uploader_csv import caption_from_filename, export_csv


def test_caption_from_filename():
    cap = caption_from_filename(Path("calm_reclaim_001.mp4"), hashtags="#everest")
    assert "#everest" in cap


def test_export_csv(tmp_path: Path):
    v = tmp_path / "a.mp4"
    v.write_bytes(b"x")
    csv_path = tmp_path / "out.csv"
    count = export_csv([v], csv_path, account_id="acct1", root_dir=tmp_path)
    assert count == 1
    assert csv_path.exists()
