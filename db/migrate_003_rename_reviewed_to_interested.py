"""Migration: rename 'reviewed' status to 'interested'.

Rebuilds jobs table with updated CHECK constraint and renames
all existing 'reviewed' rows to 'interested'.

Usage:
    python -m db.migrate_003_rename_reviewed_to_interested
"""

from .connection import get_db


def migrate():
    conn = get_db()

    # Check if migration is needed
    ddl = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='jobs'"
    ).fetchone()
    if ddl and "'interested'" in ddl[0]:
        print("Migration 003: already applied (interested status exists).")
        return

    print("Migration 003: renaming 'reviewed' to 'interested'...")

    # Rebuild table first (new constraint allows 'interested'),
    # then rename data inside the INSERT via CASE expression.
    conn.executescript("""
        PRAGMA foreign_keys = OFF;

        CREATE TABLE jobs_new (
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
                                CHECK (status IN ('new', 'interested', 'passed', 'applied', 'rejected', 'offer')),
            location_label  TEXT CHECK (location_label IS NULL OR location_label IN ('Seattle', 'Remote', 'Review for location')),
            job_type        TEXT,
            pay_range       TEXT,
            contract_duration TEXT,
            resume_md           TEXT,
            resume_pdf_path     TEXT,
            cover_letter_md     TEXT,
            cover_letter_pdf_path TEXT,
            notes               TEXT,
            created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now')),
            updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now'))
        );

        INSERT INTO jobs_new (
            id, title, url, description, posted_date,
            source_id, feed_id, score, score_rationale, status,
            location_label, job_type, pay_range, contract_duration,
            resume_md, resume_pdf_path, cover_letter_md, cover_letter_pdf_path,
            notes, created_at, updated_at
        )
        SELECT
            id, title, url, description, posted_date,
            source_id, feed_id, score, score_rationale,
            CASE WHEN status = 'reviewed' THEN 'interested' ELSE status END,
            location_label, job_type, pay_range, contract_duration,
            resume_md, resume_pdf_path, cover_letter_md, cover_letter_pdf_path,
            notes, created_at, updated_at
        FROM jobs;

        DROP TABLE jobs;

        ALTER TABLE jobs_new RENAME TO jobs;

        CREATE TRIGGER IF NOT EXISTS jobs_updated_at
            AFTER UPDATE ON jobs
            FOR EACH ROW
        BEGIN
            UPDATE jobs SET updated_at = strftime('%Y-%m-%dT%H:%M:%S', 'now')
            WHERE id = OLD.id;
        END;

        CREATE INDEX IF NOT EXISTS idx_jobs_status        ON jobs (status);
        CREATE INDEX IF NOT EXISTS idx_jobs_score         ON jobs (score);
        CREATE INDEX IF NOT EXISTS idx_jobs_posted_date   ON jobs (posted_date);
        CREATE INDEX IF NOT EXISTS idx_jobs_status_score  ON jobs (status, score DESC);
        CREATE INDEX IF NOT EXISTS idx_jobs_location_label ON jobs (location_label);
        CREATE INDEX IF NOT EXISTS idx_jobs_source_id     ON jobs (source_id);
        CREATE INDEX IF NOT EXISTS idx_jobs_feed_id       ON jobs (feed_id);

        PRAGMA foreign_keys = ON;
    """)

    print("Migration 003: done.")


if __name__ == "__main__":
    migrate()
