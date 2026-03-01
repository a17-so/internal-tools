# Pretti Edit Maker

Automated short-form video generator for the Pretti app. Creates TikTok-style slideshow videos with hook text, app demo overlays, and background music.

## Setup

```bash
cd edit-maker
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

If the repo path changes and `pip` in `.venv` breaks, recreate the venv:
```bash
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Usage

### List available features

```bash
python main.py list
```

### Generate a single video

```bash
python main.py generate facial_features short_philtrum
```

Options:
- `--hook N` — use a specific hook by index
- `--dry-run` — print config without rendering

### Generate a batch of videos

```bash
python main.py batch facial_features short_philtrum -n 3
```

### One-command: generate + export uploader CSV

```bash
python main.py batch facial_features short_philtrum -n 5 \
  --export-csv ../tiktok-uploader/posts.csv \
  --account-id <CONNECTED_ACCOUNT_ID> \
  --hashtags "#pretti #makeup #fyp"
```

### Export uploader CSV from existing outputs

```bash
python main.py export-uploader-csv \
  --account-id <CONNECTED_ACCOUNT_ID> \
  --output-csv ../tiktok-uploader/posts.csv \
  --root-dir output \
  --hashtags "#pretti #makeup #fyp"
```

### Generate random videos across features

```bash
python generate_random.py        # 6 videos (default)
python generate_random.py -n 10  # 10 videos
```

### Audit hooks and assets

```bash
python main.py audit
```

### Enable verbose logging

```bash
python main.py -v generate facial_features short_philtrum
```

### Upload exported CSV with uploader CLI

```bash
cd ../tiktok-uploader
uploader upload:batch --csv ./posts.csv --root ../edit-maker/output --send-now
```

## Project Structure

```
edit-maker/
├── main.py              # CLI entry point
├── generator.py          # Core video generation logic
├── config.py             # All paths, sizes, and timing constants
├── hooks.json            # Feature definitions and hook text
├── generate_random.py    # Batch-generate random feature videos
├── cleanup_hooks.py      # Utility to clean hook text patterns
├── requirements.txt      # Python dependencies
├── assets/
│   ├── images/           # Feature image folders
│   ├── music/            # Background tracks
│   └── ui/               # Demo video and UI card
└── output/               # Generated videos (gitignored)
```

## Adding a New Feature

1. Create an image folder under `assets/images/<category>/<feature name>/`
2. Add an entry in `hooks.json` under `features.<category>.<feature_id>` with `folder` and `hooks` keys
3. Run `python main.py generate <category> <feature_id> --dry-run` to verify paths
4. Run `python main.py audit` to verify asset integrity before production generation
