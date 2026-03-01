from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import requests

from outreach_automation.local_scraper_client import LocalScrapeClient, LocalScrapeSettings
from outreach_automation.models import ScrapePayload


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


def _make_template_script(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "def get_templates(app_name='REGEN', app_config=None):",
                "    return {",
                "        'submicro': {",
                "            'subject': f'PAID PROMO OPPORTUNITY - {app_name} App',",
                "            'email_md': 'hey {name},\\n\\nemail body',",
                "            'dm_md': 'hey {name},\\n\\ndm body',",
                "        }",
                "    }",
            ]
        )
    )


def test_local_scraper_extracts_bio_ig_and_email(tmp_path: Path, monkeypatch: Any) -> None:
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(parents=True)
    _make_template_script(scripts_dir / "regen.py")

    def fake_get(*args: Any, **kwargs: Any) -> _FakeResponse:
        _ = (args, kwargs)
        return _FakeResponse(
            {
                "profile": {
                    "username": "creatorx",
                    "name": "Creator X",
                    "bio": "ig: @creatorx_ig email creatorx(at)mail.com",
                    "bio_link": "",
                }
            }
        )

    monkeypatch.setattr("outreach_automation.local_scraper_client.requests.get", fake_get)

    client = LocalScrapeClient(
        LocalScrapeSettings(
            searchapi_key="dummy",
            request_timeout_seconds=10,
            same_username_fallback=False,
            templates_dir=scripts_dir,
            outreach_apps_json=None,
        )
    )
    result = client.scrape(
        ScrapePayload(
            app="regen",
            creator_url="https://www.tiktok.com/@creatorx",
            category="Submicro",
            sender_profile="ethan",
        )
    )

    assert result.ig_handle == "creatorx_ig"
    assert result.email_to == "creatorx@mail.com"
    assert "hey creatorx" in result.dm_text
    assert result.email_subject == "PAID PROMO OPPORTUNITY - REGEN App"


def test_local_scraper_same_username_fallback(tmp_path: Path, monkeypatch: Any) -> None:
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(parents=True)
    _make_template_script(scripts_dir / "regen.py")

    def fake_get(*args: Any, **kwargs: Any) -> _FakeResponse:
        _ = (args, kwargs)
        return _FakeResponse(
            {
                "profile": {
                    "username": "sameuser",
                    "name": "Same User",
                    "bio": "no social links",
                    "bio_link": "",
                }
            }
        )

    monkeypatch.setattr("outreach_automation.local_scraper_client.requests.get", fake_get)

    client = LocalScrapeClient(
        LocalScrapeSettings(
            searchapi_key="dummy",
            request_timeout_seconds=10,
            same_username_fallback=True,
            templates_dir=scripts_dir,
            outreach_apps_json=None,
        )
    )
    result = client.scrape(
        ScrapePayload(
            app="regen",
            creator_url="https://www.tiktok.com/@sameuser",
            category="Submicro",
            sender_profile="ethan",
        )
    )
    assert result.ig_handle == "sameuser"


def test_local_scraper_retries_transient_searchapi_error(tmp_path: Path, monkeypatch: Any) -> None:
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(parents=True)
    _make_template_script(scripts_dir / "regen.py")

    calls = {"count": 0}

    def fake_get(*args: Any, **kwargs: Any) -> _FakeResponse:
        _ = (args, kwargs)
        calls["count"] += 1
        if calls["count"] < 2:
            raise requests.Timeout("temporary timeout")
        return _FakeResponse(
            {
                "profile": {
                    "username": "retryuser",
                    "name": "Retry User",
                    "bio": "ig: @retryuser",
                    "bio_link": "",
                }
            }
        )

    monkeypatch.setattr("outreach_automation.local_scraper_client.requests.get", fake_get)
    monkeypatch.setattr("outreach_automation.local_scraper_client.time.sleep", lambda _: None)

    client = LocalScrapeClient(
        LocalScrapeSettings(
            searchapi_key="dummy",
            request_timeout_seconds=10,
            same_username_fallback=False,
            templates_dir=scripts_dir,
            outreach_apps_json=None,
        )
    )
    result = client.scrape(
        ScrapePayload(
            app="regen",
            creator_url="https://www.tiktok.com/@retryuser",
            category="Submicro",
            sender_profile="ethan",
        )
    )
    assert calls["count"] == 2
    assert result.ig_handle == "retryuser"


def test_local_scraper_extracts_email_and_ig_from_link_page(tmp_path: Path, monkeypatch: Any) -> None:
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(parents=True)
    _make_template_script(scripts_dir / "regen.py")

    class _StreamResponse(_FakeResponse):
        def __init__(self, body: str) -> None:
            super().__init__({})
            self._body = body

        def iter_content(self, chunk_size: int = 8192) -> Iterator[bytes]:
            data = self._body.encode("utf-8")
            for i in range(0, len(data), chunk_size):
                yield data[i : i + chunk_size]

    def fake_get(*args: Any, **kwargs: Any) -> Any:
        url = args[0] if args else kwargs.get("url", "")
        if "searchapi.io" in str(url):
            return _FakeResponse(
                {
                    "profile": {
                        "username": "withlink",
                        "name": "With Link",
                        "bio": "no public email in bio",
                        "bio_link": "https://linktr.ee/withlink",
                    }
                }
            )
        return _StreamResponse(
            '<a href="mailto:lead@example.com">mail</a>'
            '<a href="https://instagram.com/withlink.ig">ig</a>'
        )

    monkeypatch.setattr("outreach_automation.local_scraper_client.requests.get", fake_get)

    client = LocalScrapeClient(
        LocalScrapeSettings(
            searchapi_key="dummy",
            request_timeout_seconds=10,
            same_username_fallback=False,
            templates_dir=scripts_dir,
            outreach_apps_json=None,
        )
    )
    result = client.scrape(
        ScrapePayload(
            app="regen",
            creator_url="https://www.tiktok.com/@withlink",
            category="Submicro",
            sender_profile="ethan",
        )
    )
    assert result.email_to == "lead@example.com"
    assert result.ig_handle == "withlink.ig"
