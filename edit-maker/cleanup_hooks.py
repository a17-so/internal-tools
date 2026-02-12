#!/usr/bin/env python3
"""
One-shot utility to clean hook text in hooks.json.

Replaces weak patterns like "X makes you attractive" with the stronger
"X is what makes you attractive" variant.
"""
import json
from typing import List

from config import HOOKS_FILE


def clean_hooks(hooks_list: List[str]) -> List[str]:
    """Upgrade weak hook phrasing to the stronger 'is what' variant."""
    current_hooks = set(hooks_list)
    cleaned: List[str] = []

    for hook in hooks_list:
        if (
            hook.endswith("makes you attractive")
            and "10x" not in hook
            and "is what" not in hook
        ):
            strong = hook.replace(" makes you attractive", " is what makes you attractive")
            if strong != hook:
                if strong in current_hooks:
                    continue  # strong version already exists; drop this one
                cleaned.append(strong)
                continue
        cleaned.append(hook)

    return cleaned


def main() -> None:
    """Run the cleanup and write the result back to hooks.json."""
    with open(HOOKS_FILE, "r") as f:
        data = json.load(f)

    for category in data.get("features", {}):
        for item_key, item in data["features"][category].items():
            if "hooks" in item:
                item["hooks"] = clean_hooks(item["hooks"])

    with open(HOOKS_FILE, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")

    print("Hooks cleaned successfully.")


if __name__ == "__main__":
    main()
