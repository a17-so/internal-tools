# Gmail Follow-up Tool

Automatically follows up on emails in your Gmail Sent folder using Playwright.

## Setup

### 1. Install Dependencies

```bash
./setup.sh
```

This will:
- Install Python dependencies (Playwright, PyYAML)
- Install Playwright browser binaries

### 2. Launch Arc with Remote Debugging

Before running the tool, you need to launch Arc browser with remote debugging enabled:

```bash
./launch_arc_debug.sh
```

Or manually:
```bash
open -a Arc --args --remote-debugging-port=9222
```

**Optional: Local API for testing**

```bash
cd api
python3 -m flask --app index run --host 0.0.0.0 --port 8001
```

## Usage

### Option 1: Apple Shortcut (Simplest - Recommended)

1. **Make sure Arc is running with debugging**:
   ```bash
   ./launch_arc_debug.sh
   ```

2. **Import the shortcut**:
   - Double-click `shortcut/followup-tool.shortcut`, or
   - Open Shortcuts app → File → Import → Select the file

3. **Run it**: The shortcut will:
   - Run the follow-up script directly on your Mac
   - Use your Arc browser to automate Gmail
   - Show you the results

That's it! No API server, no deployment, just works locally.

#### Manual Shortcut Setup (if import fails)
1. Open the **Shortcuts** app and create a new shortcut.
2. Add a **Run Shell Script** action:
   ```bash
   cd /Users/adzter/internal-tools/followup-tool && python3 followup_gmail.py --profile pretti --arc
   ```
3. (Optional) Add **Show Result** underneath so the output pops up.
4. Save it as “Follow-up Tool” and trigger it from Spotlight, menu bar, or Siri.

Prefer to call the local API instead?
1. Add **Run Shell Script** with `./run_followup.sh --profile pretti`.
2. Or recreate the HTTP flow: “Choose from List” → “Dictionary” → “Get Contents of URL (POST http://localhost:8001/followup)” → “Show Result”.

### Option 2: Command Line

For local testing with your Arc browser:

1. Launch Arc with debugging:
   ```bash
   ./launch_arc_debug.sh
   ```

2. Start API server:
   ```bash
   export USE_ARC=true
   cd api
   python3 -m flask --app index run --host 0.0.0.0 --port 8001
   ```

3. Use the shell script:
   ```bash
   ./run_followup.sh --profile pretti
   ```

### Option 3: Direct Python Script

```bash
python3 followup_gmail.py --profile pretti
```

Options:
- `--profile`: Sender profile (pretti) - defaults to config default
- `--max-emails`: Maximum emails to process (default: None = all emails)
- `--dry-run`: Preview mode - don't actually send emails
- `--config`: Path to config.yaml (default: config.yaml in script directory)

## Cloud Run Deployment (Optional)

If you want the Shortcut to hit an always-on API instead of running locally:

1. Install/authenticate Google Cloud SDK:
   ```bash
   gcloud auth login
   gcloud config set project YOUR_PROJECT_ID
   ```
2. Deploy:
   ```bash
   gcloud run deploy followup-tool-api \
     --source /Users/adzter/internal-tools/followup-tool \
     --region us-central1 \
     --platform managed \
     --allow-unauthenticated \
     --timeout 600 \
     --concurrency 1 \
     --memory 2Gi \
     --cpu 2
   ```
3. Update your Shortcut (or any client) to POST to the new Cloud Run URL.

## Configuration

Edit `config.yaml` to configure sender profiles:

```yaml
profiles:
  pretti:
    gmail_sender: "abhay@a17.so"
    from_name: "Advaith"
    link_url: "https://apps.apple.com/us/app/pretti-ai-makeup-assistant/id6749188903"
    app_name: "Pretti"

default_profile: "pretti"
```

## How It Works

1. **Connects to Arc Browser**: Uses Chrome DevTools Protocol (CDP) to connect to your existing Arc browser instance
2. **Navigates to Gmail**: Opens Gmail and goes to the Sent folder
3. **Scans Emails**: Loads all sent emails (scrolls to load more if needed)
4. **Processes Each Email**:
   - Opens the email thread
   - Extracts the username from the original message (looks for "hey username," pattern)
   - Sends a follow-up reply with the personalized template
5. **Cycles Through All**: Processes all emails in your Sent folder
6. **Remembers Progress**: Every time a follow-up is sent we log the username + level in `followup_progress.json` so reruns skip people who already received level 3.

## API Endpoints

### POST `/followup`

Run the follow-up process.

**Request Body:**
```json
{
  "profile": "pretti",
  "max_emails": null,
  "dry_run": false
}
```

**Response:**
```json
{
  "ok": true,
  "message": "Follow-up process completed (dry_run=false)"
}
```

### GET `/health`

Health check endpoint.

## Troubleshooting

### "Failed to connect to Arc"
- Launch Arc with debugging every time: `./launch_arc_debug.sh` (or `open -a Arc --args --remote-debugging-port=9222`)
- Wait 5 seconds before running the tool
- Confirm Arc is listening: `lsof -i :9222`

### "Executable doesn't exist" / Playwright browser missing
```bash
python3 -m playwright install chromium
```
or simply run `./setup.sh` again.

### Quick Fix Checklist
- [ ] Arc browser is open and running with remote debugging
- [ ] Logged into Gmail inside Arc
- [ ] Playwright Chromium is installed
- [ ] You’re not rate-limited (try `--max-emails 5` first)

### Test Connection
```bash
./launch_arc_debug.sh
sleep 5
python3 followup_gmail.py --profile pretti --arc --max-emails 1 --dry-run
```

### Still stuck?
```bash
killall Arc 2>/dev/null || true
open -a Arc --args --remote-debugging-port=9222
sleep 5
lsof -i :9222
```
If the port is open but the script still fails, rerun `./setup.sh` to reinstall Playwright binaries.

## Notes

- The tool processes **ALL emails** by default (no filters)
- It uses your **actual Arc browser** (not Chromium)
- Make sure you're **logged into Gmail** in Arc before running
- The script will **navigate back to Sent folder** after each email to ensure reliability
