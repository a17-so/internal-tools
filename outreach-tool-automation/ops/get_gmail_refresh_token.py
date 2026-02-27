#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Gmail OAuth refresh token")
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--client-secret", required=True)
    parser.add_argument("--account-email", required=True)
    args = parser.parse_args()

    client_config = {
        "installed": {
            "client_id": args.client_id,
            "client_secret": args.client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")

    print("account_email=", args.account_email)
    print("refresh_token=", creds.refresh_token)
    print("access_token=", creds.token)
    print("expiry=", creds.expiry)
    print("json=", json.dumps({"account_email": args.account_email, "refresh_token": creds.refresh_token}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
