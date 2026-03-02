"""CLI for Frankenstein Maker."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List

from fm.capture.session import run_capture_session
from fm.capture.store import read_jsonl, write_jsonl
from fm.config import (
    APPROVED_PATH,
    CANDIDATES_PATH,
    CAPTURED_PATH,
    COOLDOWN_STORE_PATH,
    DATA_DIR,
    DEFAULT_COOLDOWN_DAYS,
    DEFAULT_SESSION_TARGET,
    MANIFEST_DEFAULT,
    MANIFEST_EXAMPLE,
    OUTPUT_DIR,
    REPORTS_DIR,
    SEED_FILE_DEFAULT,
    SEED_FILE_EXAMPLE,
    VIDEOS_DIR,
)
from fm.export.uploader_csv import discover_videos, export_csv
from fm.hooks.cooldown import apply_cooldown, load_cooldown_store, save_cooldown_store
from fm.hooks.dedupe import dedupe_rows
from fm.hooks.review import run_review
from fm.logging import setup_logging
from fm.render.export import render_batch
from fm.utils.paths import ensure_dir
from fm.validate.assets import validate_manifest_assets
from fm.validate.manifest import validate_manifest_file

logger = logging.getLogger(__name__)


def _cmd_init(_args: argparse.Namespace) -> None:
    for path in [DATA_DIR, OUTPUT_DIR, VIDEOS_DIR, REPORTS_DIR]:
        ensure_dir(path)

    ensure_dir(SEED_FILE_EXAMPLE.parent)
    if not SEED_FILE_EXAMPLE.exists():
        SEED_FILE_EXAMPLE.write_text(
            "# Put one instagram handle per line\n"
            "example_page_one\n"
            "example_page_two\n",
            encoding="utf-8",
        )

    if not SEED_FILE_DEFAULT.exists():
        SEED_FILE_DEFAULT.write_text(SEED_FILE_EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")

    ensure_dir(MANIFEST_EXAMPLE.parent)
    example_manifest: Dict = {
        "timing": {
            "hook_seconds_min": 3.0,
            "hook_seconds_max": 5.0,
        },
        "styles": {
            "calm_reclaim": {
                "clip_pools": ["/absolute/path/to/calm_clip_01.mp4"],
                "music": {"path": "/absolute/path/to/calm_music.mp3"},
                "icon": {"path": "/absolute/path/to/everest_icon.png"},
                "overlays": {
                    "top_bar": {
                        "hook": "still scrolling bro?",
                        "cta": "download everest and start microlearning",
                    }
                },
            },
            "intense_smart": {
                "clip_pools": ["/absolute/path/to/intense_clip_01.mp4"],
                "music": {"path": "/absolute/path/to/intense_music.mp3"},
                "icon": {"path": "/absolute/path/to/everest_icon.png"},
                "overlays": {
                    "top_bar": {
                        "hook": "smart people do not doomscroll",
                        "cta": "use everest to reclaim your attention",
                    }
                },
            },
        },
    }

    if not MANIFEST_EXAMPLE.exists():
        MANIFEST_EXAMPLE.write_text(json.dumps(example_manifest, indent=2) + "\n", encoding="utf-8")

    if not MANIFEST_DEFAULT.exists():
        MANIFEST_DEFAULT.write_text(MANIFEST_EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")

    for p in [CAPTURED_PATH, CANDIDATES_PATH, APPROVED_PATH]:
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("", encoding="utf-8")

    if not COOLDOWN_STORE_PATH.exists():
        COOLDOWN_STORE_PATH.write_text("{}\n", encoding="utf-8")

    print("Initialized project scaffolding and example files.")


def _cmd_capture_start(args: argparse.Namespace) -> None:
    seed_file = Path(args.seed_file).expanduser()
    output = Path(args.output).expanduser()

    count = run_capture_session(seed_file=seed_file, output_path=output, target=args.session_target)
    import asyncio

    final_count = asyncio.run(count)
    print(f"Capture session ended. Total captures: {final_count}")


def _cmd_capture_finalize(args: argparse.Namespace) -> None:
    captured = read_jsonl(Path(args.input).expanduser())
    unique, dropped = dedupe_rows(captured, phash_threshold=args.phash_threshold)

    store_path = Path(args.cooldown_store).expanduser()
    store = load_cooldown_store(store_path)
    finalized = apply_cooldown(unique, store, cooldown_days=args.cooldown_days)
    save_cooldown_store(store_path, store)

    out_path = Path(args.output).expanduser()
    write_jsonl(out_path, finalized)

    print(
        "Finalize complete: "
        f"captured={len(captured)} unique={len(unique)} dropped={len(dropped)} "
        f"eligible={sum(1 for r in finalized if r.get('eligible'))}"
    )


def _cmd_hooks_review(args: argparse.Namespace) -> None:
    reviewed, accepted = run_review(
        candidates_path=Path(args.input).expanduser(),
        approved_path=Path(args.output).expanduser(),
        reviewer=args.reviewer,
    )
    print(f"Review complete. reviewed={reviewed} accepted={accepted}")


def _select_hooks(approved_rows: List[Dict], count: int) -> List[Dict]:
    eligible = [r for r in approved_rows if str(r.get("hook_local_path") or "").strip()]
    return eligible[:count]


def _cmd_render(args: argparse.Namespace) -> None:
    manifest_path = Path(args.manifest).expanduser()
    errors, warnings, manifest = validate_manifest_file(manifest_path)
    if errors:
        for e in errors:
            print(f"ERROR: {e}")
        sys.exit(1)

    for w in warnings:
        print(f"WARN: {w}")

    approved = read_jsonl(Path(args.approved_hooks).expanduser())
    hooks = _select_hooks(approved, count=args.count * (2 if args.style == "both" else 1))

    if not hooks:
        print("No approved hooks with hook_local_path found. Populate approved.jsonl first.")
        return

    videos_dir = Path(args.videos_dir).expanduser()
    ensure_dir(videos_dir)

    styles = [args.style] if args.style != "both" else ["calm_reclaim", "intense_smart"]
    outputs = []
    cursor = 0
    for style in styles:
        slice_hooks = hooks[cursor: cursor + args.count]
        cursor += args.count
        outs = render_batch(
            style_name=style,
            hooks=slice_hooks,
            manifest=manifest,
            count=args.count,
            videos_dir=videos_dir,
            dry_run=args.dry_run,
        )
        outputs.extend(outs)

    print(f"Render complete. Generated {len(outputs)} videos.")
    for p in outputs:
        print(f"- {p}")


def _cmd_export_csv(args: argparse.Namespace) -> None:
    videos_dir = Path(args.videos_dir).expanduser()
    videos = discover_videos(videos_dir)
    count = export_csv(
        videos=videos,
        output_csv=Path(args.output_csv).expanduser(),
        account_id=args.account_id,
        hashtags=args.hashtags,
        platform=args.platform,
        mode=args.mode,
        root_dir=videos_dir,
        absolute_paths=args.absolute_paths,
    )
    print(f"Exported {count} rows to {args.output_csv}")


def _cmd_audit(args: argparse.Namespace) -> None:
    manifest_path = Path(args.manifest).expanduser()
    errors, warnings, data = validate_manifest_file(manifest_path)
    asset_errors: List[str] = []
    asset_warnings: List[str] = []
    if data:
        asset_errors, asset_warnings = validate_manifest_assets(data)

    all_errors = errors + asset_errors
    all_warnings = warnings + asset_warnings

    print("=== Audit ===")
    print(f"Errors: {len(all_errors)}")
    print(f"Warnings: {len(all_warnings)}")

    for e in all_errors:
        print(f"ERROR: {e}")
    for w in all_warnings:
        print(f"WARN: {w}")

    if args.strict and all_errors:
        sys.exit(1)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Frankenstein Maker")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Create folders and example files")
    p_init.set_defaults(func=_cmd_init)

    p_capture = sub.add_parser("capture", help="Capture operations")
    capture_sub = p_capture.add_subparsers(dest="capture_cmd", required=True)

    p_capture_start = capture_sub.add_parser("start", help="Start capture session")
    p_capture_start.add_argument("--seed-file", default=str(SEED_FILE_DEFAULT))
    p_capture_start.add_argument("--session-target", type=int, default=DEFAULT_SESSION_TARGET)
    p_capture_start.add_argument("--output", default=str(CAPTURED_PATH))
    p_capture_start.set_defaults(func=_cmd_capture_start)

    p_capture_finalize = capture_sub.add_parser("finalize", help="Finalize captured hooks")
    p_capture_finalize.add_argument("--input", default=str(CAPTURED_PATH))
    p_capture_finalize.add_argument("--output", default=str(CANDIDATES_PATH))
    p_capture_finalize.add_argument("--cooldown-store", default=str(COOLDOWN_STORE_PATH))
    p_capture_finalize.add_argument("--cooldown-days", type=int, default=DEFAULT_COOLDOWN_DAYS)
    p_capture_finalize.add_argument("--phash-threshold", type=int, default=8)
    p_capture_finalize.set_defaults(func=_cmd_capture_finalize)

    p_hooks = sub.add_parser("hooks", help="Hooks review operations")
    hooks_sub = p_hooks.add_subparsers(dest="hooks_cmd", required=True)
    p_hooks_review = hooks_sub.add_parser("review", help="Review candidates")
    p_hooks_review.add_argument("--input", default=str(CANDIDATES_PATH))
    p_hooks_review.add_argument("--output", default=str(APPROVED_PATH))
    p_hooks_review.add_argument("--reviewer", default="local_user")
    p_hooks_review.set_defaults(func=_cmd_hooks_review)

    p_render = sub.add_parser("render", help="Render final videos")
    p_render.add_argument("--style", choices=["calm_reclaim", "intense_smart", "both"], default="both")
    p_render.add_argument("--count", type=int, required=True)
    p_render.add_argument("--manifest", default=str(MANIFEST_DEFAULT))
    p_render.add_argument("--approved-hooks", default=str(APPROVED_PATH))
    p_render.add_argument("--videos-dir", default=str(VIDEOS_DIR))
    p_render.add_argument("--dry-run", action="store_true")
    p_render.set_defaults(func=_cmd_render)

    p_export = sub.add_parser("export-csv", help="Export uploader CSV")
    p_export.add_argument("--account-id", required=True)
    p_export.add_argument("--hashtags", default="")
    p_export.add_argument("--videos-dir", default=str(VIDEOS_DIR))
    p_export.add_argument("--output-csv", required=True)
    p_export.add_argument("--platform", default="tiktok")
    p_export.add_argument("--mode", default="draft", choices=["draft", "direct"])
    p_export.add_argument("--absolute-paths", action="store_true")
    p_export.set_defaults(func=_cmd_export_csv)

    p_audit = sub.add_parser("audit", help="Validate manifest/assets")
    p_audit.add_argument("--manifest", default=str(MANIFEST_DEFAULT))
    p_audit.add_argument("--strict", action="store_true")
    p_audit.set_defaults(func=_cmd_audit)

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    setup_logging(verbose=args.verbose)

    try:
        args.func(args)
    except KeyboardInterrupt:
        print("Interrupted.")
    except Exception as exc:  # noqa: BLE001
        logger.exception("Command failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
