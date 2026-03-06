# Outreach Tool Automation

Local-first outreach automation that reads Raw Leads from Google Sheets, generates scripts with a local scraper, sends outreach across TikTok/Instagram/Email, and writes execution state to Firestore.

This service is designed to run from one operator machine and does **not** require Cloud Run for scraping.

## Scope

- Source lead data: Google Sheet `Raw Leads`
- Channels: TikTok DM, Instagram DM, Email
- Persistence: Firestore (`jobs`, `accounts`, `locks`)
- Scraping: local SearchAPI + local template scripts
- Execution: single-run CLI (`run_once`) with lock protection

## Current Behavior

- Per-lead execution order: `TikTok -> Instagram -> Email`
- `creator_tier` is required for processing
- Lead URL cell is cleared after each attempted lead (success or failure)
- Lead is considered `Processed` when at least one channel sends successfully
- Failed TikTok links are printed at end of run
- Optional verbose per-lead summary via `--verbose-summary`
- Email safety:
  - recipient blocklist (`EMAIL_RECIPIENT_BLOCKLIST`)
  - duplicate-recipient suppression (skip email if that recipient was already emailed in a prior completed run)

## Repository Layout

```text
outreach-tool-automation/
├── src/outreach_automation/
│   ├── run_once.py
│   ├── stop_run.py
│   ├── unlock_run_lock.py
│   ├── orchestrator.py
│   ├── sheets_client.py
│   ├── local_scraper_client.py
│   ├── firestore_client.py
│   ├── account_router.py
│   ├── email_sender.py
│   ├── ig_dm.py
│   ├── tiktok_dm.py
│   ├── templates/
│   └── ...
├── tests/
├── ops/
├── .env.example
└── README.md
```

## Prerequisites

- Python `3.11+`
- Google Cloud project with Firestore enabled
- Access to target Google Sheet
- SearchAPI key
- Gmail OAuth client + refresh tokens for sender account(s)
- Playwright installed via project deps

## Setup

```bash
cd /Users/rootb/Code/a17/internal-tools/outreach-tool-automation
python3 -m venv .venv
source .venv/bin/activate
pip install -e "[dev]"
cp .env.example .env
```

## Authentication (ADC)

If not using a service account JSON, authenticate ADC with required scopes:

```bash
gcloud auth application-default login \
  --scopes=https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/spreadsheets,https://www.googleapis.com/auth/drive

gcloud auth application-default set-quota-project outreach-tool-automation
```

If ADC expires, rerun the same commands.

## Required Environment Variables

At minimum:

- `GOOGLE_SHEETS_ID`
- `FIRESTORE_PROJECT_ID`
- `SEARCHAPI_KEY`
- `GMAIL_CLIENT_ID`
- `GMAIL_CLIENT_SECRET`
- `GMAIL_ACCOUNT_1_EMAIL`
- `GMAIL_ACCOUNT_1_REFRESH_TOKEN`

Important runtime controls:

- `SENDER_PROFILE` (for template sender identity)
- `EMAIL_SENDER_HANDLE` / `INSTAGRAM_SENDER_HANDLE` / `TIKTOK_SENDER_HANDLE` (pin to one operator account)
- `EMAIL_RECIPIENT_BLOCKLIST` (comma-separated hard-block list)
- `TIKTOK_ATTACH_MODE=true`
- `TIKTOK_ATTACH_AUTO_START=true`
- `TIKTOK_CDP_URL=http://127.0.0.1:9222`

Humanized DM pacing (anti-pattern hardening):

- `IG_MIN_SECONDS_BETWEEN_SENDS`
- `IG_SEND_JITTER_SECONDS`
- `TIKTOK_MIN_SECONDS_BETWEEN_SENDS`
- `TIKTOK_SEND_JITTER_SECONDS`

## Firestore Data Model

### `accounts`

Expected fields per account:

- `id`
- `platform`: `email | instagram | tiktok`
- `handle`
- `status`: `active | cooling | flagged`
- `daily_sent`
- `daily_limit`
- optional: `cooldown_until`, `last_reset`

Seed from example:

```bash
cp ops/accounts.seed.example.json ops/accounts.seed.json
python -m outreach_automation.seed_accounts --file ops/accounts.seed.json
```

### `jobs`

Each lead attempt writes one job record with:

- lead URL + tier category
- per-channel status/error
- sender handles used
- timestamps
- dry-run marker

### `locks`

Run lock document:

- `locks/orchestrator`

## Raw Leads Sheet Contract

Supported layouts:

1. Standard row layout:
- `creator_url`
- `creator_tier`
- optional `status`

2. Matrix layout:
- URL columns by day/person
- paired tier columns named `<header> Tier`

Processing requirements:

- URL must be TikTok URL
- Tier must be one of: `Macro`, `Micro`, `Submicro`, `Ambassador`, `Themepage`

## Core Commands

### Dry run

```bash
python -m outreach_automation.run_once --dry-run --max-leads 10 --verbose-summary
```

### Live run

```bash
python -m outreach_automation.run_once --live --max-leads 30 --verbose-summary
```

### Live run with selected channels

```bash
python -m outreach_automation.run_once --live --channels tiktok --max-leads 10 --ignore-dedupe
python -m outreach_automation.run_once --live --channels instagram,email --max-leads 10
```

### Force rerun already-contacted URLs (testing only)

```bash
python -m outreach_automation.run_once --live --ignore-dedupe --lead-row-index 42 --channels tiktok --verbose-summary
```

## Stop / Recovery Commands

### Stop active run safely (from another terminal)

```bash
python -m outreach_automation.stop_run
```

If process is stuck in teardown:

```bash
python -m outreach_automation.stop_run --force
```

### Clear stale run lock

```bash
python -m outreach_automation.unlock_run_lock
```

### Reset daily counters

```bash
python -m outreach_automation.reset_counters
```

## TikTok Attach Mode

Attach mode is recommended for reliability when login automation is blocked.

Behavior:

- automation connects to local Chrome debugging endpoint
- opens a per-lead tab
- closes tab in `finally` even on failure
- retries once if DM thread is stuck loading before input appears

If debugger is down and auto-start is enabled, `run_once` launches debug Chrome automatically.

## Safety Controls

- Run lock prevents overlapping runs
- Sender-handle pinning prevents accidental routing to wrong account
- Email duplicate recipient suppression prevents repeated sends to same email across leads
- Recipient blocklist prevents known-bad targets
- Randomized send spacing avoids fixed-interval bot-like cadence

## Troubleshooting

### `insufficient authentication scopes` / Sheets 403
Re-auth ADC with Sheets + Drive scopes (see Authentication section).

### `Reauthentication is needed`
ADC token expired or invalidated. Re-run `gcloud auth application-default login`.

### `Run lock already held`
Another run is active or stale lock exists. Use `stop_run` and/or `unlock_run_lock`.

### No IG/TikTok tabs open
Common causes:

- lead skipped by dedupe
- tier missing (`failed_missing_tier`)
- account unavailable (`pending_tomorrow` with `no_*_account`)

Run with `--verbose-summary` to inspect exact per-lead reasons.

### TikTok DM thread loads forever
Patched with one reload retry and guaranteed tab cleanup. If persistent, run tiktok-only with verbose summary and inspect `tiktok_*` error codes.

## Development

Quality gates:

```bash
make check
make test
```

`make check` runs:

- Ruff
- MyPy (strict)
- Pytest

## Operational Notes

- Keep this automation isolated to `outreach-tool-automation` changes only.
- Do not share `.env` or OAuth secrets.
- Rotate credentials if exposed.
- For sharing with another operator:
  - share repo
  - share non-secret setup steps from this README
  - have them generate their own local `.env` and ADC auth
