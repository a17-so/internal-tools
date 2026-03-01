import pytest

from outreach_automation.models import Tier
from outreach_automation.tier_resolver import InvalidTierError, MissingTierError, resolve_tier


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Macro", Tier.MACRO),
        ("macro", Tier.MACRO),
        ("MICRO", Tier.MICRO),
        ("submicro", Tier.SUBMICRO),
        ("sub-micro", Tier.SUBMICRO),
        ("Ambassador", Tier.AMBASSADOR),
        ("Themepage", Tier.THEMEPAGE),
        ("Theme Page", Tier.THEMEPAGE),
        ("theme-pages", Tier.THEMEPAGE),
    ],
)
def test_resolve_tier(raw: str, expected: Tier) -> None:
    assert resolve_tier(raw) is expected


def test_missing_tier() -> None:
    with pytest.raises(MissingTierError):
        resolve_tier("   ")


def test_invalid_tier() -> None:
    with pytest.raises(InvalidTierError):
        resolve_tier("nano")
