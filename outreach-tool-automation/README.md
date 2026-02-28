# Outreach Tool Automation

Local-first outreach backend that processes Raw Leads and sends email/IG/TikTok outreach.

## v1 Behavior

- Source of truth for category: `creator_tier` column from `Raw Leads`
- If tier is missing/invalid, fallback defaults to `Submicro` (`DEFAULT_CREATOR_TIER`)
- Supports two lead layouts:
  - Standard columns (`creator_url`, optional `creator_tier`, optional `status`)
  - Matrix mode (no explicit URL column): auto-selects the first column containing TikTok links and processes down that column
- Sequential execution per lead: Email -> Instagram -> TikTok
- No automatic retries for IG/TikTok sends
- Dry-run mode available for full pipeline validation without sending
- IG/TikTok live send requires pre-bootstrapped Playwright sessions

## Layout

```text
outreach-tool-automation/
├── src/outreach_automation/
│   ├── run_once.py
│   ├── orchestrator.py
│   ├── sheets_client.py
│   ├── scraper_client.py
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
- If Raw Leads headers differ, set:
  - `RAW_LEADS_URL_COLUMN`
  - `RAW_LEADS_TIER_COLUMN`
  - `RAW_LEADS_STATUS_COLUMN`

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

Run selected channels only (useful for testing):

```bash
python -m outreach_automation.run_once --live --channels instagram
python -m outreach_automation.run_once --live --channels email,tiktok
# force rerun same lead URL for testing
python -m outreach_automation.run_once --live --channels instagram --lead-row-index 15 --ignore-dedupe
```

Bootstrap IG/TikTok login sessions (one-time 2FA per active account):

```bash
python -m outreach_automation.login_bootstrap --platform all
# or limit to one active account
python -m outreach_automation.login_bootstrap --platform all --account-handle @regenhealth.app --account-handle @regenapp
```

TikTok attach mode (recommended when login attempts are blocked):

```bash
# 1) Start a separate Chrome debug profile (keeps your normal Chrome tabs intact)
./ops/start_chrome_debug.sh 9222

# 2) Enable attach mode in .env
# TIKTOK_ATTACH_MODE=true
# TIKTOK_CDP_URL=http://127.0.0.1:9222

# 3) Run tiktok-only send test
python -m outreach_automation.run_once --live --channels tiktok --lead-row-index 15 --ignore-dedupe
```

Notes for attach mode:
- Keep TikTok logged in on that Chrome instance.
- Do not run multiple outreach processes against the same attached Chrome at once.
- The automation will open/close only the tab it creates and will not close your attached Chrome browser.

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
