
### Google Sheets Schema

The outreach tool tracks creator outreach in Google Sheets with the following columns:

| Column | Field | Description |
|--------|-------|-------------|
| A | Name | Creator's display name |
| B | Instagram @ | Instagram handle (with hyperlink) |
| C | TikTok @ | TikTok handle (with hyperlink) |
| D | Email | Creator's email address |
| E | Average Views (Instagram) | Average Instagram post views |
| F | Average Views (TikTok) | Average TikTok video views |
| G | Status | Outreach status (Sent, Followup Sent, etc.) |
| H | Sent from Email | Email address used for outreach |
| I | Sent from IG @ | Instagram account used for DM |
| J | Sent from TT @ | TikTok account used for DM |
| K | Initial Outreach Date | Date/time when first outreach was sent |

### Local Run Command

```
cd api
python3 -m flask --app index  run --host 0.0.0.0 --port 8000
```

**Note:** When running locally, the server will be accessible at `http://<your-local-ip>:8000/scrape`
- Check the terminal output for your current local IP address (e.g., `http://10.18.166.108:8000`)
- To test from your phone: make sure both devices are on the same WiFi network and update the shortcut URL to use your local IP


### Deployment Command

Deploy to Google Cloud Run with the following command:

```bash
gcloud run deploy outreach-tool-api \
  --source . \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --timeout 60 \
  --concurrency 8 \
  --min-instances 1 \
  --set-secrets GOOGLE_SERVICE_ACCOUNT_JSON=outreach-service-account:latest
```

**Production URL**: https://outreach-tool-api-544313478134.us-central1.run.app

**Note**: 
- The deployment uses the `Dockerfile` in the root directory
- Environment configuration is loaded from `api/env.yaml`
- Service account credentials are mounted from Secret Manager (`outreach-service-account`)

```
