"""Read/write feed fetch timestamps."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from .connection import get_db


def get_last_fetch(feed_url: str, *, db: sqlite3.Connection | None = None) -> datetime | None:
    """Return the last-fetch timestamp for a feed, or None if never fetched."""
    conn = db or get_db()
    row = conn.execute(
        "SELECT last_fetch FROM feed_fetch_log WHERE feed_url = ?",
        (feed_url,),
    ).fetchone()
    if row is None:
        return None
    return datetime.fromisoformat(row["last_fetch"])


def get_all_last_fetches(*, db: sqlite3.Connection | None = None) -> dict[str, datetime]:
    """Return {feed_url: last_fetch} for all tracked feeds."""
    conn = db or get_db()
    rows = conn.execute("SELECT feed_url, last_fetch FROM feed_fetch_log").fetchall()
    return {row["feed_url"]: datetime.fromisoformat(row["last_fetch"]) for row in rows}


def set_last_fetch(
    feed_url: str,
    last_fetch: datetime,
    *,
    db: sqlite3.Connection | None = None,
) -> None:
    """Record or update the last-fetch timestamp for a feed."""
    conn = db or get_db()
    conn.execute(
        """
        INSERT INTO feed_fetch_log (feed_url, last_fetch)
        VALUES (?, ?)
        ON CONFLICT(feed_url) DO UPDATE SET last_fetch = excluded.last_fetch
        """,
        (feed_url, last_fetch.isoformat()),
    )
    conn.commit()
