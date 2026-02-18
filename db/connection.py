"""Database connection management.

get_db() returns a connection with WAL mode, Row factory, and foreign keys.
Connections are cached per-thread for safety.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from .schema import SCHEMA_SQL

DB_PATH = Path(__file__).resolve().parent.parent / "job_search.db"

_local = threading.local()


def get_db(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Return a SQLite connection (cached per-thread).

    Args:
        db_path: Override the default database path. Useful for testing.
    """
    path = str(db_path or DB_PATH)
    conn = getattr(_local, "conn", None)

    # Return cached connection if same path and still open
    if conn is not None and getattr(_local, "db_path", None) == path:
        try:
            conn.execute("SELECT 1")
            return conn
        except sqlite3.ProgrammingError:
            pass  # connection was closed, create a new one

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    _local.conn = conn
    _local.db_path = path
    return conn


def close_db() -> None:
    """Close the thread-local connection if it exists."""
    conn = getattr(_local, "conn", None)
    if conn is not None:
        conn.close()
        _local.conn = None
        _local.db_path = None


def init_db(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Initialize the database schema. Returns the connection.

    Idempotent: all DDL uses IF NOT EXISTS.
    """
    conn = get_db(db_path)
    conn.executescript(SCHEMA_SQL)
    return conn
