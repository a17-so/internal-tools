from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta
from typing import Any

import firebase_admin  # type: ignore[import-untyped]
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from outreach_automation.models import Account, AccountStatus, JobRecord, Platform


class FirestoreClient:
    def __init__(self, service_account_path: str | None, project_id: str) -> None:
        if not firebase_admin._apps:
            if service_account_path:
                cred = credentials.Certificate(service_account_path)
            else:
                cred = credentials.ApplicationDefault()
            firebase_admin.initialize_app(cred, {"projectId": project_id})
        self._db = firestore.client()

    def write_job(self, job_id: str, record: JobRecord) -> None:
        payload = {
            **asdict(record),
            "created_at": record.created_at,
            "completed_at": record.completed_at,
        }
        self._db.collection("jobs").document(job_id).set(payload)

    def mark_dead_job(self, job_id: str, reason: str) -> None:
        self._db.collection("jobs").document(job_id).set(
            {
                "status": "dead",
                "error": reason,
                "completed_at": datetime.now(UTC),
            },
            merge=True,
        )

    def was_processed_url(self, lead_url: str) -> bool:
        query = (
            self._db.collection("jobs")
            .where(filter=FieldFilter("lead_url", "==", lead_url))
            .limit(20)
            .stream()
        )
        for doc in query:
            data = doc.to_dict() or {}
            if data.get("status") == "completed" and not bool(data.get("dry_run")):
                return True
        return False

    def acquire_run_lock(self, holder: str, ttl_seconds: int) -> bool:
        lock_ref = self._db.collection("locks").document("orchestrator")
        tx = self._db.transaction()

        @firestore.transactional  # type: ignore[untyped-decorator]
        def _acquire(transaction: Any) -> bool:
            snap = lock_ref.get(transaction=transaction)
            now = datetime.now(UTC)
            expires_at = now + timedelta(seconds=ttl_seconds)
            if not snap.exists:
                transaction.set(lock_ref, {"holder": holder, "expires_at": expires_at})
                return True
            data = snap.to_dict() or {}
            current_exp = data.get("expires_at")
            if current_exp is None or current_exp <= now:
                transaction.set(lock_ref, {"holder": holder, "expires_at": expires_at})
                return True
            return False

        return bool(_acquire(tx))

    def release_run_lock(self, holder: str) -> None:
        lock_ref = self._db.collection("locks").document("orchestrator")
        snap = lock_ref.get()
        if not snap.exists:
            return
        data = snap.to_dict() or {}
        if data.get("holder") == holder:
            lock_ref.delete()

    def next_account(self, platform: Platform) -> Account | None:
        candidates = sorted(
            self._active_account_docs(platform),
            key=lambda d: (d.to_dict() or {}).get("daily_sent", 0),
        )

        for doc in candidates:
            acc = self._doc_to_account(doc.id, doc.to_dict() or {})
            if acc.daily_sent >= acc.daily_limit:
                continue
            if self._try_increment_daily_sent(doc.id, acc.daily_sent):
                return acc
        return None

    def list_active_accounts(self, platform: Platform) -> list[Account]:
        docs = self._active_account_docs(platform)
        return [self._doc_to_account(doc.id, doc.to_dict() or {}) for doc in docs]

    def mark_account_cooling(self, account_id: str, cooldown_minutes: int = 60) -> None:
        until = datetime.now(UTC) + timedelta(minutes=cooldown_minutes)
        self._db.collection("accounts").document(account_id).set(
            {
                "status": AccountStatus.COOLING.value,
                "cooldown_until": until,
            },
            merge=True,
        )

    def reset_daily_counters(self) -> int:
        today = date.today().isoformat()
        docs = self._db.collection("accounts").stream()
        count = 0
        for doc in docs:
            self._db.collection("accounts").document(doc.id).set(
                {"daily_sent": 0, "last_reset": today}, merge=True
            )
            count += 1
        return count

    def _try_increment_daily_sent(self, account_id: str, expected_sent: int) -> bool:
        ref = self._db.collection("accounts").document(account_id)
        tx = self._db.transaction()

        @firestore.transactional  # type: ignore[untyped-decorator]
        def _incr(transaction: Any) -> bool:
            snap = ref.get(transaction=transaction)
            if not snap.exists:
                return False
            data = snap.to_dict() or {}
            current = int(data.get("daily_sent", 0))
            if current != expected_sent:
                return False
            transaction.update(ref, {"daily_sent": current + 1})
            return True

        return bool(_incr(tx))

    def _active_account_docs(self, platform: Platform) -> list[Any]:
        return list(
            self._db.collection("accounts")
            .where(filter=FieldFilter("platform", "==", platform.value))
            .where(filter=FieldFilter("status", "==", AccountStatus.ACTIVE.value))
            .stream()
        )

    @staticmethod
    def _doc_to_account(doc_id: str, data: dict[str, Any]) -> Account:
        cooldown_until = data.get("cooldown_until")
        parsed_cooldown = cooldown_until if isinstance(cooldown_until, datetime) else None
        return Account(
            id=doc_id,
            platform=Platform(str(data.get("platform", "email"))),
            handle=str(data.get("handle", "")),
            status=AccountStatus(str(data.get("status", "active"))),
            daily_sent=int(data.get("daily_sent", 0)),
            daily_limit=int(data.get("daily_limit", 0)),
            last_reset=data.get("last_reset"),
            cooldown_until=parsed_cooldown,
        )
