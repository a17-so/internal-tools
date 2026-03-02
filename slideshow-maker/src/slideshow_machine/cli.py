from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .assets_normalizer import normalize_assets
from .crawler import read_accounts, run_crawl
from .db import init_db, tx
from .drafts import make_drafts
from .exporter import export_draft
from .matcher import match_posts
from .scoring import compute_scores


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="slideshow-machine")
    parser.add_argument("--db", default="./data/slideshow_machine.db", help="SQLite DB path")

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db", help="Initialize database schema")

    p_backfill = sub.add_parser("backfill", help="Run one-time Playwright historical backfill")
    p_backfill.add_argument("--accounts-file", required=True, help="File with one @handle or URL per line")
    p_backfill.add_argument("--max-posts-per-account", type=int, default=None)
    p_backfill.add_argument("--headed", action="store_true", help="Run browser in headed mode")

    p_assets = sub.add_parser("ingest-assets", help="Normalize assets corpus")
    p_assets.add_argument("--assets-root", default="./assets")
    p_assets.add_argument("--with-ocr", action="store_true", help="Use local tesseract OCR if available")

    p_match = sub.add_parser("match-posts", help="Match crawled posts to format families")
    p_match.add_argument("--threshold", type=float, default=0.4)

    sub.add_parser("score-formats", help="Compute proxy virality scores")

    p_drafts = sub.add_parser("make-drafts", help="Generate review-only draft bundles")
    p_drafts.add_argument("--topic", required=True)
    p_drafts.add_argument("--count", required=True, type=int)
    p_drafts.add_argument("--account-scope", default="", help="Comma-separated account handles")
    p_drafts.add_argument("--explore-ratio", type=float, default=0.2)

    p_export = sub.add_parser("export-draft", help="Export draft manifest + uploader row")
    p_export.add_argument("--draft-id", required=True)
    p_export.add_argument("--output-root", default="./output")

    sub.add_parser("report", help="Show pipeline status summary")

    return parser


def cmd_init_db(db_path: Path) -> None:
    init_db(db_path)
    print(json.dumps({"ok": True, "db": str(db_path)}, indent=2))


def cmd_backfill(db_path: Path, args: argparse.Namespace) -> None:
    accounts = read_accounts(Path(args.accounts_file))
    summary = run_crawl(
        db_path=db_path,
        accounts=accounts,
        max_posts_per_account=args.max_posts_per_account,
        headless=not args.headed,
    )
    print(json.dumps(asdict(summary), indent=2))


def cmd_ingest_assets(db_path: Path, args: argparse.Namespace) -> None:
    result = normalize_assets(db_path, Path(args.assets_root), with_ocr=args.with_ocr)
    print(json.dumps(asdict(result), indent=2))


def cmd_match_posts(db_path: Path, args: argparse.Namespace) -> None:
    result = match_posts(db_path, threshold=args.threshold)
    print(json.dumps(result, indent=2))


def cmd_score_formats(db_path: Path) -> None:
    result = compute_scores(db_path)
    print(json.dumps(result, indent=2))


def cmd_make_drafts(db_path: Path, args: argparse.Namespace) -> None:
    account_scope = [x.strip() for x in args.account_scope.split(",") if x.strip()]
    bundles = make_drafts(
        db_path=db_path,
        topic=args.topic,
        count=args.count,
        account_scope=account_scope,
        explore_ratio=args.explore_ratio,
    )
    out = [
        {
            "draft_id": b.draft_id,
            "format_name": b.format_name,
            "predicted_score": b.predicted_score,
            "caption": b.caption,
            "rationale": b.rationale,
            "slides": [{"index": s.index, "role": s.role, "text": s.text} for s in b.slides],
        }
        for b in bundles
    ]
    print(json.dumps(out, indent=2))


def cmd_export_draft(db_path: Path, args: argparse.Namespace) -> None:
    path = export_draft(db_path, args.draft_id, Path(args.output_root))
    print(json.dumps({"manifest": str(path)}, indent=2))


def cmd_report(db_path: Path) -> None:
    with tx(db_path) as conn:
        posts = conn.execute("SELECT COUNT(*) c FROM crawl_posts").fetchone()["c"]
        failures = conn.execute("SELECT COUNT(*) c FROM crawl_failures").fetchone()["c"]
        issues = conn.execute("SELECT COUNT(*) c FROM normalization_issues").fetchone()["c"]
        matches = conn.execute("SELECT status, COUNT(*) c FROM post_format_matches GROUP BY status").fetchall()
        scores = conn.execute("SELECT COUNT(*) c FROM format_scores").fetchone()["c"]
        drafts = conn.execute("SELECT COUNT(*) c FROM drafts").fetchone()["c"]

    report = {
        "posts": posts,
        "crawl_failures": failures,
        "normalization_issues": issues,
        "matches": {m["status"]: m["c"] for m in matches},
        "format_scores": scores,
        "drafts": drafts,
    }
    print(json.dumps(report, indent=2))


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    db_path = Path(args.db)

    if args.command == "init-db":
        cmd_init_db(db_path)
    elif args.command == "backfill":
        cmd_backfill(db_path, args)
    elif args.command == "ingest-assets":
        cmd_ingest_assets(db_path, args)
    elif args.command == "match-posts":
        cmd_match_posts(db_path, args)
    elif args.command == "score-formats":
        cmd_score_formats(db_path)
    elif args.command == "make-drafts":
        cmd_make_drafts(db_path, args)
    elif args.command == "export-draft":
        cmd_export_draft(db_path, args)
    elif args.command == "report":
        cmd_report(db_path)
    else:
        parser.error(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
