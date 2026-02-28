import os

import scrape_profile


class _FakeResponse:
    def __init__(self, *, status_code: int = 200, payload: dict | None = None, body: str = "") -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self._body = body

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")

    def json(self) -> dict:
        return self._payload

    def iter_content(self, chunk_size: int = 8192):
        data = self._body.encode("utf-8")
        for i in range(0, len(data), chunk_size):
            yield data[i : i + chunk_size]


def test_extract_ig_handle_from_link_page_html(monkeypatch):
    def fake_get(url: str, **kwargs):
        _ = kwargs
        assert "linktr.ee" in url
        return _FakeResponse(body='<a href="https://www.instagram.com/creator.handle/">IG</a>')

    monkeypatch.setattr(scrape_profile, "requests", type("Req", (), {"get": staticmethod(fake_get)})())
    handle = scrape_profile._extract_ig_handle_from_link_page("https://linktr.ee/creator")
    assert handle == "creator.handle"


def test_scrape_tiktok_with_searchapi_link_crawl_fallback(monkeypatch):
    os.environ["SEARCHAPI_KEY"] = "dummy"
    os.environ["SCRAPE_IG_BIO_LINK_CRAWL_ENABLED"] = "true"
    os.environ["SCRAPE_IG_SAME_USERNAME_FALLBACK"] = "false"

    def fake_get(url: str, params=None, timeout=None, **kwargs):
        _ = (params, timeout, kwargs)
        if "searchapi.io" in url:
            return _FakeResponse(
                payload={
                    "profile": {
                        "username": "creatorx",
                        "bio": "no ig here",
                        "bio_link": "https://beacons.ai/creatorx",
                    }
                }
            )
        return _FakeResponse(body='<meta content="https://instagram.com/creatorx_ig" />')

    monkeypatch.setattr(scrape_profile, "requests", type("Req", (), {"get": staticmethod(fake_get)})())
    result = scrape_profile.scrape_tiktok_with_searchapi("creatorx")
    assert result["ig_handle"] == "creatorx_ig"


def test_scrape_tiktok_with_searchapi_same_username_fallback(monkeypatch):
    os.environ["SEARCHAPI_KEY"] = "dummy"
    os.environ["SCRAPE_IG_BIO_LINK_CRAWL_ENABLED"] = "false"
    os.environ["SCRAPE_IG_SAME_USERNAME_FALLBACK"] = "true"

    def fake_get(url: str, params=None, timeout=None, **kwargs):
        _ = (params, timeout, kwargs)
        return _FakeResponse(
            payload={
                "profile": {
                    "username": "sameasig",
                    "bio": "just lifting",
                    "bio_link": "",
                }
            }
        )

    monkeypatch.setattr(scrape_profile, "requests", type("Req", (), {"get": staticmethod(fake_get)})())
    result = scrape_profile.scrape_tiktok_with_searchapi("sameasig")
    assert result["ig_handle"] == "sameasig"
