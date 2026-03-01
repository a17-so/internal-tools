#!/usr/bin/env python3
"""
Generate videos for a batch of randomly selected features.

Usage:
    python generate_random.py            # Generate 6 random videos (default)
    python generate_random.py -n 10      # Generate 10 random videos
"""
import argparse
import logging
import random
import sys

from generator import generate_video, load_hooks

logger = logging.getLogger(__name__)


def generate_random_videos(count: int = 6) -> None:
    """Select *count* random features and generate one video each."""
    if count <= 0:
        logger.error("Count must be a positive integer.")
        sys.exit(1)

    hooks_db = load_hooks()

    features_list = [
        (category, feature_id)
        for category, features in hooks_db.get("features", {}).items()
        for feature_id in features
    ]

    if not features_list:
        logger.error("No features found in hooks.json")
        sys.exit(1)

    count = min(count, len(features_list))
    selected = random.sample(features_list, count)

    logger.info("Found %d features — selected %d for generation.", len(features_list), count)
    for cat, feat in selected:
        logger.info("  • %s / %s", cat, feat)

    successful = 0
    for i, (category, feature) in enumerate(selected):
        print(f"\n[{i + 1}/{count}] Generating video for {category} → {feature}...")
        try:
            output = generate_video(category=category, feature_id=feature)
            if output:
                print(f"✓ Success: {output}")
                successful += 1
        except Exception as exc:
            logger.error("Failed %s/%s: %s", category, feature, exc)

    print(f"\nCompleted. {successful}/{count} videos generated successfully.")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Generate random feature videos")
    parser.add_argument("-n", "--count", type=int, default=6, help="Number of videos to generate")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    generate_random_videos(count=args.count)


if __name__ == "__main__":
    main()
