"""Shared fixtures for pytest test suite."""

import tempfile
from pathlib import Path

import pytest

from db.connection import init_db, close_db


@pytest.fixture
def db_conn():
    """Create a temporary database with full schema for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    conn = init_db(db_path)
    yield conn

    close_db()
    Path(db_path).unlink(missing_ok=True)
    Path(db_path + "-wal").unlink(missing_ok=True)
    Path(db_path + "-shm").unlink(missing_ok=True)


@pytest.fixture
def app_client(db_conn):
    """Create a Flask test client backed by a temp database."""
    from unittest.mock import patch
    import app as flask_app

    # Patch get_db to return our temp connection
    with patch("db.connection.get_db", return_value=db_conn), \
         patch("db.jobs.get_db", return_value=db_conn):
        flask_app.app.config["TESTING"] = True
        with flask_app.app.test_client() as client:
            yield client
