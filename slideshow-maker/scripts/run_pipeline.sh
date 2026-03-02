#!/usr/bin/env bash
set -euo pipefail

DB_PATH="${1:-./data/slideshow_machine.db}"
ACCOUNTS_FILE="${2:-./config/accounts.example.txt}"
TOPIC="${3:-Everyday makeup glow up guide}"

python -m slideshow_machine.cli --db "$DB_PATH" init-db
python -m slideshow_machine.cli --db "$DB_PATH" ingest-assets --assets-root ./assets
python -m slideshow_machine.cli --db "$DB_PATH" backfill --accounts-file "$ACCOUNTS_FILE"
python -m slideshow_machine.cli --db "$DB_PATH" match-posts --threshold 0.4
python -m slideshow_machine.cli --db "$DB_PATH" score-formats
python -m slideshow_machine.cli --db "$DB_PATH" make-drafts --topic "$TOPIC" --count 5
python -m slideshow_machine.cli --db "$DB_PATH" report
EOF && chmod +x scripts/run_pipeline.sh