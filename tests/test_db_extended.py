"""Extended database tests (kimberlygarmoe-37, kimberlygarmoe-39)."""

import sqlite3
import pytest
from db.jobs import (
    upsert_job,
    update_analysis,
    update_status,
    get_job,
    get_next_review_job,
    count_review_jobs,
    update_notes,
)


class TestUpdateAnalysis:
    """Tests for update_analysis() (kimberlygarmoe-37)."""

    def test_updates_location_label(self, db_conn):
        job = upsert_job("Writer", "https://example.com/1", db=db_conn)
        updated = update_analysis(job.id, location_label="Seattle", db=db_conn)
        assert updated.location_label == "Seattle"

    def test_updates_multiple_fields(self, db_conn):
        job = upsert_job("Writer", "https://example.com/2", db=db_conn)
        updated = update_analysis(
            job.id,
            location_label="Remote",
            job_type="Full-time",
            pay_range="$100K-$150K/year",
            db=db_conn,
        )
        assert updated.location_label == "Remote"
        assert updated.job_type == "Full-time"
        assert updated.pay_range == "$100K-$150K/year"

    def test_no_kwargs_returns_unchanged_job(self, db_conn):
        job = upsert_job("Writer", "https://example.com/3", db=db_conn)
        result = update_analysis(job.id, db=db_conn)
        assert result is not None
        assert result.id == job.id

    def test_nonexistent_job_returns_none(self, db_conn):
        result = update_analysis(99999, location_label="Seattle", db=db_conn)
        assert result is None

    def test_invalid_location_label_raises(self, db_conn):
        job = upsert_job("Writer", "https://example.com/4", db=db_conn)
        with pytest.raises(sqlite3.IntegrityError):
            update_analysis(job.id, location_label="InvalidLabel", db=db_conn)

    def test_updates_title(self, db_conn):
        job = upsert_job("R123Writer", "https://example.com/5", db=db_conn)
        updated = update_analysis(
            job.id,
            location_label="Seattle",
            title="R123 Writer",
            db=db_conn,
        )
        assert updated.title == "R123 Writer"


class TestReviewQueue:
    """Tests for get_next_review_job() and count_review_jobs() (kimberlygarmoe-39)."""

    def test_returns_new_job(self, db_conn):
        upsert_job("Review Job", "https://example.com/review1", db=db_conn)
        job = get_next_review_job(db=db_conn)
        assert job is not None
        assert job.title == "Review Job"

    def test_skips_non_new_jobs(self, db_conn):
        j = upsert_job("Passed Job", "https://example.com/passed", db=db_conn)
        update_status(j.id, "passed", db=db_conn)
        upsert_job("New Job", "https://example.com/new", db=db_conn)

        job = get_next_review_job(db=db_conn)
        assert job.title == "New Job"

    def test_returns_none_when_empty(self, db_conn):
        assert get_next_review_job(db=db_conn) is None

    def test_excludes_ids(self, db_conn):
        j1 = upsert_job("Job A", "https://example.com/a", db=db_conn)
        j2 = upsert_job("Job B", "https://example.com/b", db=db_conn)

        job = get_next_review_job(exclude_ids=[j1.id], db=db_conn)
        assert job.id == j2.id

    def test_orders_by_score_desc(self, db_conn):
        from db.jobs import update_score
        j1 = upsert_job("Low Score", "https://example.com/low", db=db_conn)
        j2 = upsert_job("High Score", "https://example.com/high", db=db_conn)
        update_score(j1.id, 3.0, db=db_conn)
        update_score(j2.id, 9.0, db=db_conn)

        job = get_next_review_job(db=db_conn)
        assert job.id == j2.id

    def test_null_scores_come_after_scored(self, db_conn):
        from db.jobs import update_score
        j1 = upsert_job("No Score", "https://example.com/noscore", db=db_conn)
        j2 = upsert_job("Has Score", "https://example.com/hasscore", db=db_conn)
        update_score(j2.id, 5.0, db=db_conn)

        job = get_next_review_job(db=db_conn)
        assert job.id == j2.id

    def test_count_review_jobs(self, db_conn):
        assert count_review_jobs(db=db_conn) == 0

        upsert_job("Job 1", "https://example.com/c1", db=db_conn)
        upsert_job("Job 2", "https://example.com/c2", db=db_conn)
        assert count_review_jobs(db=db_conn) == 2

        j = upsert_job("Job 3", "https://example.com/c3", db=db_conn)
        update_status(j.id, "interested", db=db_conn)
        assert count_review_jobs(db=db_conn) == 2  # only 'new' jobs


class TestUpdateNotes:
    def test_updates_notes(self, db_conn):
        job = upsert_job("Notes Job", "https://example.com/notes", db=db_conn)
        updated = update_notes(job.id, "Not a good fit", db=db_conn)
        assert updated.notes == "Not a good fit"

    def test_nonexistent_job_returns_none(self, db_conn):
        result = update_notes(99999, "notes", db=db_conn)
        assert result is None
