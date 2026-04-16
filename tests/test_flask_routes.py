"""Tests for Flask routes (kimberlygarmoe-33)."""

import pytest
from db.jobs import upsert_job, update_status


class TestIndex:
    def test_index_returns_200(self, app_client, db_conn):
        resp = app_client.get("/")
        assert resp.status_code == 200

    def test_index_shows_jobs(self, app_client, db_conn):
        upsert_job("Test Writer", "https://example.com/1", db=db_conn)
        resp = app_client.get("/")
        assert b"Test Writer" in resp.data

    def test_index_filters_by_status(self, app_client, db_conn):
        job = upsert_job("Writer A", "https://example.com/a", db=db_conn)
        update_status(job.id, "passed", db=db_conn)
        upsert_job("Writer B", "https://example.com/b", db=db_conn)

        resp = app_client.get("/?status=passed")
        assert b"Writer A" in resp.data
        assert b"Writer B" not in resp.data


class TestJobDetail:
    def test_existing_job(self, app_client, db_conn):
        job = upsert_job("Detail Job", "https://example.com/detail", db=db_conn)
        resp = app_client.get(f"/job/{job.id}")
        assert resp.status_code == 200
        assert b"Detail Job" in resp.data

    def test_missing_job_returns_404(self, app_client):
        resp = app_client.get("/job/99999")
        assert resp.status_code == 404


class TestStatusUpdate:
    def test_valid_status(self, app_client, db_conn):
        job = upsert_job("Status Job", "https://example.com/status", db=db_conn)
        resp = app_client.post(
            f"/job/{job.id}/status",
            data={"status": "interested"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "interested"

    def test_invalid_status_returns_400(self, app_client, db_conn):
        job = upsert_job("Bad Status", "https://example.com/bad-status", db=db_conn)
        resp = app_client.post(
            f"/job/{job.id}/status",
            data={"status": "invalid_status"},
        )
        assert resp.status_code == 400
        assert "Invalid status" in resp.get_json()["error"]

    def test_missing_status_returns_400(self, app_client, db_conn):
        job = upsert_job("No Status", "https://example.com/no-status", db=db_conn)
        resp = app_client.post(f"/job/{job.id}/status", data={})
        assert resp.status_code == 400

    def test_nonexistent_job_returns_404(self, app_client):
        resp = app_client.post(
            "/job/99999/status",
            data={"status": "interested"},
        )
        assert resp.status_code == 404


class TestScoreUpdate:
    def test_valid_score(self, app_client, db_conn):
        job = upsert_job("Score Job", "https://example.com/score", db=db_conn)
        resp = app_client.post(
            f"/job/{job.id}/score",
            data={"score": "7.5", "rationale": "Good match"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["score"] == 7.5

    def test_score_out_of_range_returns_400(self, app_client, db_conn):
        job = upsert_job("Bad Score", "https://example.com/bad-score", db=db_conn)
        resp = app_client.post(
            f"/job/{job.id}/score",
            data={"score": "15"},
        )
        assert resp.status_code == 400
        assert "between 0 and 10" in resp.get_json()["error"]

    def test_negative_score_returns_400(self, app_client, db_conn):
        job = upsert_job("Neg Score", "https://example.com/neg-score", db=db_conn)
        resp = app_client.post(
            f"/job/{job.id}/score",
            data={"score": "-1"},
        )
        assert resp.status_code == 400

    def test_non_numeric_score_returns_400(self, app_client, db_conn):
        job = upsert_job("NaN Score", "https://example.com/nan-score", db=db_conn)
        resp = app_client.post(
            f"/job/{job.id}/score",
            data={"score": "abc"},
        )
        assert resp.status_code == 400

    def test_boundary_scores_accepted(self, app_client, db_conn):
        job = upsert_job("Boundary", "https://example.com/boundary", db=db_conn)
        for score in ["0", "10"]:
            resp = app_client.post(
                f"/job/{job.id}/score",
                data={"score": score},
            )
            assert resp.status_code == 200


class TestStripHtml:
    def test_strips_tags(self):
        from app import strip_html_with_spacing
        assert "Hello World" in strip_html_with_spacing("<p>Hello</p><p>World</p>")

    def test_empty_input(self):
        from app import strip_html_with_spacing
        assert strip_html_with_spacing("") == ""
        assert strip_html_with_spacing(None) == ""


class TestIsRecentJob:
    def test_recent_date(self):
        from app import is_recent_job
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        assert is_recent_job(today) is True

    def test_old_date(self):
        from app import is_recent_job
        assert is_recent_job("2020-01-01") is False

    def test_none_returns_false(self):
        from app import is_recent_job
        assert is_recent_job(None) is False

    def test_invalid_date_returns_false(self):
        from app import is_recent_job
        assert is_recent_job("not-a-date") is False
