from __future__ import annotations

import re


def normalize_dm_text(raw_text: str) -> str:
    """Normalize generated DM text while preserving paragraph line breaks."""
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
    lines: list[str] = []
    prev_blank = False
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            if not prev_blank:
                lines.append("")
            prev_blank = True
            continue
        lines.append(line)
        prev_blank = False

    # Trim leading/trailing blank lines.
    while lines and lines[0] == "":
        lines.pop(0)
    while lines and lines[-1] == "":
        lines.pop()

    return "\n".join(lines)
