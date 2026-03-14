from __future__ import annotations

from outreach_automation.models import Tier

_ALLOWED: dict[str, Tier] = {
    "macro": Tier.MACRO,
    "micro": Tier.MICRO,
    "submicro": Tier.SUBMICRO,
    "sub-micro": Tier.SUBMICRO,
    "ambassador": Tier.AMBASSADOR,
    "themepage": Tier.THEMEPAGE,
    "theme-page": Tier.THEMEPAGE,
    "theme page": Tier.THEMEPAGE,
    "themepages": Tier.THEMEPAGE,
    "theme-pages": Tier.THEMEPAGE,
    "ai influencer": Tier.AI_INFLUENCER,
    "ai-influencer": Tier.AI_INFLUENCER,
    "ai_influencer": Tier.AI_INFLUENCER,
}


class TierValidationError(ValueError):
    pass


class MissingTierError(TierValidationError):
    pass


class InvalidTierError(TierValidationError):
    pass


class UnsupportedTierDeferredError(TierValidationError):
    pass


_DEFERRED_UNSUPPORTED = {
    "yt creator",
    "yt-creator",
    "yt_creator",
}


def resolve_tier(raw: str) -> Tier:
    normalized = raw.strip().lower().replace("_", "-")
    if not normalized:
        raise MissingTierError("creator_tier is required")
    if normalized in _DEFERRED_UNSUPPORTED:
        raise UnsupportedTierDeferredError(f"unsupported creator_tier for automation: {raw}")

    matched = _ALLOWED.get(normalized)
    if matched is None:
        raise InvalidTierError(f"invalid creator_tier: {raw}")
    return matched
