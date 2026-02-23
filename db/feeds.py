"""CRUD operations for the sources and feeds tables."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from .connection import get_db
from .models import Feed, Source


def get_or_create_source(
    name: str, *, db: sqlite3.Connection | None = None
) -> int:
    """Return the source ID for *name*, creating a new row if needed."""
    conn = db or get_db()
    row = conn.execute(
        "SELECT id FROM sources WHERE name = ?", (name,)
    ).fetchone()
    if row:
        return row["id"]
    cursor = conn.execute(
        "INSERT INTO sources (name) VALUES (?) RETURNING id", (name,)
    )
    return cursor.fetchone()["id"]


def get_or_create_feed(
    name: str,
    *,
    url: str | None = None,
    source_id: int | None = None,
    db: sqlite3.Connection | None = None,
) -> int:
    """Return the feed ID for *name*, creating a new row if needed.

    If *url* is provided, looks up by url first, then by name.
    When creating, stores both name and url.
    """
    conn = db or get_db()

    # Try lookup by url first (most precise)
    if url:
        row = conn.execute(
            "SELECT id FROM feeds WHERE url = ?", (url,)
        ).fetchone()
        if row:
            return row["id"]

    # Fall back to lookup by name
    row = conn.execute(
        "SELECT id FROM feeds WHERE name = ?", (name,)
    ).fetchone()
    if row:
        # Backfill url if we now have it and the row doesn't
        if url:
            conn.execute(
                "UPDATE feeds SET url = ? WHERE id = ? AND url IS NULL",
                (url, row["id"]),
            )
        return row["id"]

    # Create new feed
    cursor = conn.execute(
        "INSERT INTO feeds (name, url, source_id) VALUES (?, ?, ?) RETURNING id",
        (name, url, source_id),
    )
    return cursor.fetchone()["id"]


# ---------------------------------------------------------------------------
# Feed fetch timestamps (replaces former feed_fetch_log helpers)
# ---------------------------------------------------------------------------

def get_last_fetch(
    feed_url: str, *, db: sqlite3.Connection | None = None
) -> datetime | None:
    """Return the last-fetch timestamp for a feed URL, or None if never fetched."""
    conn = db or get_db()
    row = conn.execute(
        "SELECT last_fetch FROM feeds WHERE url = ?", (feed_url,)
    ).fetchone()
    if row is None or row["last_fetch"] is None:
        return None
    return datetime.fromisoformat(row["last_fetch"])


def get_all_last_fetches(
    *, db: sqlite3.Connection | None = None
) -> dict[str, datetime]:
    """Return {feed_url: last_fetch} for all feeds with a recorded timestamp."""
    conn = db or get_db()
    rows = conn.execute(
        "SELECT url, last_fetch FROM feeds WHERE url IS NOT NULL AND last_fetch IS NOT NULL"
    ).fetchall()
    return {row["url"]: datetime.fromisoformat(row["last_fetch"]) for row in rows}


def set_last_fetch(
    feed_url: str,
    last_fetch: datetime,
    *,
    db: sqlite3.Connection | None = None,
) -> None:
    """Record or update the last-fetch timestamp for a feed URL.

    If a feed row exists for this URL, updates its last_fetch.
    Otherwise creates a minimal row (name derived from URL).
    """
    conn = db or get_db()

    # Try to update existing row
    cursor = conn.execute(
        "UPDATE feeds SET last_fetch = ? WHERE url = ?",
        (last_fetch.isoformat(), feed_url),
    )
    if cursor.rowcount == 0:
        # No row with this URL — create one using URL as the name
        conn.execute(
            "INSERT INTO feeds (name, url, last_fetch) VALUES (?, ?, ?)",
            (feed_url, feed_url, last_fetch.isoformat()),
        )
    conn.commit()
