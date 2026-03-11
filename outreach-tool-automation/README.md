# Outreach Tool Automation

Local-first outreach automation for REGEN.

It reads Raw Leads from Google Sheets, generates scripts from local templates + SearchAPI, sends via TikTok/Instagram/Email, writes status back to Sheets, and records jobs/accounts/locks in Firestore.

## Scope

- This repo intentionally runs a local scraper path (no dependency on hosted `outreach-tool` API for automation runs).
- Production-like behavior is controlled by `.env` + Firestore account pool.
- Current supported automation tiers: `Macro`, `Micro`, `Submicro`, `Ambassador`, `Themepage`.
- `YT Creator` and `AI Influencer` are intentionally auto-skipped for now as `skipped_unsupported_tier`.

## Architecture

- Lead source: `Raw Leads` sheet (row format or matrix format)
- Scraper: `src/outreach_automation/clients/local_scraper_client.py`
- Orchestration: `src/outreach_automation/orchestrator.py`
- Routing: `src/outreach_automation/account_router.py`
- Senders:
  - TikTok: `src/outreach_automation/senders/tiktok_dm.py`
  - Instagram: `src/outreach_automation/senders/ig_dm.py`
  - Email: `src/outreach_automation/senders/email_sender.py`
- Persistence: Firestore collections `accounts`, `jobs`, `locks`

## Quick Start (New Device)

```bash
cd /Users/rootb/Code/a17/internal-tools/outreach-tool-automation
python3 -m venv .venv
source .venv/bin/activate
pip install -e "[dev]"
cp .env.example .env
```

### 1) Configure ADC (Google auth)

```bash
gcloud auth application-default login \
  --scopes=https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/spreadsheets,https://www.googleapis.com/auth/drive

gcloud auth application-default set-quota-project outreach-tool-automation
```

If a command fails with reauthentication/scopes errors, rerun both commands above.

### 2) Fill `.env`

Required minimum:

- `GOOGLE_SHEETS_ID`
- `FIRESTORE_PROJECT_ID`
- `SEARCHAPI_KEY`
- `GMAIL_CLIENT_ID`
- `GMAIL_CLIENT_SECRET`
- `GMAIL_ACCOUNT_1_EMAIL`
- `GMAIL_ACCOUNT_1_REFRESH_TOKEN`

Recommended routing defaults:

- `STRICT_SENDER_PINNING=true`
- Pin channels you want fixed sender on:
  - `EMAIL_SENDER_HANDLE=...`
  - `INSTAGRAM_SENDER_HANDLE=...`
- Leave TikTok unpinned if cycling:
  - `TIKTOK_SENDER_HANDLE=`
- TikTok cycling mode:
  - `TIKTOK_ATTACH_MODE=false`
  - `TIKTOK_CYCLING_MODE=per_account_session`

### 3) Seed Firestore accounts

```bash
cp ops/accounts.seed.example.json ops/accounts.seed.json
# edit ops/accounts.seed.json for your real handles/status/limits
python -m outreach_automation.seed_accounts --file ops/accounts.seed.json
```

### 4) Authenticate browser sessions (important)

Do not rely on automated TikTok login attempts when TikTok is rate-limiting login.
Use manual Chrome profile login and persist that profile dir.

Helper script:

```bash
./ops/open_platform_profile.sh tiktok @regenapp
./ops/open_platform_profile.sh instagram @ethan.peps
```

This opens normal Chrome with user-data-dir under:

- `sessions/tiktok/<handle>`
- `sessions/instagram/<handle>`

Log in + 2FA manually, then close that Chrome window. Credentials are stored in that profile dir.

Alternative bootstrap command:

```bash
python -m outreach_automation.login_bootstrap --platform instagram --account-handle @ethan.peps
python -m outreach_automation.login_bootstrap --platform tiktok --account-handle @regenapp
```

`login_bootstrap` now uses plain Chrome for TikTok auth and Playwright profile bootstrap for Instagram.
If TikTok shows login attempt limits, keep using the manual helper and wait cooldown windows.

### 5) Doctor check

```bash
python -m outreach_automation.doctor
```

Look for:

- `ok: true`
- account counts for each platform
- readiness matrix entries with `"ready": true`

## Operational Commands

### Run

Dry run:

```bash
python -m outreach_automation.run_once --dry-run --max-leads 10 --verbose-summary
```

Live run:

```bash
python -m outreach_automation.run_once --live --max-leads 30 --verbose-summary
```

Channel-specific:

```bash
python -m outreach_automation.run_once --live --channels tiktok --max-leads 5 --ignore-dedupe --verbose-summary
python -m outreach_automation.run_once --live --channels instagram,email --max-leads 10 --verbose-summary
```

### Stop / Recovery

Stop active run:

```bash
python -m outreach_automation.stop_run
```

Force stop:

```bash
python -m outreach_automation.stop_run --force
```

Unlock stale lock:

```bash
python -m outreach_automation.unlock_run_lock
```

Reset daily counters:

```bash
python -m outreach_automation.reset_counters
```

## Routing Behavior

- Routing algorithm: least-used eligible account.
- Eligibility:
  - Firestore `status=active`
  - `daily_sent < daily_limit`
  - readiness checks pass for that platform
- Strict pinning:
  - If `STRICT_SENDER_PINNING=true` and channel handle is pinned, no fallback to other handles for that channel.
- TikTok modes:
  - `per_account_session` (default/recommended for cycling)
  - `attach_single_browser` + `TIKTOK_ATTACH_MODE=true` (single-account/manual attach mode)

## Lead + Status Behavior

Per lead:

1. Tier validation
2. Scrape
3. Route accounts
4. Send order: TikTok -> Instagram -> Email
5. Write Firestore job
6. Update sheet status + clear URL cell

Status mapping:

- `Processed` if at least one channel sent, or all outcomes are success-equivalent skips.
- `pending_tomorrow` for account-availability constraints.
- Failure statuses map to `failed_<code>`.
- Deferred unsupported tiers map to `skipped_unsupported_tier`.

## Firestore Collections

- `accounts`: sender handles, status, daily counters, limits
- `jobs`: per-lead job records (channel outcomes + selected sender handles)
- `locks`: single run lock (`locks/orchestrator`)

## Raw Leads Contract

Supported formats:

1. Row format with headers: `creator_url`, `creator_tier`, optional `status`
2. Matrix format with URL columns and paired `<header> Tier` columns

Current automation tier support:

- `Macro`
- `Micro`
- `Submicro`
- `Ambassador`
- `Themepage`

Temporarily deferred (auto-skipped):

- `YT Creator`
- `AI Influencer`

## Reports and Logs

`run_once` prints:

- processed/failed/skipped counts
- per-lead summary when `--verbose-summary`
- `failed_tiktok_links`
- `tracking_append_failed_links`
- account usage selected/skips

JSON report path:

- `logs/run-reports/run-<timestamp>.json`

## Troubleshooting

`403 insufficient authentication scopes`:

- rerun ADC login with explicit scopes and set quota project.

`Reauthentication is needed`:

- rerun `gcloud auth application-default login`.

`Run lock already held`:

- `python -m outreach_automation.stop_run`
- if stale: `python -m outreach_automation.unlock_run_lock`

TikTok login shows `Maximum number of attempts reached`:

- stop automated login attempts
- use manual Chrome helper `./ops/open_platform_profile.sh tiktok @handle`
- wait cooldown window before retrying login

No IG/TikTok tab appears during run:

- likely dedupe/skip/no eligible account/readiness fail
- rerun with `--verbose-summary` and inspect `doctor` readiness matrix

## Development Quality

```bash
make check
```

Runs Ruff, MyPy, and pytest.
