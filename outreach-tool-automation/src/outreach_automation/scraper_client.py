from __future__ import annotations

from dataclasses import asdict

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from outreach_automation.models import ScrapePayload, ScrapeResponse


class ScrapeClient:
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url

    @retry(
        reraise=True,
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type((requests.Timeout, requests.ConnectionError)),
    )
    def scrape(self, payload: ScrapePayload) -> ScrapeResponse:
        response = requests.post(
            self._base_url,
            json={
                "app": payload.app,
                "url": payload.creator_url,
                "category": payload.category,
                "sender_profile": payload.sender_profile,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return ScrapeResponse(
            dm_text=str(data.get("dm_text", "")).strip(),
            email_to=data.get("email_to"),
            email_subject=data.get("email_subject"),
            email_body_text=data.get("email_body_text"),
            ig_handle=data.get("ig_handle"),
        )


__all__ = ["ScrapeClient", "ScrapePayload", "ScrapeResponse", "asdict"]
