# Uploader V2

Multi-account, queue-based social uploader (TikTok implemented first) with a web UI and a CLI.

## What This Version Adds

- Internal app login (single-operator mode)
- Persistent connected TikTok accounts (not cookie-only)
- Account picker for uploads
- Draft-first upload mode with optional direct mode
- Video and slideshow (image set) post types
- Production fallback for TikTok slideshows (auto-fallback to generated video if native slideshow init fails)
- Bulk queue + batch dispatch with retries and throttling
- Upload history + queue management
- CLI support for single uploads and CSV batch ingestion
- Multi-provider architecture with TikTok + Instagram live (Instagram direct video/Reels)

## Tech

- Next.js App Router
- Prisma + SQLite
- Typed provider and queue services

## Setup

1. Install dependencies:

```bash
npm install
```

2. Configure env vars in `.env.local`:

```bash
NEXT_PUBLIC_APP_URL=http://localhost:3000

# TikTok app credentials
TIKTOK_CLIENT_KEY=...
TIKTOK_CLIENT_SECRET=...

# Internal app auth bootstrap user
APP_USER_EMAIL=you@company.com
APP_USER_PASSWORD=strong-password

# Token encryption secret (passphrase or base64 32-byte key)
ENCRYPTION_KEY=change-me

# Optional overrides
DATABASE_URL=file:./prisma/dev.db
UPLOADS_DIR=./uploads
QUEUE_GLOBAL_CONCURRENCY=5
QUEUE_ACCOUNT_CONCURRENCY=2
TIKTOK_SLIDESHOW_FALLBACK=video
SLIDESHOW_FALLBACK_FRAME_SECONDS=1.2
INSTAGRAM_GRAPH_VERSION=v24.0
```

3. Push schema to SQLite:

```bash
npm run db:push
```

4. Start the app:

```bash
npm run dev
```

5. Open [http://localhost:3000/login](http://localhost:3000/login)

## Web Workflow

1. Login with `APP_USER_EMAIL` / `APP_USER_PASSWORD`
2. Go to `Accounts` and click `Connect TikTok`
3. Authorize account(s)
   - TikTok: OAuth via `Connect TikTok`
   - Instagram: token connect via `Accounts` page (`instagram_user_id` + access token)
4. Go to `Compose`
5. Select account + mode + post type
6. Add posts to tray
7. Click `Send All`
8. Track progress in `Queue` and `History`

## CLI

CLI entrypoint is installed as `uploader` (bin maps to `src/bin/uploader.mjs`).

### Create API key

```bash
uploader auth:token:create \
  --email you@company.com \
  --password strong-password \
  --base-url http://localhost:3000
```

### List connected accounts

```bash
uploader accounts:list --provider tiktok
```

```bash
uploader accounts:connect-instagram \
  --instagram-user-id <IG_USER_ID> \
  --access-token <GRAPH_ACCESS_TOKEN>
```

### Queue one video

```bash
uploader upload:file \
  --account <connected_account_id> \
  --caption "Caption text #tags" \
  --file ../edit-maker/output/feature_001.mp4 \
  --mode draft
```

### Queue one slideshow

```bash
uploader upload:slideshow \
  --account <connected_account_id> \
  --caption "Slideshow caption" \
  --images ./a.jpg,./b.jpg,./c.jpg \
  --mode draft
```

### Queue a CSV batch

```bash
uploader upload:batch \
  --csv ./posts.csv \
  --root ../edit-maker/output \
  --send-now
```

### Job control

```bash
uploader jobs:list --status queued,running,failed
uploader jobs:retry --batch <batch_id>
uploader jobs:cancel --batch <batch_id>
```

## CSV Schema

Required columns:

- `file_type` (`video` or `slideshow`)
- `account_id`
- `mode` (`draft` or `direct`)
- `caption`

Video rows:

- `video_path`

Slideshow rows:

- `image_paths` (semicolon-separated ordered paths)

Optional columns:

- `platform` (defaults to `tiktok`)
- `client_ref`
- `schedule_at` (currently ignored)

Example:

```csv
file_type,account_id,mode,caption,video_path,image_paths,platform,client_ref
video,cmabc123,draft,"Post 1 #fyp",feature_001.mp4,,tiktok,job-001
slideshow,cmabc123,draft,"Post 2 #tips",,slide1.jpg;slide2.jpg;slide3.jpg,tiktok,job-002
```

## Notes

- Draft mode is default everywhere.
- Instagram currently supports `direct` video/Reels mode only in this uploader.
- Duplicate prevention uses idempotency hash (media + caption + mode + account).
- Retries are exponential backoff for retryable errors.
- Compose includes bulk caption tools (prepend/append/find-replace) and slideshow image reordering.
