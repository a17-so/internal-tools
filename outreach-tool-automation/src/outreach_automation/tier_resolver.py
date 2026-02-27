from __future__ import annotations

from outreach_automation.models import Tier

_ALLOWED: dict[str, Tier] = {
    "macro": Tier.MACRO,
    "micro": Tier.MICRO,
    "submicro": Tier.SUBMICRO,
    "sub-micro": Tier.SUBMICRO,
    "ambassador": Tier.AMBASSADOR,
}


class TierValidationError(ValueError):
    pass


class MissingTierError(TierValidationError):
    pass


class InvalidTierError(TierValidationError):
    pass


def resolve_tier(raw: str) -> Tier:
    normalized = raw.strip().lower().replace("_", "-")
    if not normalized:
        raise MissingTierError("creator_tier is required")

    matched = _ALLOWED.get(normalized)
    if matched is None:
        raise InvalidTierError(f"invalid creator_tier: {raw}")
    return matched
