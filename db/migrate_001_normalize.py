#!/usr/bin/env python3
"""Migration 001: Normalize source/feed columns into separate tables.

Converts the old denormalized schema (jobs.source TEXT, jobs.feed TEXT,
feed_fetch_log table) into the normalized schema (sources, feeds tables
with FK references from jobs).

Safe to run multiple times — skips if already migrated.

Usage:
    python -m db.migrate_001_normalize
    python -m db.migrate_001_normalize --db-path /path/to/job_search.db
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

from .connection import get_db, close_db


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cols = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    return column in cols


def migrate(db_path: str | Path | None = None) -> None:
    """Run the normalization migration."""
    conn = get_db(db_path)

    # ── Guard: skip if already migrated ──────────────────────────────
    if _table_exists(conn, "sources") and _column_exists(conn, "jobs", "source_id"):
        print("Already migrated — sources table and jobs.source_id exist. Skipping.")
        return

    # ── Guard: nothing to migrate if old columns don't exist ─────────
    if not _column_exists(conn, "jobs", "source"):
        print("Old schema not detected (no jobs.source column). Nothing to migrate.")
        return

    print("Starting migration: normalize source/feed into separate tables...")

    # ── 1. Create new tables ─────────────────────────────────────────
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sources (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS feeds (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL UNIQUE,
            url         TEXT UNIQUE,
            source_id   INTEGER REFERENCES sources(id),
            last_fetch  TEXT
        );
    """)
    print("  Created sources and feeds tables.")

    # ── 2. Populate sources from existing jobs.source values ─────────
    conn.execute("""
        INSERT OR IGNORE INTO sources (name)
        SELECT DISTINCT source FROM jobs WHERE source IS NOT NULL
    """)
    source_count = conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
    print(f"  Populated {source_count} source(s).")

    # ── 3. Populate feeds from existing jobs.feed values ─────────────
    conn.execute("""
        INSERT OR IGNORE INTO feeds (name)
        SELECT DISTINCT feed FROM jobs WHERE feed IS NOT NULL
    """)

    # ── 4. Absorb feed_fetch_log into feeds table ────────────────────
    if _table_exists(conn, "feed_fetch_log"):
        # For each feed_fetch_log row, try to match an existing feed by
        # checking if the feed_url was used as the feed name, or update
        # feeds that were created from jobs.feed with matching urls.
        rows = conn.execute("SELECT feed_url, last_fetch FROM feed_fetch_log").fetchall()
        for row in rows:
            feed_url = row["feed_url"]
            last_fetch = row["last_fetch"]

            # Try to find a feed with this url already
            existing = conn.execute(
                "SELECT id FROM feeds WHERE url = ?", (feed_url,)
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE feeds SET last_fetch = ? WHERE id = ?",
                    (last_fetch, existing["id"]),
                )
            else:
                # No feed matched by url — insert with url as name
                conn.execute(
                    "INSERT OR IGNORE INTO feeds (name, url, last_fetch) VALUES (?, ?, ?)",
                    (feed_url, feed_url, last_fetch),
                )

        conn.execute("DROP TABLE feed_fetch_log")
        print(f"  Absorbed {len(rows)} feed_fetch_log row(s) into feeds table.")

    feed_count = conn.execute("SELECT COUNT(*) FROM feeds").fetchone()[0]
    print(f"  Total feeds: {feed_count}.")

    # ── 5. Add FK columns to jobs ────────────────────────────────────
    if not _column_exists(conn, "jobs", "source_id"):
        conn.execute("ALTER TABLE jobs ADD COLUMN source_id INTEGER REFERENCES sources(id)")
    if not _column_exists(conn, "jobs", "feed_id"):
        conn.execute("ALTER TABLE jobs ADD COLUMN feed_id INTEGER REFERENCES feeds(id)")

    # ── 6. Backfill FK values from text columns ──────────────────────
    conn.execute("""
        UPDATE jobs SET source_id = (
            SELECT s.id FROM sources s WHERE s.name = jobs.source
        )
        WHERE source IS NOT NULL AND source_id IS NULL
    """)
    conn.execute("""
        UPDATE jobs SET feed_id = (
            SELECT f.id FROM feeds f WHERE f.name = jobs.feed
        )
        WHERE feed IS NOT NULL AND feed_id IS NULL
    """)
    print("  Backfilled source_id and feed_id on jobs rows.")

    # ── 7. Drop old text columns ─────────────────────────────────────
    # SQLite doesn't support DROP COLUMN before 3.35.0 (2021-03).
    # We'll recreate the table to remove the old columns.
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS jobs_new (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            title           TEXT NOT NULL,
            url             TEXT NOT NULL UNIQUE,
            description     TEXT,
            posted_date     TEXT,
            source_id       INTEGER REFERENCES sources(id),
            feed_id         INTEGER REFERENCES feeds(id),
            score           REAL CHECK (score IS NULL OR (score >= 0 AND score <= 10)),
            score_rationale TEXT,
            status          TEXT NOT NULL DEFAULT 'new'
                                CHECK (status IN ('new', 'passed', 'reviewed', 'applied', 'rejected', 'offer')),
            location_label  TEXT CHECK (location_label IS NULL OR location_label IN ('Seattle', 'Remote', 'Review for location')),
            job_type        TEXT,
            pay_range       TEXT,
            contract_duration TEXT,
            resume_md           TEXT,
            resume_pdf_path     TEXT,
            cover_letter_md     TEXT,
            cover_letter_pdf_path TEXT,
            created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now')),
            updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now'))
        );

        INSERT INTO jobs_new (
            id, title, url, description, posted_date,
            source_id, feed_id,
            score, score_rationale, status, location_label,
            job_type, pay_range, contract_duration,
            resume_md, resume_pdf_path, cover_letter_md, cover_letter_pdf_path,
            created_at, updated_at
        )
        SELECT
            id, title, url, description, posted_date,
            source_id, feed_id,
            score, score_rationale, status, location_label,
            job_type, pay_range, contract_duration,
            resume_md, resume_pdf_path, cover_letter_md, cover_letter_pdf_path,
            created_at, updated_at
        FROM jobs;

        DROP TABLE jobs;
        ALTER TABLE jobs_new RENAME TO jobs;

        -- Recreate trigger
        CREATE TRIGGER IF NOT EXISTS jobs_updated_at
            AFTER UPDATE ON jobs
            FOR EACH ROW
        BEGIN
            UPDATE jobs SET updated_at = strftime('%Y-%m-%dT%H:%M:%S', 'now')
            WHERE id = OLD.id;
        END;

        -- Recreate indexes
        CREATE INDEX IF NOT EXISTS idx_jobs_status      ON jobs (status);
        CREATE INDEX IF NOT EXISTS idx_jobs_score       ON jobs (score);
        CREATE INDEX IF NOT EXISTS idx_jobs_posted_date ON jobs (posted_date);
        CREATE INDEX IF NOT EXISTS idx_jobs_status_score ON jobs (status, score DESC);
        CREATE INDEX IF NOT EXISTS idx_jobs_location_label ON jobs (location_label);
        CREATE INDEX IF NOT EXISTS idx_jobs_source_id   ON jobs (source_id);
        CREATE INDEX IF NOT EXISTS idx_jobs_feed_id     ON jobs (feed_id);
    """)
    print("  Rebuilt jobs table without old source/feed text columns.")

    conn.commit()
    print("Migration complete.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run database normalization migration")
    parser.add_argument("--db-path", help="Path to database file")
    args = parser.parse_args()

    try:
        migrate(args.db_path)
    finally:
        close_db()


if __name__ == "__main__":
    main()
