from __future__ import annotations

import re


def normalize_dm_text(raw_text: str) -> str:
    """Normalize generated DM text into a single clean message payload."""
    if not raw_text:
        return ""

    text = raw_text
    # Convert simple markdown emphasis to plain text.
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    text = re.sub(r"_([^_]+)_", r"\1", text)
    # Convert links: [text](url) -> text.
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Force single-message format across DM channels.
    text = re.sub(r"\s+", " ", text)
    return text.strip()

