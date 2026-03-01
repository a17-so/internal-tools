# Outreach Tool Automation

Local-first outreach backend that processes Raw Leads and sends email/IG/TikTok outreach.

## v1 Behavior

- Source of truth for category: `creator_tier` column from `Raw Leads`
- Supports two lead layouts:
  - Standard columns (`creator_url`, optional `creator_tier`, optional `status`)
  - Matrix mode (no explicit URL column): scans all TikTok URL columns and, when present, reads tier from the paired header `<date/name> Tier`
- Missing/invalid tiers are rejected with deterministic sheet statuses:
  - `failed_missing_tier`
  - `failed_invalid_tier`
- Sequential execution per lead: TikTok -> Instagram -> Email
- No automatic retries for IG/TikTok sends
- Dry-run mode available for full pipeline validation without sending
- IG/TikTok live send requires pre-bootstrapped Playwright sessions
- Scraper is local-only: in-process SearchAPI + local templates (no hosted `/scrape` dependency)

## Layout

```text
outreach-tool-automation/
├── src/outreach_automation/
│   ├── run_once.py
│   ├── orchestrator.py
│   ├── sheets_client.py
│   ├── local_scraper_client.py
│   ├── firestore_client.py
│   ├── account_router.py
│   ├── email_sender.py
│   ├── ig_dm.py
│   ├── tiktok_dm.py
│   ├── tier_resolver.py
│   └── status_mapper.py
├── tests/
└── ops/
```

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Create env file:

```bash
cp .env.example .env
```

Authentication options:
- Service account JSON (set `GOOGLE_SERVICE_ACCOUNT_JSON`)
- ADC keyless mode (leave `GOOGLE_SERVICE_ACCOUNT_JSON` blank and run `gcloud auth application-default login`)
- Quota project for ADC is auto-exported from `GOOGLE_CLOUD_QUOTA_PROJECT` (falls back to `FIRESTORE_PROJECT_ID`)
- If Raw Leads headers differ, set:
  - `RAW_LEADS_URL_COLUMN`
  - `RAW_LEADS_TIER_COLUMN`
  - `RAW_LEADS_STATUS_COLUMN`
- Optional sender pinning (recommended while you test with one operator account):
  - `EMAIL_SENDER_HANDLE=ethan@a17.so`
  - `INSTAGRAM_SENDER_HANDLE=@ethan.peps`
  - `TIKTOK_SENDER_HANDLE=@regen.app`

Scrape setup:
- Set `SEARCHAPI_KEY`; local scraper uses `LOCAL_TEMPLATES_DIR` scripts.
- Optional: set `OUTREACH_APPS_JSON` for sender-profile template overrides.
- Startup preflight validates required template files and local session directories for active sender accounts.

## Run

Dry-run (recommended first):

```bash
python -m outreach_automation.run_once --dry-run
```

Single row dry-run:

```bash
python -m outreach_automation.run_once --dry-run --lead-row-index 2
```

Live run:

```bash
python -m outreach_automation.run_once --live
```

Run exactly 30 leads (your current testing flow):

```bash
python -m outreach_automation.run_once --live --max-leads 30
```

Run selected channels only (useful for testing):

```bash
python -m outreach_automation.run_once --live --channels instagram
python -m outreach_automation.run_once --live --channels email,tiktok
# force rerun same lead URL for testing
python -m outreach_automation.run_once --live --channels instagram --lead-row-index 15 --ignore-dedupe
```

Stop an active run:

```bash
# press Ctrl+C in the same terminal
```

Clear a stale run lock if a prior process crashed:

```bash
python -m outreach_automation.unlock_run_lock
```

Current success policy:
- A lead is marked `Processed` if any channel (`email`, `instagram`, or `tiktok`) sends successfully.
- All enabled channels are still attempted per lead.

Bootstrap IG/TikTok login sessions (one-time 2FA per active account):

```bash
python -m outreach_automation.login_bootstrap --platform all
# or limit to one active account
python -m outreach_automation.login_bootstrap --platform all --account-handle @regenhealth.app --account-handle @regenapp
```

TikTok attach mode (recommended when login attempts are blocked):

```bash
# 1) Enable attach mode in .env
# TIKTOK_ATTACH_MODE=true
# TIKTOK_ATTACH_AUTO_START=true
# TIKTOK_CDP_URL=http://127.0.0.1:9222
# TIKTOK_MIN_SECONDS_BETWEEN_SENDS=90

# 2) Run tiktok-only send test
python -m outreach_automation.run_once --live --channels tiktok --lead-row-index 15 --ignore-dedupe
```

Notes for attach mode:
- With `TIKTOK_ATTACH_AUTO_START=true`, `run_once` auto-launches debug Chrome if CDP is down.
- Manual fallback (optional): `./ops/start_chrome_debug.sh 9222`
- Keep TikTok logged in on that Chrome instance.
- Do not run multiple outreach processes against the same attached Chrome at once.
- The automation will open/close only the tab it creates and will not close your attached Chrome browser.
- Live preflight fails fast if `TIKTOK_ATTACH_MODE=true` but `TIKTOK_CDP_URL` is unreachable.
- DM send pacing uses randomized delays (base + jitter), not fixed intervals:
  - `IG_MIN_SECONDS_BETWEEN_SENDS` + `IG_SEND_JITTER_SECONDS`
  - `TIKTOK_MIN_SECONDS_BETWEEN_SENDS` + `TIKTOK_SEND_JITTER_SECONDS`

Seed Firestore accounts:

```bash
cp ops/accounts.seed.example.json ops/accounts.seed.json
# edit handles/emails in ops/accounts.seed.json
python -m outreach_automation.seed_accounts --file ops/accounts.seed.json
```

Reset daily account counters:

```bash
python -m outreach_automation.reset_counters
```

## Quality

```bash
make check
make test
```

## Notes

- This project only modifies files inside `outreach-tool-automation`.
- Dashboard implementation is intentionally out of scope for v1.
- To temporarily stop live email sends, set `EMAIL_SEND_ENABLED=false` in `.env`.
