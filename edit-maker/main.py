#!/usr/bin/env python3
"""
Pretti Edit Maker — Automated short-form video generator.

Usage:
    python main.py list                              # List all features
    python main.py generate <category> <feature>     # Generate 1 video
    python main.py batch <category> <feature> -n 2   # Generate multiple videos
    python main.py generate --dry-run ...             # Test without rendering
"""
import argparse
import logging
import sys
from pathlib import Path

from config import OUTPUT_DIR
from generator import (
    audit_feature_assets,
    generate_video,
    get_feature_info,
    list_all_features,
)
from uploader_csv import CsvExportOptions, discover_output_videos, export_uploader_csv

logger = logging.getLogger(__name__)


def cmd_list(_args: argparse.Namespace) -> None:
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


def cmd_generate(args: argparse.Namespace) -> None:
    """Generate a single video."""
    try:
        output = generate_video(
            category=args.category,
            feature_id=args.feature,
            hook_index=args.hook,
            dry_run=args.dry_run,
        )
        if output:
            print(f"\n✓ Video saved to: {output}")
    except Exception as exc:
        logger.error("Generation failed: %s", exc)
        sys.exit(1)


def cmd_batch(args: argparse.Namespace) -> None:
    """Generate multiple videos for a feature."""
    count = args.count
    if count <= 0:
        logger.error("Count must be a positive integer.")
        sys.exit(1)

    # Pre-validate the feature before starting the batch
    info = get_feature_info(args.category, args.feature)
    if not info:
        logger.error("Feature not found: %s/%s", args.category, args.feature)
        sys.exit(1)

    hooks = info.get("hooks", [])
    num_hooks = len(hooks)

    print(f"Generating {count} videos for {args.category}/{args.feature}...")

    outputs = []
    for i in range(count):
        print(f"\n--- Video {i + 1}/{count} ---")
        try:
            output = generate_video(
                category=args.category,
                feature_id=args.feature,
                hook_index=i if i < num_hooks else None,
                dry_run=args.dry_run,
            )
            if output:
                outputs.append(output)
        except Exception as exc:
            logger.error("Error on video %d: %s", i + 1, exc)

    if outputs:
        print(f"\n✓ Generated {len(outputs)} videos:")
        for o in outputs:
            print(f"  - {o}")

        if args.export_csv:
            csv_path = Path(args.export_csv).expanduser()
            options = CsvExportOptions(
                account_id=args.account_id,
                mode=args.upload_mode,
                platform=args.platform,
                hashtags=args.hashtags,
                root_dir=Path(args.root_dir).expanduser(),
                absolute_paths=args.absolute_paths,
            )
            row_count = export_uploader_csv(outputs, csv_path, options)
            print(f"\n✓ Exported {row_count} row(s) to uploader CSV: {csv_path}")

def cmd_audit(_args: argparse.Namespace) -> None:
    """Run a consistency audit across hooks and assets."""
    errors, warnings = audit_feature_assets()

    print("\n=== Asset Audit ===")
    print(f"Errors: {len(errors)}")
    print(f"Warnings: {len(warnings)}")

    if errors:
        print("\nErrors:")
        for item in errors:
            print(f"  - {item}")

    if warnings:
        print("\nWarnings:")
        for item in warnings:
            print(f"  - {item}")

    if errors:
        sys.exit(1)

def cmd_export_uploader_csv(args: argparse.Namespace) -> None:
    """Export uploader CSV from existing edit-maker output files."""
    root_dir = Path(args.root_dir).expanduser()
    videos = discover_output_videos(root_dir)

    if not videos:
        logger.error("No .mp4 files found in %s", root_dir)
        sys.exit(1)

    output_csv = Path(args.output_csv).expanduser()
    options = CsvExportOptions(
        account_id=args.account_id,
        mode=args.upload_mode,
        platform=args.platform,
        hashtags=args.hashtags,
        root_dir=root_dir,
        absolute_paths=args.absolute_paths,
    )
    row_count = export_uploader_csv(videos, output_csv, options)

    print(f"✓ Exported {row_count} row(s) to: {output_csv}")
    print("Next: uploader upload:batch --csv <that file> --root <root_dir> --send-now")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Pretti Edit Maker — Automated short-form video generator",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # list
    list_parser = subparsers.add_parser("list", help="List all available features")
    list_parser.set_defaults(func=cmd_list)

    # generate
    gen_parser = subparsers.add_parser("generate", help="Generate a single video")
    gen_parser.add_argument("category", help="Feature category (e.g. facial_features)")
    gen_parser.add_argument("feature", help="Feature ID (e.g. short_philtrum)")
    gen_parser.add_argument("--hook", type=int, help="Specific hook index to use")
    gen_parser.add_argument("--dry-run", action="store_true", help="Test without rendering")
    gen_parser.set_defaults(func=cmd_generate)

    # batch
    batch_parser = subparsers.add_parser("batch", help="Generate multiple videos")
    batch_parser.add_argument("category", help="Feature category")
    batch_parser.add_argument("feature", help="Feature ID")
    batch_parser.add_argument("-n", "--count", type=int, default=2, help="Number of videos")
    batch_parser.add_argument("--dry-run", action="store_true", help="Test without rendering")
    batch_parser.add_argument(
        "--export-csv",
        help="Write uploader CSV after generation (requires account options)",
    )
    batch_parser.add_argument(
        "--account-id",
        default="",
        help="Connected account ID for uploader CSV rows",
    )
    batch_parser.add_argument(
        "--upload-mode",
        default="draft",
        choices=["draft", "direct"],
        help="Uploader mode for generated CSV rows",
    )
    batch_parser.add_argument(
        "--platform",
        default="tiktok",
        help="Platform value in uploader CSV rows",
    )
    batch_parser.add_argument(
        "--hashtags",
        default="",
        help="Hashtag block appended to generated captions, e.g. '#pretti #makeup'",
    )
    batch_parser.add_argument(
        "--root-dir",
        default=str(OUTPUT_DIR),
        help="Root directory used for relative video paths in CSV",
    )
    batch_parser.add_argument(
        "--absolute-paths",
        action="store_true",
        help="Write absolute file paths instead of paths relative to --root-dir",
    )
    batch_parser.set_defaults(func=cmd_batch)

    # audit
    audit_parser = subparsers.add_parser("audit", help="Audit hooks/assets integrity")
    audit_parser.set_defaults(func=cmd_audit)

    # export-uploader-csv
    export_parser = subparsers.add_parser(
        "export-uploader-csv",
        help="Export uploader CSV from existing output videos",
    )
    export_parser.add_argument("--account-id", required=True, help="Connected account ID")
    export_parser.add_argument("--output-csv", required=True, help="Destination CSV path")
    export_parser.add_argument(
        "--upload-mode",
        default="draft",
        choices=["draft", "direct"],
        help="Uploader mode for generated rows",
    )
    export_parser.add_argument(
        "--platform",
        default="tiktok",
        help="Platform value in generated rows",
    )
    export_parser.add_argument(
        "--hashtags",
        default="",
        help="Hashtag block appended to each generated caption",
    )
    export_parser.add_argument(
        "--root-dir",
        default=str(OUTPUT_DIR),
        help="Folder to scan for .mp4 output videos",
    )
    export_parser.add_argument(
        "--absolute-paths",
        action="store_true",
        help="Write absolute file paths in CSV",
    )
    export_parser.set_defaults(func=cmd_export_uploader_csv)

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "batch" and args.export_csv and not args.account_id:
        logger.error("--account-id is required when --export-csv is provided.")
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
