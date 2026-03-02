from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class HistoricalPost:
    post_id: str
    post_url: str
    account_handle: str
    posted_at: datetime | None
    caption: str | None
    views: int
    likes: int
    comments: int
    shares: int
    source: str = "playwright_public"
    confidence: float = 0.8


@dataclass(slots=True)
class PostFormatMatch:
    post_id: str
    format_name: str | None
    example_id: str | None
    confidence: float
    status: str
    reasons: list[str]


@dataclass(slots=True)
class DraftSlide:
    index: int
    role: str
    text: str


@dataclass(slots=True)
class DraftBundle:
    draft_id: str
    format_name: str
    topic: str
    caption: str
    predicted_score: float
    rationale: list[str]
    slides: list[DraftSlide]
