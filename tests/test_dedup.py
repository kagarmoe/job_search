"""Integration tests for pipeline/dedup.py (kimberlygarmoe-41)."""

from unittest.mock import patch, MagicMock

import pytest
from pipeline.dedup import deduplicate_jobs, normalize_title, _parse_date
from db.jobs import upsert_job, get_job


class TestParseDate:
    def test_valid_date(self):
        d = _parse_date("2026-03-15")
        assert d.year == 2026
        assert d.month == 3
        assert d.day == 15

    def test_date_with_time(self):
        d = _parse_date("2026-03-15 14:30:00")
        assert d.year == 2026
        assert d.month == 3

    def test_none_returns_min(self):
        from datetime import datetime
        assert _parse_date(None) == datetime.min

    def test_empty_returns_min(self):
        from datetime import datetime
        assert _parse_date("") == datetime.min

    def test_invalid_returns_min(self):
        from datetime import datetime
        assert _parse_date("not-a-date") == datetime.min


class TestDeduplicateJobs:
    def test_removes_duplicates_keeps_richest(self, db_conn):
        # Two jobs with same normalized title, same time window
        upsert_job(
            "Writer in Seattle, WA",
            "https://example.com/d1",
            description="Short desc",
            posted_date="2026-03-10",
            db=db_conn,
        )
        j2 = upsert_job(
            "Writer in Bellevue, WA",
            "https://example.com/d2",
            description="A much longer and richer description with more details",
            posted_date="2026-03-12",
            db=db_conn,
        )

        with patch("pipeline.dedup.get_db", return_value=db_conn):
            stats = deduplicate_jobs()

        assert stats["duplicates"] == 1
        assert stats["deleted"] == 1
        # The richer description should survive
        assert get_job(j2.id, db=db_conn) is not None

    def test_dry_run_does_not_delete(self, db_conn):
        upsert_job("DryRun Job", "https://example.com/dr1", description="a", posted_date="2026-03-10", db=db_conn)
        j2 = upsert_job("DryRun Job", "https://example.com/dr2", description="bb", posted_date="2026-03-12", db=db_conn)

        with patch("pipeline.dedup.get_db", return_value=db_conn):
            stats = deduplicate_jobs(dry_run=True)

        assert stats["duplicates"] == 1
        assert stats["deleted"] == 0
        # Both jobs should still exist
        assert get_job(j2.id, db=db_conn) is not None

    def test_different_time_windows_kept(self, db_conn):
        # Same title but 60 days apart — should be treated as separate postings
        j1 = upsert_job("Window Job", "https://example.com/w1", description="a", posted_date="2026-01-01", db=db_conn)
        j2 = upsert_job("Window Job", "https://example.com/w2", description="b", posted_date="2026-03-15", db=db_conn)

        with patch("pipeline.dedup.get_db", return_value=db_conn):
            stats = deduplicate_jobs(window_days=30)

        assert stats["duplicates"] == 0
        assert get_job(j1.id, db=db_conn) is not None
        assert get_job(j2.id, db=db_conn) is not None

    def test_single_job_not_touched(self, db_conn):
        j = upsert_job("Unique Job", "https://example.com/unique", description="desc", db=db_conn)

        with patch("pipeline.dedup.get_db", return_value=db_conn):
            stats = deduplicate_jobs()

        assert stats["groups"] == 0
        assert stats["duplicates"] == 0
        assert get_job(j.id, db=db_conn) is not None

    def test_null_dates_cluster_together(self, db_conn):
        # Jobs with no date all get datetime.min and should cluster
        upsert_job("NullDate Job", "https://example.com/nd1", description="short", db=db_conn)
        j2 = upsert_job("NullDate Job", "https://example.com/nd2", description="longer description here", db=db_conn)

        with patch("pipeline.dedup.get_db", return_value=db_conn):
            stats = deduplicate_jobs()

        assert stats["duplicates"] == 1
        # The one with the longer description survives
        assert get_job(j2.id, db=db_conn) is not None
