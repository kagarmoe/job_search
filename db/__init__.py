"""job_search database package.

Usage:
    from db import init_db, get_db, close_db
    conn = init_db()  # creates tables if needed
"""

from .connection import close_db, get_db, init_db

__all__ = ["get_db", "init_db", "close_db"]
