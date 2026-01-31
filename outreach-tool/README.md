
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
| H | Personalization | Custom notes for outreach |
| I | Sent From (Email) | Email address used to send |
| J | Sent From (TikTok) | TikTok account used |
| K | Sent From (Instagram) | Instagram account used |
| L | Email Thread ID | Gmail thread ID for tracking |

### Sheet Names by Category

- **Macros** - Creators with 100k+ followers
- **Micros** - Creators with 10k-100k followers
- **Submicros** - Creators with 1k-10k followers
- **Ambassadors** - Brand ambassadors
- **Theme Pages** - Theme page accounts
- **Raw Leads** - Unprocessed leads

---

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

---

## New Features (2026-01-30)

### Health Check Endpoint

Monitor service health with the `/health` endpoint:

```bash
curl http://localhost:8000/health
```

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2026-01-30T21:27:26-08:00",
  "checks": {
    "config": {"status": "healthy", "apps": ["pretti", "lifemaxx", "hardmaxx"]},
    "sheets_api": {"status": "healthy"},
    "gmail_api": {"status": "healthy"},
    "scraper": {"status": "healthy"}
  }
}
```

### Request Validation Endpoint

Debug configuration issues before running outreach with `/validate`:

```bash
curl -X POST http://localhost:8000/validate \
  -H "Content-Type: application/json" \
  -d '{"app": "hardmaxx", "sender_profile": "abhay", "category": "micro"}'
```

**Use Cases**:
- Verify sender profile exists before running outreach
- Debug configuration issues
- Test new sender profiles
- Validate category mappings

---

## Testing

### Local Testing

1. **Restart the Flask server** to pick up new code:
   ```bash
   # Stop current server (Ctrl+C), then:
   cd api
   python3 -m flask --app index run --host 0.0.0.0 --port 8000
   ```

2. **Run test script**:
   ```bash
   ./test_new_endpoints.sh
   ```

### Production Testing

After deployment, test the production endpoints:

```bash
# Health check
curl https://outreach-tool-api-544313478134.us-central1.run.app/health

# Validate request
curl -X POST https://outreach-tool-api-544313478134.us-central1.run.app/validate \
  -H "Content-Type: application/json" \
  -d '{"app": "hardmaxx", "sender_profile": "abhay"}'
```

---

## Quick Deploy

Use the deployment script:

```bash
./deploy.sh
```

---

## Troubleshooting

### Sender Profile Not Found

Use the `/validate` endpoint to see available profiles:

```bash
curl -X POST http://localhost:8000/validate \
  -H "Content-Type: application/json" \
  -d '{"app": "hardmaxx", "sender_profile": "invalid"}'
```

### Server Returns 404 for New Endpoints

**Cause**: Flask server hasn't reloaded with new code

**Solution**: Restart the Flask server (see Testing section above)

### Check Logs

**Local**:
```bash
tail -f api/debug.log
```

**Production**:
```bash
gcloud run logs read outreach-tool-api --region us-central1 --limit 50
```

---

## Available Sender Profiles

### hardmaxx
- `abhay`, `advaith`, `ethan`, `ekam`, `ryder`

### lifemaxx
- `abhay`, `advaith`, `ethan`

### pretti
- `abhay`, `ethan`

---

## API Reference

See [API_REFERENCE.md](API_REFERENCE.md) for complete endpoint documentation.
