"""Tests for Flask /ingest route."""

from unittest.mock import patch, MagicMock

import pytest


class TestIngestRoute:
    """Tests for POST /ingest."""

    def test_get_returns_form(self, app_client):
        resp = app_client.get("/ingest")
        assert resp.status_code == 200
        assert b"Add Job" in resp.data or b"url" in resp.data

    @patch("pipeline.ingest.fetch_job_from_url")
    def test_valid_url_redirects_to_job_detail(self, mock_fetch, app_client):
        mock_fetch.return_value = {
            "title": "Writer at Acme",
            "url": "https://boards.greenhouse.io/acme/jobs/1",
            "description": "A job",
            "source": "Greenhouse",
            "feed": "Manual Ingest",
        }

        resp = app_client.post(
            "/ingest",
            data={"url": "https://boards.greenhouse.io/acme/jobs/1"},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "/job/" in resp.headers["Location"]

    def test_missing_url_returns_400(self, app_client):
        resp = app_client.post("/ingest", data={})
        assert resp.status_code == 400

    def test_empty_url_returns_400(self, app_client):
        resp = app_client.post("/ingest", data={"url": "   "})
        assert resp.status_code == 400
