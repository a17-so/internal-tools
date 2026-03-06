# Outreach Tool Automation

Lean local-first outreach runner for `regen`.
It pulls leads from Google Sheets, builds outreach content from local templates + SearchAPI, sends via TikTok/Instagram/Email, and records outcomes in Firestore.

## What Is Included (Essential Only)

- Runtime core: orchestrator, routing, senders, clients
- One template set: `regen`
- Manual operator commands (`run_once`, `stop_run`, lock reset, counter reset)
- Minimal ops scripts needed for local Chrome debug + Gmail token generation
- Tests for core logic

Removed: LaunchDaemon packaging and unused app templates.

## Project Layout

```text
outreach-tool-automation/
├── src/outreach_automation/
│   ├── run_once.py
│   ├── stop_run.py
│   ├── unlock_run_lock.py
│   ├── reset_counters.py
│   ├── seed_accounts.py
│   ├── orchestrator.py
│   ├── account_router.py
│   ├── clients/
│   │   ├── firestore_client.py
│   │   ├── sheets_client.py
│   │   └── local_scraper_client.py
│   ├── senders/
│   │   ├── tiktok_dm.py
│   │   ├── ig_dm.py
│   │   └── email_sender.py
│   ├── templates/
│   │   └── regen.py
│   └── ...
├── ops/
│   ├── start_chrome_debug.sh
│   ├── get_gmail_refresh_token.py
│   └── accounts.seed.example.json
├── tests/
├── .env.example
└── README.md
```

## Setup

```bash
cd /Users/rootb/Code/a17/internal-tools/outreach-tool-automation
python3 -m venv .venv
source .venv/bin/activate
pip install -e "[dev]"
cp .env.example .env
```

## Google Auth (ADC)

```bash
gcloud auth application-default login \
  --scopes=https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/spreadsheets,https://www.googleapis.com/auth/drive

gcloud auth application-default set-quota-project outreach-tool-automation
```

If ADC expires, rerun both commands.

## Required `.env`

Minimum:

- `GOOGLE_SHEETS_ID`
- `FIRESTORE_PROJECT_ID`
- `SEARCHAPI_KEY`
- `GMAIL_CLIENT_ID`
- `GMAIL_CLIENT_SECRET`
- `GMAIL_ACCOUNT_1_EMAIL`
- `GMAIL_ACCOUNT_1_REFRESH_TOKEN`

Important behavior controls:

- `SENDER_PROFILE`
- `EMAIL_SENDER_HANDLE`
- `INSTAGRAM_SENDER_HANDLE`
- `TIKTOK_SENDER_HANDLE`
- `STRICT_SENDER_PINNING=true` (recommended)
- `EMAIL_RECIPIENT_BLOCKLIST`
- `TIKTOK_ATTACH_MODE=true`
- `TIKTOK_ATTACH_AUTO_START=true`
- `TIKTOK_CDP_URL=http://127.0.0.1:9222`

## Firestore Collections

- `accounts`: sender accounts + daily limits + status
- `jobs`: per-lead execution records
- `locks`: run lock (`locks/orchestrator`)

Seed accounts:

```bash
cp ops/accounts.seed.example.json ops/accounts.seed.json
python -m outreach_automation.seed_accounts --file ops/accounts.seed.json
```

## Raw Leads Contract

Supports either:

1. Row format: `creator_url`, `creator_tier`, optional `status`
2. Matrix format: URL columns plus paired `<header> Tier` columns

Allowed tiers:

- `Macro`
- `Micro`
- `Submicro`
- `Ambassador`
- `Themepage`

## Run Commands

Dry run:

```bash
python -m outreach_automation.run_once --dry-run --max-leads 10 --verbose-summary
```

Live:

```bash
python -m outreach_automation.run_once --live --max-leads 30 --verbose-summary
```

Channel-specific:

```bash
python -m outreach_automation.run_once --live --channels tiktok --max-leads 10 --ignore-dedupe
python -m outreach_automation.run_once --live --channels instagram,email --max-leads 10
```

## Stop / Recovery

Stop active run:

```bash
python -m outreach_automation.stop_run
```

Force stop stuck process:

```bash
python -m outreach_automation.stop_run --force
```

Clear stale lock:

```bash
python -m outreach_automation.unlock_run_lock
```

Reset daily counters:

```bash
python -m outreach_automation.reset_counters
```

## Current Runtime Behavior

- Per-lead channel order: `TikTok -> Instagram -> Email`
- URL cell is cleared after each attempted lead
- Lead becomes `Processed` when at least one channel sends successfully
- End-of-run prints failed TikTok links
- End-of-run prints tracking-append failures (if any)
- Email has blocklist + duplicate-recipient suppression
- DM pacing uses jittered waits (non-fixed cadence)

## Troubleshooting

`403 insufficient authentication scopes`:
- Re-run ADC login with Sheets + Drive scopes.

`Run lock already held`:
- Use `stop_run`, then `unlock_run_lock` if needed.

No IG/TikTok tabs open:
- Lead may be deduped/skipped or no active account available.
- Re-run with `--verbose-summary`.

TikTok attach mode not connecting:
- Ensure debugger is reachable at `TIKTOK_CDP_URL` or leave auto-start enabled.

## Dev Quality Check

```bash
make check
```

This runs Ruff, MyPy, and pytest.
