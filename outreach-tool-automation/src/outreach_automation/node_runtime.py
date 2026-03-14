from __future__ import annotations

import os


def suppress_node_deprecation_warnings() -> None:
    """Reduce noisy Node deprecation warnings in Playwright subprocess logs."""
    existing = (os.environ.get("NODE_OPTIONS") or "").strip()
    if "--no-deprecation" in existing:
        return
    if not existing:
        os.environ["NODE_OPTIONS"] = "--no-deprecation"
        return
    os.environ["NODE_OPTIONS"] = f"{existing} --no-deprecation"
