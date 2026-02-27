from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from outreach_automation.settings import load_settings

REQUIRED_FIELDS = {"id", "platform", "handle", "status", "daily_sent", "daily_limit"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed Firestore accounts collection from JSON")
    parser.add_argument("--file", required=True, help="Path to accounts seed JSON")
    parser.add_argument("--dotenv-path", default=None)
    args = parser.parse_args()

    settings = load_settings(dotenv_path=args.dotenv_path)
    client = _build_client(settings.google_service_account_json, settings.firestore_project_id)

    payload = _load_seed(Path(args.file))
    db = client._db

    written = 0
    for record in payload:
        doc_id = str(record["id"])
        data = {k: v for k, v in record.items() if k != "id"}
        db.collection("accounts").document(doc_id).set(data, merge=True)
        written += 1

    print(f"seeded_accounts={written}")
    return 0


def _load_seed(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"seed file not found: {path}")
    data = json.loads(path.read_text())
    if not isinstance(data, list):
        raise ValueError("seed file must be a JSON array")
    out: list[dict[str, Any]] = []
    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"item {idx} is not an object")
        missing = REQUIRED_FIELDS - set(item.keys())
        if missing:
            raise ValueError(f"item {idx} missing required fields: {sorted(missing)}")
        out.append(item)
    return out


def _build_client(service_account_path: str | None, project_id: str) -> Any:
    from outreach_automation.firestore_client import FirestoreClient

    return FirestoreClient(service_account_path=service_account_path, project_id=project_id)


if __name__ == "__main__":
    raise SystemExit(main())
