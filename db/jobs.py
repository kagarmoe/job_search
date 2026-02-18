"""CRUD operations for the jobs table."""

from __future__ import annotations

import sqlite3

from .connection import get_db
from .models import Job


def upsert_job(
    title: str,
    url: str,
    *,
    description: str | None = None,
    posted_date: str | None = None,
    source: str | None = None,
    feed: str | None = None,
    db: sqlite3.Connection | None = None,
) -> Job:
    """Insert a job or update it if the URL already exists.

    On conflict, updates title/description/posted_date/source/feed
    but preserves user-set fields (score, status, resume, cover letter).
    """
    conn = db or get_db()
    cursor = conn.execute(
        """
        INSERT INTO jobs (title, url, description, posted_date, source, feed)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(url) DO UPDATE SET
            title       = excluded.title,
            description = excluded.description,
            posted_date = excluded.posted_date,
            source      = excluded.source,
            feed        = excluded.feed
        RETURNING *
        """,
        (title, url, description, posted_date, source, feed),
    )
    row = cursor.fetchone()
    conn.commit()
    return Job.from_row(row)


def get_job(job_id: int, *, db: sqlite3.Connection | None = None) -> Job | None:
    """Fetch a single job by ID."""
    conn = db or get_db()
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return Job.from_row(row) if row else None


def get_job_by_url(url: str, *, db: sqlite3.Connection | None = None) -> Job | None:
    """Fetch a single job by URL."""
    conn = db or get_db()
    row = conn.execute("SELECT * FROM jobs WHERE url = ?", (url,)).fetchone()
    return Job.from_row(row) if row else None


def list_jobs(
    *,
    status: str | None = None,
    source: str | None = None,
    min_score: float | None = None,
    order_by: str = "created_at DESC",
    limit: int | None = None,
    db: sqlite3.Connection | None = None,
) -> list[Job]:
    """List jobs with optional filters.

    Args:
        status: Filter by status (new, reviewed, applied, rejected, offer).
        source: Filter by source.
        min_score: Only return jobs scored at or above this value.
        order_by: SQL ORDER BY clause. Default: created_at DESC.
        limit: Max number of results.
    """
    conn = db or get_db()
    clauses: list[str] = []
    params: list = []

    if status is not None:
        clauses.append("status = ?")
        params.append(status)
    if source is not None:
        clauses.append("source = ?")
        params.append(source)
    if min_score is not None:
        clauses.append("score >= ?")
        params.append(min_score)

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

    # Validate order_by to prevent injection — allow only known columns + direction
    _ALLOWED_ORDER = {
        "created_at", "posted_date", "score", "status", "title", "id",
        "created_at DESC", "created_at ASC",
        "posted_date DESC", "posted_date ASC",
        "score DESC", "score ASC",
        "status ASC", "status DESC",
        "title ASC", "title DESC",
        "id ASC", "id DESC",
    }
    if order_by not in _ALLOWED_ORDER:
        order_by = "created_at DESC"

    sql = f"SELECT * FROM jobs{where} ORDER BY {order_by}"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    return [Job.from_row(r) for r in rows]


def update_status(
    job_id: int, status: str, *, db: sqlite3.Connection | None = None
) -> Job | None:
    """Update a job's status. Returns the updated job or None if not found."""
    conn = db or get_db()
    cursor = conn.execute(
        "UPDATE jobs SET status = ? WHERE id = ? RETURNING *",
        (status, job_id),
    )
    row = cursor.fetchone()
    conn.commit()
    return Job.from_row(row) if row else None


def update_score(
    job_id: int,
    score: float,
    rationale: str | None = None,
    *,
    db: sqlite3.Connection | None = None,
) -> Job | None:
    """Update a job's score and optional rationale."""
    conn = db or get_db()
    cursor = conn.execute(
        "UPDATE jobs SET score = ?, score_rationale = ? WHERE id = ? RETURNING *",
        (score, rationale, job_id),
    )
    row = cursor.fetchone()
    conn.commit()
    return Job.from_row(row) if row else None


def delete_job(job_id: int, *, db: sqlite3.Connection | None = None) -> bool:
    """Delete a job by ID. Returns True if a row was deleted."""
    conn = db or get_db()
    cursor = conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    conn.commit()
    return cursor.rowcount > 0
