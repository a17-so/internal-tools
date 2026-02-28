from outreach_automation.tiktok_nodriver_spike import _extract_tiktok_handle, _normalize_tiktok_path


def test_extract_tiktok_handle() -> None:
    assert _extract_tiktok_handle("https://www.tiktok.com/@regen.app") == "regen.app"
    assert _extract_tiktok_handle("https://example.com") is None


def test_normalize_tiktok_path() -> None:
    assert _normalize_tiktok_path("@regen.app") == "@regen.app"
    assert _normalize_tiktok_path("regen.app") == "@regen.app"
    assert (
        _normalize_tiktok_path("https://www.tiktok.com/@regen.app?lang=en")
        == "@regen.app"
    )

