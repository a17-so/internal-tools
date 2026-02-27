# Outreach Automation System — Full Build Plan
> This document is a complete specification for building an end-to-end outreach automation system. It is intended to be handed off to an AI coding agent (Codex) to implement in full. Every architectural decision is explained with reasoning so the agent understands not just *what* to build but *why*.

---

## 1. Context & Goal

The existing system has a Next.js frontend and a Python Flask backend. A virtual assistant (VA) currently handles all outreach manually: reading a leads spreadsheet, checking creator stats, submitting URLs to a web tool, copying generated scripts, and manually sending DMs and emails across Instagram, TikTok, and email.

The goal is to **fully eliminate the VA** by building an autonomous loop that:
- Reads raw leads from Google Sheets
- Uses creator tier provided in Raw Leads (`Macro`, `Micro`, `Submicro`, `Ambassador`)
- Calls the existing Flask `/scrape` endpoint to generate outreach templates
- Sends emails via Gmail API
- Sends Instagram DMs via Playwright browser automation
- Sends TikTok DMs via Playwright browser automation
- Marks each lead as processed in Google Sheets
- Logs all results to Firestore for dashboard visibility

---

## 2. Architecture Overview

### Why Everything Runs Locally on an M4 Air

The system runs entirely on a dedicated M4 Air Mac that is left on permanently. This decision was made for one critical reason: **residential IP address**.

Instagram and TikTok aggressively flag DMs sent from cloud data center IPs (AWS, GCP, etc.) because they are easy to identify as non-human. A residential IP — the home internet connection of the M4 Air — looks completely natural to both platforms. The accounts sending DMs already have history on this IP, further reducing flag risk.

Running locally also eliminates cloud compute costs entirely. The M4 Air is more than powerful enough to handle 6 concurrent browser sessions with zero strain.

### Why Firestore Is Still Used

Even though the system runs locally, Firestore is kept for two reasons:
1. **The dashboard** is hosted on Vercel and needs a cloud-accessible data source. It cannot read a local SQLite file.
2. **Firestore's free tier** covers the entire usage volume of this system at no cost.

Everything else that could run in the cloud (Cloud Run, Cloud Scheduler) is replaced with local equivalents (Python scripts, macOS launchd cron) to keep costs at approximately $0/month.

### Why Not Browserbase or Other Managed Browser Services

Browserbase was evaluated at ~$139/month for the required volume. Self-hosted Playwright on the M4 Air achieves the same result for free, with the added benefit of the residential IP. Browserbase's main value-add is managed stealth and proxies — both of which are unnecessary when running from a home IP on aged accounts.

### Why Not OpenClaw (For Now)

OpenClaw is an AI agent layer useful for dynamic browser interactions where the UI may change unpredictably. It is not needed for the initial build. Playwright with well-structured selectors handles all required browser interactions. OpenClaw can be added as a layer-2 upgrade later to handle UI changes automatically and to manage other automations on the same machine.

### Why Sequential Sending Per Lead (Not Parallel)

Each lead triggers email + IG DM + TikTok DM sequentially rather than simultaneously. Reasoning:
- Volume is low (~300 DMs/day total across all accounts) so time is not a constraint
- Sequential execution is simpler to build, debug, and maintain
- It reduces the risk of hitting rate limits by spacing out actions naturally
- Parallel execution would consume account quota faster with no meaningful benefit at this scale

---

## 3. Full System Flow

```
[macOS launchd — cron trigger every X hours]
         ↓
[orchestrator.py — main loop]
    Step 1: Read up to 100 unprocessed leads from Google Sheets
    Step 2: Validate `creator_tier` from the lead row
    Step 3: POST to Flask /scrape endpoint with URL + category + sender profile
    Step 4: Send email via Gmail API
    Step 5: Send Instagram DM via Playwright
    Step 6: Send TikTok DM via Playwright
    Step 7: Mark lead as "Processed" in Google Sheets
    Step 8: Write full job result to Firestore
         ↓
[Firestore — free tier]
    Stores job results, account pool state, daily counters
         ↓
[Vercel Dashboard — existing frontend, new /dashboard page]
    Reads Firestore in real time
    Displays account health, job feed, errors, stats
```

---

## 4. Creator Tier Source (Raw Leads)

The system uses creator tier from the spreadsheet as the source of truth in v1.

### Allowed Tier Values

| Tier |
|---|
| Macro |
| Micro |
| Submicro |
| Ambassador |

### How It Works

Each lead row includes `creator_tier`. The orchestrator validates it against the allowed set and passes it directly as `category` into `/scrape`.

### Validation Rules

- Missing `creator_tier` → mark row `failed_missing_tier`
- Invalid value → mark row `failed_invalid_tier`
- Valid value → continue outreach flow

### Why This v1 Approach

- Removes dependence on uncertain third-party TikTok view metrics
- Keeps categorization explicit and auditable in Sheets
- Reduces implementation risk and gets the full pipeline running faster

---

## 5. Flask `/scrape` Integration

The existing Flask backend already does the hardest work: scraping the TikTok bio for Instagram handle and email, generating tailored DM and email templates based on creator category and brand app, and logging to Google Sheets.

The automation does **not** interact with the frontend UI at all. It calls the REST API directly:

- **Endpoint:** `POST /scrape`
- **Input:** `{ creator_url, category, sender_profile }`
- **Output:** `{ dm_text, email_to, email_subject, email_body, ig_handle }`

This is the cleanest possible integration — the backend is unchanged, the automation simply acts as a programmatic client.

---

## 6. Account Pool & Rotation

### Why Rotation Is Needed

Each platform enforces daily DM limits per account. Sending too many DMs from a single account risks it being flagged, action-blocked, or banned. By rotating across multiple accounts, the system distributes volume safely.

### Account Sets

There are 3 complete sets of accounts:
- 3 Instagram sender accounts
- 3 TikTok sender accounts
- 3 email sender addresses (`@a17.so`)

### Safe Daily Limits Per Account

| Platform | Safe Daily DMs |
|---|---|
| Instagram | ~25-30 |
| TikTok | ~40-50 |
| Email | ~150 |

### How the Router Works

Before each send, the system checks Firestore for the next available account on that platform where:
- `status == "active"`
- `daily_sent < daily_limit`

It selects that account, increments its `daily_sent` counter, and proceeds. If all accounts for a platform are at their daily limit, the job is marked as `pending_tomorrow` and retried in the next cron run.

Daily counters reset automatically at midnight via a lightweight reset function that runs as part of the cron.

### Session Management

Each Instagram and TikTok account has a saved browser session (cookies) stored in Firestore or as a local encrypted file. The Playwright browser loads this session at the start of each run rather than logging in fresh. 

**This is critical.** Fresh logins from a new browser fingerprint every run is one of the top signals platforms use to detect automation. Persistent sessions look like a normal logged-in user returning to the site.

---

## 7. Gmail API Setup

### Why Gmail API and Not SMTP

The system uses `@a17.so` email addresses via Google Workspace. Gmail API with OAuth2 is the correct integration for sending from these accounts programmatically. SMTP is not recommended for Google Workspace accounts and basic password auth was deprecated by Google in March 2025.

### Setup Steps (One-Time)

1. Enable Gmail API in GCP Console for the existing project
2. Add `gmail.send` OAuth scope to existing service account (same one used for Sheets)
3. Each of the 3 `@a17.so` accounts performs a one-time OAuth authorization flow to grant send permissions
4. Refresh tokens stored in `.env` file (never committed to GitHub)

### Why This Is Low-Risk

Gmail API sends emails exactly as a human would from that account. The sending mechanism itself does not affect spam rates. Deliverability is determined by DNS records and sending reputation, not the API.

### Email Warm-Up

All 3 `@a17.so` accounts should be warmed up before hitting full automation volume. This means gradually increasing send volume over 2-3 weeks. Cold accounts jumping to 100+ emails/day immediately will trigger spam filters. Tools like Lemwarm or Instantly.ai can automate this warm-up process.

---

## 8. Playwright Browser Automation

### Instagram DM Flow

For each lead:
1. Load the saved session cookies for the selected sender account
2. Navigate to `instagram.com/{ig_handle}`
3. Wait for the profile page to load
4. Locate and click the "Message" button
5. Wait a randomized delay (human jitter — see below)
6. Type the `dm_text` at human-like speed (not instant paste)
7. Wait another randomized delay
8. Send the message
9. Close the session or navigate away

### TikTok DM Flow

Same pattern as Instagram:
1. Load saved session cookies for selected TikTok sender account
2. Navigate to `tiktok.com/@{handle}` (handle extracted from the lead URL)
3. Locate and click the message/DM button
4. Wait jitter delay
5. Type `dm_text` at human-like speed
6. Wait jitter delay
7. Send
8. Close

### Why the Same `dm_text` for Both Platforms

The `/scrape` endpoint returns one `dm_text`. The same script is sent on both Instagram and TikTok. This is intentional — the templates are already tailored by creator category (Macro/Micro/Submicro/Ambassador), which is the meaningful variation. Platform-specific copy is not required at this stage.

### Human Jitter — Why It Matters

Fixed timing intervals are one of the clearest bot signals. If every DM takes exactly 3.2 seconds, platforms detect the pattern quickly. The system introduces randomized delays at every step:
- Before clicking message button: random 1.5 – 4 seconds
- Between starting to type and finishing: human-speed keystroke simulation, not instant paste
- After sending, before closing: random 2 – 5 seconds
- Between successive DMs from the same account: random 3 – 8 minutes

These ranges should be configurable in `config.py` so they can be adjusted without touching core logic.

### Selector Strategy

Playwright selectors for the message button and text input should use text-based or semantic selectors where possible rather than brittle CSS class names. Instagram and TikTok update their UI regularly and class names change. Text-based selectors (e.g. a button containing the text "Message") are more resilient. Where class names must be used, they should be isolated in a single `selectors.py` file so updates require changing one place only.

---

## 9. Google Sheets Integration

### Reading Leads

The orchestrator reads up to 100 rows at a time from the "Raw Leads" sheet where the status column is not "Processed". It uses the existing Google Sheets service account credentials already in the project.

Required columns in v1:
- `creator_url`
- `creator_tier`
- `status`

### Marking Processed

After all three outreach channels complete successfully for a lead, the system updates that row's status column to "Processed". It does not delete rows — updating a status column is safer because it preserves the history and avoids row index shifting bugs that come with deletion.

### Error States

If any channel fails (email bounced, IG DM blocked, TikTok DM failed), the row is marked with the specific failure reason rather than "Processed". This surfaces on the dashboard and allows manual review without the lead being silently skipped.

---

## 10. Firestore Schema

### Collection: `accounts`

Stores the state of every sender account across all platforms. The account router reads and writes this collection on every send.

Fields per document:
- `platform` — "instagram", "tiktok", or "email"
- `handle` — the account username or email address
- `daily_sent` — integer, how many sends today
- `daily_limit` — integer, configured safe maximum
- `status` — "active", "cooling", or "flagged"
- `last_reset` — date string, when daily_sent was last reset to 0
- `session_data` — encrypted session cookie string (for IG and TikTok accounts)

### Collection: `jobs`

One document per lead processed. Written after all channels complete (or fail).

Fields per document:
- `lead_url` — the original TikTok URL
- `category` — Macro/Micro/Submicro/Ambassador
- `ig_handle` — extracted Instagram handle
- `email_to` — extracted email address
- `email_status` — "sent", "failed", or "skipped"
- `ig_status` — "sent", "failed", or "skipped"
- `tiktok_status` — "sent", "failed", or "skipped"
- `error` — error message if any channel failed
- `created_at` — timestamp
- `completed_at` — timestamp
- `sender_email` — which email account was used
- `sender_ig` — which IG account was used
- `sender_tiktok` — which TikTok account was used

### Collection: `config`

Single document storing system-wide configuration. Allows changing allowed tiers and limits without redeploying code.

Fields:
- `allowed_tiers` — `["Macro", "Micro", "Submicro", "Ambassador"]`
- `daily_limits` — `{ instagram: 25, tiktok: 40, email: 150 }`
- `jitter_ranges` — `{ min_between_dms: 180, max_between_dms: 480 }` (seconds)
- `batch_size` — how many leads to process per cron run (default 100)

---

## 11. Firestore Security Rules

The Firestore database should have rules that:
- Allow read-only access from the Vercel dashboard only for authenticated app users (Firebase Auth + client SDK)
- Deny all other access

Backend/local Python access should be controlled by IAM via service account roles (Admin SDK), not client security rules.

---

## 12. macOS launchd Cron Setup

The orchestrator is triggered by macOS launchd, the native Mac scheduler. This replaces GCP Cloud Scheduler entirely.

A `.plist` file is created in `/Library/LaunchDaemons/` that:
- Points to the Python orchestrator script
- Runs on a configured interval (e.g. every 4 hours)
- Logs stdout and stderr to a local log file
- Starts automatically on boot (no interactive login required)

This is entirely native to macOS — no third-party tools, no Docker, no cloud services required.

The M4 Air should have sleep disabled when plugged in (System Settings → Battery → disable sleep on power adapter) to ensure launchd triggers reliably.

---

## 13. Vercel Dashboard

A new `/dashboard` page added to the existing Next.js frontend on Vercel. The dashboard reads from Firestore in real time using the Firebase client SDK.

### Account Health Panel

Displays a card for each of the 9 sender accounts (3 IG + 3 TikTok + 3 email). Each card shows:
- Platform icon
- Handle/address
- Daily sent vs daily limit (e.g. "14 / 25")
- Status indicator: green (active), yellow (cooling), red (flagged)

### Live Job Feed

A table of the most recent 50 jobs showing:
- Lead URL
- Creator category
- Email status (✅ / ❌ / ⏭)
- IG DM status (✅ / ❌ / ⏭)
- TikTok DM status (✅ / ❌ / ⏭)
- Timestamp
- Error message on hover/expand if failed

### Stats Bar

Top-level numbers:
- Total messages sent today
- Total messages sent this week
- Success rate per platform (%)
- Leads remaining in queue

### Why Vercel and Not a Separate Dashboard Tool

The existing frontend is already on Vercel. Adding a `/dashboard` route is a minimal change — same codebase, same deployment, no new hosting. The team already knows where to go.

---

## 14. Repository Structure

```
outreach-automation/
├── orchestrator.py          # Main loop — reads leads, coordinates all steps
├── tier_resolver.py         # Validates/normalizes creator_tier from Raw Leads
├── scraper.py               # Calls Flask /scrape endpoint
├── email_sender.py          # Gmail API integration
├── ig_dm.py                 # Playwright Instagram DM automation
├── tiktok_dm.py             # Playwright TikTok DM automation
├── sheets_client.py         # Google Sheets read/write
├── firestore_client.py      # Firestore read/write for jobs + accounts
├── account_router.py        # Selects next healthy sender account
├── session_manager.py       # Loads/saves browser session cookies
├── selectors.py             # All Playwright CSS/text selectors in one place
├── config.py                # Loads settings from Firestore config collection
├── reset_counters.py        # Resets daily_sent to 0 at midnight
├── com.a17.outreach.daemon.plist   # macOS launchd cron config
├── requirements.txt         # All Python dependencies
├── .env                     # API keys and credentials — NEVER committed
└── .env.example             # Template showing required env vars, no real values
```

### Module Responsibilities

**orchestrator.py** — The entry point. Reads leads from Sheets in batches of up to 100. For each lead, validates tier, calls scraper, email_sender, ig_dm, tiktok_dm in sequence. Writes results to Firestore. Marks lead in Sheets.

**tier_resolver.py** — Takes `creator_tier` from Sheets, normalizes casing/spacing, validates allowed values, returns canonical category string.

**scraper.py** — Takes URL, category, and sender profile. Makes a POST request to the existing Flask `/scrape` endpoint. Returns the full response object.

**email_sender.py** — Takes email address, subject, body, and sender account. Sends via Gmail API. Returns success/failure status.

**ig_dm.py** — Takes IG handle, DM text, and sender account. Launches Playwright with saved session. Navigates to profile, sends DM with jitter. Returns success/failure.

**tiktok_dm.py** — Same pattern as ig_dm.py but for TikTok.

**sheets_client.py** — All Google Sheets operations: reading unprocessed leads, updating status column.

**firestore_client.py** — All Firestore operations: writing job results, reading/updating account pool, reading config.

**account_router.py** — Reads account pool from Firestore. Returns next available account for a given platform. Increments daily_sent counter.

**session_manager.py** — Handles loading session cookies from storage into Playwright browser context. Handles saving updated cookies after each session.

**selectors.py** — Single file containing all platform UI selectors. When Instagram or TikTok updates their UI, only this file needs to change.

**config.py** — Loads the config document from Firestore on startup. Makes all allowed tiers and limits available to other modules.

**reset_counters.py** — Lightweight script that sets all `daily_sent` values to 0 in the accounts collection. Run as a separate launchd job at midnight daily.

---

## 15. Error Handling Philosophy

### Per-Channel Failures

If email sending fails for a lead, the system still attempts IG DM and TikTok DM. Failures are isolated per channel. The job result in Firestore records exactly which channels succeeded and which failed.

### Retry Logic

Cloud Tasks is not being used (everything is local), so retry logic is implemented directly:
- Network errors (timeouts, 5xx from /scrape): retry up to 2 times with exponential backoff
- Google API transient failures (Sheets/Firestore/Gmail): retry up to 2 times with exponential backoff
- Platform sends (Instagram DM and TikTok DM): **no automatic retries**
- Platform blocks (Instagram action blocked, TikTok rate limited): mark account as "cooling", move to next account for subsequent leads
- Hard failures (account banned, invalid IG handle): mark as failed, log to Firestore, do not retry

### Dead Letter Handling

Jobs that fail all retry attempts are written to Firestore with `status: "dead"`. These surface prominently on the dashboard for manual review. The lead is NOT marked as Processed in Google Sheets so it can be retried in a future run.

### Logging

Every step logs to both:
- Local log file (captured by launchd, useful for debugging on the Mac)
- Firestore job document (visible on dashboard)

Log entries include timestamps, account used, action taken, and full error messages on failure.

---

## 16. Security Considerations

- `.env` file contains all credentials and is never committed to GitHub. `.env.example` is committed with placeholder values showing required variables.
- Google service account JSON key stored in `.env` or as a local file path referenced in `.env`
- Instagram and TikTok session cookies stored encrypted in Firestore or as local encrypted files
- Gmail OAuth refresh tokens stored in `.env`
- Firestore security rules prevent unauthorized access from outside the service account and Vercel frontend
- No credentials are ever logged

---

## 17. Development & Deployment Workflow

### Development (M4 Pro)

Build and test the entire system on the M4 Pro development machine. Each module can be tested independently before wiring into the orchestrator. Use a small test batch of leads (5-10) to validate the full loop end-to-end before deploying.

### Deployment (M4 Air)

1. `git clone` the repository onto the M4 Air
2. `pip install -r requirements.txt`
3. Copy `.env` file manually (never via git)
4. Install Playwright browsers: `playwright install chromium`
5. Install launchd plist: copy `com.a17.outreach.daemon.plist` to `/Library/LaunchDaemons/` and load it
6. Verify launchd trigger fires correctly on schedule
7. Monitor first few runs via dashboard and local logs

### Environment Variables Required

The `.env.example` file should document all of the following:
- `FLASK_SCRAPE_URL` — URL of the Flask /scrape endpoint
- `GOOGLE_SERVICE_ACCOUNT_JSON` — path to GCP service account key file
- `GOOGLE_SHEETS_ID` — ID of the Raw Leads spreadsheet
- `FIRESTORE_PROJECT_ID` — GCP project ID
- `GMAIL_ACCOUNT_1_REFRESH_TOKEN` — OAuth refresh token for first email account
- `GMAIL_ACCOUNT_2_REFRESH_TOKEN`
- `GMAIL_ACCOUNT_3_REFRESH_TOKEN`
- `IG_SESSION_ENCRYPTION_KEY` — key for encrypting stored session cookies
- `TIKTOK_SESSION_ENCRYPTION_KEY`

---

## 18. Future Upgrades (Post-Launch)

Once the base system is stable and running, the following can be added without changing the core architecture:

**OpenClaw Integration** — Replace raw Playwright calls with OpenClaw agent calls. OpenClaw handles UI changes automatically using AI-driven element detection, eliminating the need to update `selectors.py` when platforms change their UI.

**Human-Like Variation in Scripts** — Add slight variations to `dm_text` before sending (e.g. minor rephrasing, emoji variation) so messages don't appear templated at scale. This can be a simple Claude API call that lightly rewrites the template before each send.

**Warm-Up Automation** — Automate the account warm-up process for new sender accounts added to the pool.

**Additional Automation Jobs** — The launchd + Firestore job queue pattern is reusable for any other automation tasks. New automations push jobs to Firestore, the M4 Air picks them up and executes.

**Auto-Categorization (Optional Mode)** — Add a future optional mode that estimates creator tier by scraping last-N TikTok post view counts and computing average views.

**Smarter Categorization** — Incorporate engagement rate (likes + comments / views) in addition to raw view count for more accurate creator tiering.

---

## 19. Pre-Launch Checklist

Before running the system against real leads:

- [ ] Outreach tool updated so each Raw Leads row has required `creator_tier`
- [ ] All 3 email accounts warmed up (2-3 weeks gradual volume increase)
- [ ] Gmail API OAuth authorized for all 3 email accounts
- [ ] Instagram session cookies saved for all 3 IG accounts
- [ ] TikTok session cookies saved for all 3 TikTok accounts
- [ ] Firestore account pool populated with all 9 accounts and correct limits
- [ ] Firestore config document created with correct allowed tiers and limits
- [ ] End-to-end test run completed with 5 test leads
- [ ] Dashboard displaying correct data
- [ ] launchd cron verified firing on schedule on M4 Air
- [ ] M4 Air sleep disabled when plugged in
- [ ] `.env` file on M4 Air confirmed complete and correct

---

*End of specification.*
