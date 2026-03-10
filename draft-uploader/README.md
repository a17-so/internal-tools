# DraftUploader

Next.js tool for uploading TikTok drafts with app-level username/password authentication, multi-user account isolation, and an admin portal.

## Features

- App authentication with username/password (`/api/auth/login`, `/api/auth/register`, `/api/auth/logout`, `/api/auth/me`)
- Persistent datastore for users, sessions, and TikTok account ownership (`data/store.json`)
- Per-user TikTok account isolation (regular users only see and use their own accounts)
- Multi-account linking via TikTok OAuth callback flow
- Admin portal with full system visibility and optional seeded internal TikTok accounts
- Staged upload pipeline with queueable batches and dispatch jobs (`/api/upload`)
- Video + slideshow post support (native TikTok photo flow with video fallback via ffmpeg)
- Bulk video and bulk slideshow staging from the compose interface with a client-side batch tray

## Environment

Copy `.env.example` to `.env.local` and configure:

- `NEXT_PUBLIC_APP_URL`
- `TIKTOK_CLIENT_KEY`
- `TIKTOK_CLIENT_SECRET`
- `TIKTOK_OAUTH_SCOPES`
- `ADMIN_USERNAME` (default: `A17`)
- `ADMIN_PASSWORD` (default: `A17ChangeMe!`)
- `INTERNAL_TIKTOK_ACCOUNTS` (optional JSON array for admin-seeded accounts)

Example internal account seed:

```json
[{"openId":"internal-open-id-1","displayName":"Internal Brand 1","accessToken":"token"}]
```

## Run

```bash
bun install
bun run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Portals

- Regular user portal: login/register, connect TikTok accounts, list own accounts, upload drafts to own accounts.
- Admin portal (`A17`): seeded on first run, can view and use all TikTok accounts across the system, plus predefined internal accounts.

## API Summary

- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`
- `GET /api/auth/tiktok` (link account)
- `GET /api/auth/callback` (OAuth callback)
- `GET /api/tiktok/accounts` (list visible accounts)
- `POST /api/upload` multipart `action=stage` (requires `postType`, media files, `tiktokAccountId`)
- `POST /api/upload` JSON `action=send-all` (creates batch, queues jobs, dispatches jobs)
- `POST /api/upload` JSON `action=dispatch` (dispatches an existing batch)
