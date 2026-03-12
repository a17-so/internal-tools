from __future__ import annotations

import random

STYLES = {"safe", "balanced", "bold", "expert"}

_COPY_BANK = {
    "safe": {
        "titles": [
            "Skincare products that helped my skin look smoother",
            "Products I repurchased for calmer looking skin",
            "My current skincare picks for texture support",
        ],
        "captions": [
            "my honest routine notes and ratings",
            "what worked for me lately",
            "sharing my current lineup",
        ],
        "hooks": [
            "skincare products i would repurchase again",
            "my no-drama skincare lineup right now",
            "products i keep reaching for every week",
        ],
        "before": [
            "my skin used to feel irritated and uneven",
            "my routine was not helping my texture",
            "i felt stuck with breakouts and dryness",
        ],
        "after": [
            "small routine changes helped my skin look healthier",
            "my skin looks calmer and way more even now",
            "consistency made the biggest difference for me",
        ],
        "cta": [
            "scan this in pretti before you buy",
            "double check this in pretti first",
            "quick scan in pretti before checkout",
        ],
        "reviews": [
            "this felt gentle and kept my skin barrier calm",
            "easy to use and my skin felt smoother over time",
            "i keep this in rotation because it is consistent",
        ],
    },
    "balanced": {
        "titles": [
            "Sephora products that helped me get glass skin",
            "Skincare products I would repurchase again",
            "My current must-buy skincare lineup",
        ],
        "captions": [
            "honest routine breakdown + ratings",
            "real results from my current routine",
            "what made the biggest difference for me",
        ],
        "hooks": [
            "sephora products i would repurchase again",
            "the skincare products that changed my skin",
            "my holy grail skincare lineup right now",
        ],
        "before": [
            "i thought it was impossible to fix my skin",
            "my texture and breakouts were out of control",
            "my skin was irritated and i tried everything",
        ],
        "after": [
            "the right skincare routine changed everything",
            "my skin is smoother, calmer, and more radiant",
            "once i fixed my routine, everything clicked",
        ],
        "cta": [
            "scan this in pretti before you buy",
            "use pretti scan before checking out",
            "run this through pretti first",
        ],
        "reviews": [
            "my skin looked smoother in a week and i kept using it",
            "this helped my barrier and reduced random flare ups",
            "lightweight, non-irritating, and super consistent",
        ],
    },
    "bold": {
        "titles": [
            "Skincare products that SAVED my skin",
            "The products I would buy again instantly",
            "My no-gatekeep skincare master list",
        ],
        "captions": [
            "my top picks, worst picks, and scan verdicts",
            "what is worth your money and what is not",
            "this routine changed my skin fast",
        ],
        "hooks": [
            "sephora sale master must buy list",
            "products that SAVED my skin barrier",
            "what i wish i bought sooner for clear skin",
        ],
        "before": [
            "my skin was a complete mess before this",
            "i hated my texture and nothing was working",
            "this was my worst skin era",
        ],
        "after": [
            "my skin started glowing once i fixed this",
            "night and day difference after this routine",
            "finally found products my skin actually loves",
        ],
        "cta": [
            "scan this in pretti right now before buying",
            "do not buy until you run a pretti scan",
            "pretti scan this first to avoid wasting money",
        ],
        "reviews": [
            "i did not expect this to work but it delivered fast",
            "this one earned a permanent spot in my routine",
            "huge difference in texture, glow, and irritation",
        ],
    },
    "expert": {
        "titles": [
            "Barrier-first skincare products I repurchase",
            "My evidence-based skincare routine picks",
            "Texture-support lineup with simple layering",
        ],
        "captions": [
            "focus: barrier support, hydration, low irritation",
            "practical routine notes with scan scores",
            "ingredient-aware picks from my routine",
        ],
        "hooks": [
            "barrier-support products i consistently rebuy",
            "my low-irritation skincare lineup",
            "products i use for texture and hydration support",
        ],
        "before": [
            "my skin was reactive, dehydrated, and uneven",
            "over-exfoliation made my skin more sensitive",
            "my routine was too aggressive for my barrier",
        ],
        "after": [
            "once i simplified, my skin looked more balanced",
            "hydration and barrier support made the biggest difference",
            "less irritation, better texture, more consistency",
        ],
        "cta": [
            "scan this in pretti for ingredient context",
            "use pretti scan to sanity-check this product",
            "quick pretti scan before adding to cart",
        ],
        "reviews": [
            "gentle profile, easy layering, and solid daily performance",
            "works well in a barrier-focused routine without heaviness",
            "consistent hydration support without noticeable irritation",
        ],
    },
}


def resolve_style(style: str | None) -> str:
    if not style:
        return "balanced"
    style_lc = style.strip().lower()
    return style_lc if style_lc in STYLES else "balanced"


def pick_line(style: str, bucket: str, rng: random.Random, fallback: str) -> str:
    bank = _COPY_BANK.get(resolve_style(style), _COPY_BANK["balanced"])
    options = bank.get(bucket, [])
    if options:
        return str(rng.choice(options))
    return fallback
