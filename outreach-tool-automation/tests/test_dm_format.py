from outreach_automation.dm_format import normalize_dm_text


def test_normalize_dm_text_collapses_newlines_and_spaces() -> None:
    raw = "hey  there,\n\nthis   is   a test.\nline two."
    assert normalize_dm_text(raw) == "hey there,\n\nthis is a test.\nline two."


def test_normalize_dm_text_strips_markdown() -> None:
    raw = "**hey** [there](https://example.com) _friend_"
    assert normalize_dm_text(raw) == "hey there friend"


def test_normalize_dm_text_trims_extra_blank_lines() -> None:
    raw = "\n\nfirst\n\n\nsecond\n\n"
    assert normalize_dm_text(raw) == "first\n\nsecond"
