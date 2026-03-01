from __future__ import annotations

import base64
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build  # type: ignore[import-untyped]
from googleapiclient.errors import HttpError  # type: ignore[import-untyped]
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from outreach_automation.models import Account, ChannelResult
from outreach_automation.settings import Settings


class EmailSender:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @retry(
        reraise=True,
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type(HttpError),
    )
    def send(
        self,
        to_email: str | None,
        subject: str | None,
        body: str | None,
        account: Account | None,
        *,
        dry_run: bool,
    ) -> ChannelResult:
        if not self._settings.email_send_enabled:
            return ChannelResult(status="skipped", error_code="email_disabled")
        if not to_email or not subject or not body:
            return ChannelResult(status="skipped", error_code="missing_email_fields")
        if account is None:
            return ChannelResult(status="pending_tomorrow", error_code="no_email_account")
        if dry_run:
            return ChannelResult(status="sent")

        match = None
        for conf in self._settings.gmail_accounts:
            if conf.email.lower() == account.handle.lower():
                match = conf
                break
        if match is None:
            return ChannelResult(status="failed", error_code="missing_refresh_token")

        if not self._settings.gmail_client_id or not self._settings.gmail_client_secret:
            return ChannelResult(status="failed", error_code="missing_gmail_client_credentials")

        creds = Credentials(  # type: ignore[no-untyped-call]
            token=None,
            refresh_token=match.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self._settings.gmail_client_id,
            client_secret=self._settings.gmail_client_secret,
            scopes=["https://www.googleapis.com/auth/gmail.send"],
        )
        creds.refresh(Request())  # type: ignore[no-untyped-call]

        service = build("gmail", "v1", credentials=creds)
        message = MIMEText(body)
        message["to"] = to_email
        message["from"] = account.handle
        message["subject"] = subject

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return ChannelResult(status="sent")
