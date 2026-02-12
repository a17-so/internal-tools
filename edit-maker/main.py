#!/usr/bin/env python3
"""
Pretti Edit Maker - Automated short-form video generator

Usage:
    python main.py list                              # List all features
    python main.py generate <category> <feature>    # Generate 1 video
    python main.py batch <category> <feature> -n 2  # Generate multiple videos
    python main.py generate --dry-run ...           # Test without rendering
"""
import argparse
import sys
from generator import generate_video, list_all_features, get_feature_info


def cmd_list(args):
    """List all available features."""
    features = list_all_features()
    
    print("\n=== Available Features ===\n")
    
    current_category = None
    for category, feature_id, sample_hook in features:
        if category != current_category:
            print(f"\n{category.upper().replace('_', ' ')}")
            print("-" * 40)
            current_category = category
        
        print(f"  {feature_id}")
        print(f"    └─ \"{sample_hook}\"")
    
    print(f"\nTotal: {len(features)} features")
    print("\nUsage: python main.py generate <category> <feature>")


def cmd_generate(args):
    """Generate a single video."""
    try:
        output = generate_video(
            category=args.category,
            feature_id=args.feature,
            hook_index=args.hook,
            dry_run=args.dry_run
        )
        if output:
            print(f"\n✓ Video saved to: {output}")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)


def cmd_batch(args):
    """Generate multiple videos for a feature."""
    count = args.count or 2
    
    print(f"Generating {count} videos for {args.category}/{args.feature}...")
    
    outputs = []
    for i in range(count):
        print(f"\n--- Video {i+1}/{count} ---")
        try:
            output = generate_video(
                category=args.category,
                feature_id=args.feature,
                hook_index=i if i < len(get_feature_info(args.category, args.feature).get("hooks", [])) else None,
                dry_run=args.dry_run
            )
            if output:
                outputs.append(output)
        except Exception as e:
            print(f"✗ Error on video {i+1}: {e}")
    
    if outputs:
        print(f"\n✓ Generated {len(outputs)} videos:")
        for o in outputs:
            print(f"  - {o}")


def main():
    parser = argparse.ArgumentParser(
        description="Pretti Edit Maker - Automated short-form video generator"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # list command
    list_parser = subparsers.add_parser("list", help="List all available features")
    list_parser.set_defaults(func=cmd_list)
    
    # generate command
    gen_parser = subparsers.add_parser("generate", help="Generate a single video")
    gen_parser.add_argument("category", help="Feature category (e.g., facial_features)")
    gen_parser.add_argument("feature", help="Feature ID (e.g., short_philtrum)")
    gen_parser.add_argument("--hook", type=int, help="Specific hook index to use")
    gen_parser.add_argument("--dry-run", action="store_true", help="Test without rendering")
    gen_parser.set_defaults(func=cmd_generate)
    
    # batch command
    batch_parser = subparsers.add_parser("batch", help="Generate multiple videos")
    batch_parser.add_argument("category", help="Feature category")
    batch_parser.add_argument("feature", help="Feature ID")
    batch_parser.add_argument("-n", "--count", type=int, default=2, help="Number of videos")
    batch_parser.add_argument("--dry-run", action="store_true", help="Test without rendering")
    batch_parser.set_defaults(func=cmd_batch)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    args.func(args)


if __name__ == "__main__":
    main()
