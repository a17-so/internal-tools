# Raw Leads Shortcut Setup (v2)

Cloud Run API URL:
- `https://outreach-tool-api-vwoqhidyxa-uc.a.run.app/add_raw_leads`

Use this JSON payload in the Shortcuts `Get Contents of URL` action (`POST`, `JSON`):

```json
{
  "app": "regen",
  "url": "<Shortcut Input URL>",
  "category": "rawlead",
  "creator_tier": "<Macro|Micro|Submicro|Ambassador>",
  "sender_profile": "<ethan|abhay|advaith|ekam>"
}
```

Recommended shortcut flow:
1. Receive URL from share sheet (TikTok profile URL).
2. Choose from list: `Macro`, `Micro`, `Submicro`, `Ambassador`.
3. Choose from list: `ethan`, `abhay`, `advaith`, `ekam`.
4. POST JSON to the URL above.
5. Show result.

Required one-time GSheet permission:
- Share the Regen spreadsheet (`1pJbbD_o_duLKDTj_Nvtn0LDaEwuSCHK4o_9U4hRav74`) with:
  - `561024281586-compute@developer.gserviceaccount.com`
- Grant editor access.

How to create iCloud share link for cofounders:
1. Open Shortcuts app on iPhone/Mac.
2. Duplicate your raw-leads shortcut.
3. Confirm the POST URL and JSON payload fields above.
4. Tap Share -> `Copy iCloud Link`.
5. Send that iCloud link to cofounders.

Quick API test after sharing sheet:

```bash
curl -sS -X POST https://outreach-tool-api-vwoqhidyxa-uc.a.run.app/add_raw_leads \
  -H 'Content-Type: application/json' \
  -d '{"app":"regen","url":"https://www.tiktok.com/@example","category":"rawlead","creator_tier":"Micro","sender_profile":"ethan"}'
```
