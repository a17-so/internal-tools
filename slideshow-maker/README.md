# Slideshow Maker

Playwright-first pipeline for one-time TikTok historical backfill, format matching, virality scoring, and on-demand slideshow draft generation.

## What Is Implemented

- One-time historical backfill from public TikTok profile/post pages (Playwright, no login required)
- Asset corpus normalization from `assets/formats/*`
- Non-standard asset filename issue queue (`Group *.png`, `Frame *.png`, etc.)
- Auto mapping from crawled posts to slideshow formats with confidence gating
- Multi-account normalized proxy virality scoring
- On-demand draft generation with exploit/explore behavior
- Draft export manifest + uploader handoff row

## Project Layout

- `src/slideshow_machine/`
  - `cli.py`: command entrypoint
  - `crawler.py`: Playwright backfill
  - `assets_normalizer.py`: corpus normalization + optional OCR
  - `matcher.py`: post-format matching + QA gating
  - `scoring.py`: account-normalized proxy virality scoring
  - `drafts.py`: draft generation engine
  - `exporter.py`: draft export outputs
  - `db.py`: SQLite schema and helpers
- `tests/`: unit/integration tests
- `config/accounts.example.txt`: account input format
- `scripts/run_pipeline.sh`: end-to-end helper script

## Setup

1. Create venv and install:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
playwright install chromium
```

2. Initialize DB:

```bash
python -m slideshow_machine.cli --db ./data/slideshow_machine.db init-db
```

## Commands

### 1) Normalize asset corpus

```bash
python -m slideshow_machine.cli --db ./data/slideshow_machine.db ingest-assets --assets-root ./assets
```

Optional OCR (uses local `tesseract` if installed):

```bash
python -m slideshow_machine.cli --db ./data/slideshow_machine.db ingest-assets --assets-root ./assets --with-ocr
```

### 2) Backfill historical posts (one-time)

Create account list file (`@handle` or full URL, one per line), then run:

```bash
python -m slideshow_machine.cli --db ./data/slideshow_machine.db backfill --accounts-file ./config/accounts.example.txt
```

Optional:

- `--max-posts-per-account 200`
- `--headed` (browser visible)

### 3) Match posts to formats

```bash
python -m slideshow_machine.cli --db ./data/slideshow_machine.db match-posts --threshold 0.4
```

Lower threshold sends fewer items to QA; higher threshold is stricter.

### 4) Compute proxy virality scores

```bash
python -m slideshow_machine.cli --db ./data/slideshow_machine.db score-formats
```

Current public-metrics proxy formula:

- normalized views: 40%
- shares per 1k views: 30%
- comments per 1k views: 15%
- likes per 1k views: 15%

### 5) Generate drafts on demand

```bash
python -m slideshow_machine.cli --db ./data/slideshow_machine.db make-drafts \
  --topic "how to pick your perfect blush shade" \
  --count 5 \
  --account-scope "app.pretti,abhaychebium" \
  --explore-ratio 0.2
```

### 6) Export draft for review/handoff

```bash
python -m slideshow_machine.cli --db ./data/slideshow_machine.db export-draft \
  --draft-id d_xxxxxxxxxxxx \
  --output-root ./output
```

Writes:

- `output/<draft_id>/manifest.json`
- `output/<draft_id>/uploader_row.csv`

### 7) Status report

```bash
python -m slideshow_machine.cli --db ./data/slideshow_machine.db report
```

## Fast End-to-End Run

```bash
./scripts/run_pipeline.sh ./data/slideshow_machine.db ./config/accounts.example.txt "everyday clean girl makeup"
```

## Data Contracts

### Backfill input

```ts
type BackfillRequest = {
  accounts: string[];
  maxPostsPerAccount?: number;
};
```

### Historical post record

```ts
type HistoricalPost = {
  postId: string;
  postUrl: string;
  accountHandle: string;
  postedAt?: string;
  caption?: string;
  metrics: {
    views: number;
    likes: number;
    comments: number;
    shares: number;
  };
  crawlMeta: {
    collectedAt: string;
    source: "playwright_public";
    confidence: number;
  };
};
```

### Post-format match

```ts
type PostFormatMatch = {
  postId: string;
  formatName?: string;
  exampleId?: string;
  confidence: number;
  status: "auto_matched" | "needs_review" | "approved";
  reasons: string[];
};
```

### Draft request

```ts
type DraftRequest = {
  topic: string;
  count: number;
  objective: "qualified_virality_proxy";
  accountScope: string[];
};
```

## Notes and Limits

- TikTok markup changes can break scraping selectors. This crawler is checkpoint-safe via DB upserts and failure logs.
- Public-only backfill does not include completion/watch-time; add official TikTok API ingestion later for full optimization.
- Backfill is intended as one-time historical ingestion, then migrate to official API source.
