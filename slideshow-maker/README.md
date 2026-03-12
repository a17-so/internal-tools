# Slideshow Maker

Python CLI for generating TikTok-ready slideshow image packs from reusable format classes.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

For Google Flow automation support:

```bash
pip install -e .[flow]
playwright install chromium
```

## Input Structure

```text
input/
  hook/
  before/
  after/
  products/
  scan_ui/            # optional, transparent PNG overlays for CTA scan
  metadata.json       # optional
```

`metadata.json` can provide optional copy pools:

```json
{
  "titles": ["Ultra skincare products that helped me get glass skin"],
  "captions": ["my honest picks from this month"],
  "hooks": ["sephora products i would repurchase again"],
  "before_lines": ["i thought it was impossible to get glass skin"],
  "after_lines": ["anything is possible with the right products"],
  "product_reviews": {
    "default": ["this one changed my skin barrier in a week"]
  },
  "cta_lines": ["scan this in pretti before you buy"]
}
```

## Commands

```bash
slideshow-maker validate-format --format skincare_v1
slideshow-maker preview --format skincare_v1 --variation-seed 42
slideshow-maker draft-copy --format skincare_v1 --count 10 --input ./input --out ./out --copy-style bold
slideshow-maker generate --format skincare_v1 --count 10 --input ./input --out ./out --copy-review ./out/copy_draft.temp.json --copy-style bold
slideshow-maker generate --format skincare_v1 --count 10 --input ./input --out ./out
```

Recommended workflow:
1. Run `draft-copy` and quickly edit `copy_draft.temp.json`.
2. Run `generate --copy-review <path>` to render slides with your approved copy.
3. Use `--copy-style safe|balanced|bold|expert` to set tone.

## Output

For each variation:

```text
out/
  variation_001/
    slides/slide_01.png ...
    manifest.json
    post.json
    debug/layout.json
```

## Google Flow Adapter Notes

The Google Flow adapter uses a persistent browser profile directory, so you can sign in once manually and reuse the authenticated session. If an automation step fails, unresolved assets are marked in `manifest.json` and batch generation continues.
