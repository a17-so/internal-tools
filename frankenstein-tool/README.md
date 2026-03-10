# Frankenstein Tool

Frankenstein Maker is a local pipeline for:
- importing manually collected hook URLs (from phone research)
- deduping/cooldown filtering them
- approving hooks for render
- composing final Everest creatives in two styles
- exporting uploader-compatible CSV files

## Important note

This tool is intended for creative production workflows. Respect each platform's terms, copyright rules, and originality policies. Use licensed/original assets where required.

## Install

```bash
cd /Users/rootb/Code/a17/internal-tools/frankenstein-maker
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

## Quickstart

```bash
fm init
fm audit

# 1) paste reel URLs from phone into a txt/csv file
# 2) import them
fm capture import --input-file data/hooks/manual_urls.txt

# finalize + review
fm capture finalize
fm hooks review

# dry-run render first
fm render --style both --count 4 --dry-run

# real render once approved hooks + assets exist
fm render --style both --count 10 --manifest data/manifests/everest_styles.json

# export uploader csv
fm export-csv --account-id YOUR_ACCOUNT_ID --output-csv output/reports/posts.csv
```

## CLI Commands

- `fm init`
- `fm capture import`
- `fm capture finalize`
- `fm hooks review`
- `fm render`
- `fm export-csv`
- `fm audit`

## Data files

- `data/hooks/captured.jsonl`
- `data/hooks/candidates.jsonl`
- `data/hooks/approved.jsonl`
- `data/manifests/everest_styles.json`

## Output

- `output/videos/*.mp4`
- `output/reports/*.csv`
- `output/reports/render_log.jsonl`
