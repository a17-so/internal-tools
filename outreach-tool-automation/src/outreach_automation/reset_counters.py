from __future__ import annotations

import argparse

from outreach_automation.firestore_client import FirestoreClient
from outreach_automation.settings import load_settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset daily account counters")
    parser.add_argument("--dotenv-path", type=str, default=None)
    args = parser.parse_args()

    settings = load_settings(dotenv_path=args.dotenv_path)
    client = FirestoreClient(
        service_account_path=settings.google_service_account_json,
        project_id=settings.firestore_project_id,
    )
    count = client.reset_daily_counters()
    print(f"reset_accounts={count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
