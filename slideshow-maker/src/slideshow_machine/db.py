from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path


SCHEMA_SQL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS crawl_posts (
  post_id TEXT PRIMARY KEY,
  post_url TEXT NOT NULL,
  account_handle TEXT NOT NULL,
  posted_at TEXT,
  caption TEXT,
  views INTEGER NOT NULL,
  likes INTEGER NOT NULL,
  comments INTEGER NOT NULL,
  shares INTEGER NOT NULL,
  collected_at TEXT NOT NULL,
  source TEXT NOT NULL,
  confidence REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS crawl_failures (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  account_handle TEXT NOT NULL,
  post_url TEXT,
  reason TEXT NOT NULL,
  collected_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS format_examples (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  format_name TEXT NOT NULL,
  example_id TEXT NOT NULL,
  slide_count INTEGER NOT NULL,
  UNIQUE(format_name, example_id)
);

CREATE TABLE IF NOT EXISTS format_slides (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  format_name TEXT NOT NULL,
  example_id TEXT NOT NULL,
  slide_index INTEGER NOT NULL,
  file_path TEXT NOT NULL,
  ocr_text TEXT,
  role TEXT,
  UNIQUE(format_name, example_id, slide_index)
);

CREATE TABLE IF NOT EXISTS normalization_issues (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  format_name TEXT NOT NULL,
  file_path TEXT NOT NULL,
  issue_type TEXT NOT NULL,
  detail TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS post_format_matches (
  post_id TEXT PRIMARY KEY,
  format_name TEXT,
  example_id TEXT,
  confidence REAL NOT NULL,
  status TEXT NOT NULL,
  reasons_json TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS format_scores (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  format_name TEXT NOT NULL,
  account_handle TEXT NOT NULL,
  normalized_views REAL NOT NULL,
  shares_per_1k REAL NOT NULL,
  comments_per_1k REAL NOT NULL,
  likes_per_1k REAL NOT NULL,
  proxy_score REAL NOT NULL,
  sample_size INTEGER NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(format_name, account_handle)
);

CREATE TABLE IF NOT EXISTS drafts (
  draft_id TEXT PRIMARY KEY,
  topic TEXT NOT NULL,
  objective TEXT NOT NULL,
  format_name TEXT NOT NULL,
  predicted_score REAL NOT NULL,
  rationale_json TEXT NOT NULL,
  caption TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS draft_slides (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  draft_id TEXT NOT NULL,
  slide_index INTEGER NOT NULL,
  role TEXT NOT NULL,
  text TEXT NOT NULL,
  UNIQUE(draft_id, slide_index)
);

CREATE TABLE IF NOT EXISTS exports (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  draft_id TEXT NOT NULL,
  output_dir TEXT NOT NULL,
  manifest_path TEXT NOT NULL,
  created_at TEXT NOT NULL
);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with connect(db_path) as conn:
        conn.executescript(SCHEMA_SQL)


@contextmanager
def tx(db_path: Path):
    conn = connect(db_path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def upsert_json(conn: sqlite3.Connection, table: str, key: str, payload: dict) -> None:
    cols = list(payload.keys())
    placeholders = ", ".join(["?"] * len(cols))
    assignments = ", ".join([f"{col}=excluded.{col}" for col in cols if col != key])
    sql = (
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders}) "
        f"ON CONFLICT({key}) DO UPDATE SET {assignments}"
    )
    conn.execute(sql, [payload[c] for c in cols])


def dumps_list(items: list[str]) -> str:
    return json.dumps(items, ensure_ascii=True)
