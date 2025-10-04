

### Local Run Command

```
cd api
python3 -m flask --app index  run --host 0.0.0.0 --port 8000
```

**Note:** When running locally, the server will be accessible at `http://<your-local-ip>:8000/scrape`
- Check the terminal output for your current local IP address (e.g., `http://10.18.166.108:8000`)
- To test from your phone: make sure both devices are on the same WiFi network and update the shortcut URL to use your local IP


### Deployment Command

```

gcloud run deploy outreach-tool-api \                       
  --source /Users/abhay/Desktop/internal-tools/outreach-tool \
  --region=us-central1 \
  --platform=managed \
  --allow-unauthenticated \
  --timeout=60 \
  --concurrency=8 \
  --min-instances=1 \
  --set-secrets=GOOGLE_SERVICE_ACCOUNT_JSON=outreach-service-account:1 \
  --set-env-vars '^|^SHEETS_SPREADSHEET_ID=1xJtBo5T4hXTGu1kEMdr-GVa1QFLFdcQDtnX9JkOM-Ys|OUTREACH_APPS_JSON={"default":{"sheets_spreadsheet_id":"1xJtBo5T4hXTGu1kEMdr-GVa1QFLFdcQDtnX9JkOM-Ys","gmail_sender":"abhay@a17.so","delegated_user":"abhay@a17.so","link_url":"https://a17.so","from_name":"Abhay Chebium"},"pretti":{"sheets_spreadsheet_id":"1xJtBo5T4hXTGu1kEMdr-GVa1QFLFdcQDtnX9JkOM-Ys","gmail_sender":"abhay@a17.so","delegated_user":"abhay@a17.so","link_url":"https://a17.so","from_name":"Abhay Chebium"},"lifemaxx":{"sheets_spreadsheet_id":"1qY3dyWpGV1oTvP3a-bz7sN3uoVUWhDWHStkJdaMzSHs","gmail_sender":"advaith@a17.so","delegated_user":"advaith@a17.so","link_url":"https://a17.so","from_name":"Advaith Akella"},"rizzard":{"sheets_spreadsheet_id":"18yDsu35QZSmhGDiEaQLR26sBzNE--v5xi5TAdW8d7n4","gmail_sender":"ethan@a17.so","delegated_user":"ethan@a17.so","link_url":"https://a17.so","from_name":"Ethan Leonard"}}'

```