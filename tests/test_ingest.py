"""Tests for pipeline/ingest.py — manual URL ingest module."""

from unittest.mock import patch, MagicMock

import pytest

from pipeline.ingest import fetch_job_from_url, _extract_title, _derive_source, _extract_body_text


class TestExtractTitle:
    """Tests for _extract_title()."""

    def test_extracts_title_from_html(self):
        html = "<html><head><title>Senior Technical Writer - Acme Corp</title></head></html>"
        assert _extract_title(html) == "Senior Technical Writer - Acme Corp"

    def test_strips_greenhouse_suffix(self):
        html = "<title>Tech Writer - Greenhouse</title>"
        assert _extract_title(html) == "Tech Writer"

    def test_strips_ashby_suffix(self):
        html = "<title>Tech Writer | Ashby Jobs</title>"
        assert _extract_title(html) == "Tech Writer"

    def test_strips_lever_suffix(self):
        html = "<title>Writer – Lever</title>"
        assert _extract_title(html) == "Writer"

    def test_returns_untitled_when_no_title_tag(self):
        html = "<html><body>Hello</body></html>"
        assert _extract_title(html) == "Untitled"


class TestDeriveSource:
    """Tests for _derive_source()."""

    def test_greenhouse_url(self):
        assert _derive_source("https://boards.greenhouse.io/acme/jobs/123") == "Greenhouse"

    def test_ashby_url(self):
        assert _derive_source("https://jobs.ashbyhq.com/company/123") == "Ashby"

    def test_lever_url(self):
        assert _derive_source("https://jobs.lever.co/company/123") == "Lever"

    def test_unknown_domain_uses_hostname(self):
        assert _derive_source("https://careers.example.com/jobs/42") == "careers.example.com"


class TestExtractBodyText:
    """Tests for _extract_body_text()."""

    def test_strips_html_tags(self):
        html = "<p>Hello <b>world</b></p>"
        result = _extract_body_text(html)
        assert "Hello" in result
        assert "world" in result
        assert "<" not in result

    def test_strips_script_and_style(self):
        html = "<script>alert('hi')</script><style>.x{}</style><p>Content</p>"
        result = _extract_body_text(html)
        assert "alert" not in result
        assert "Content" in result

    def test_truncates_to_10000_chars(self):
        html = "<p>" + "a" * 20000 + "</p>"
        result = _extract_body_text(html)
        assert len(result) <= 10000


class TestFetchJobFromUrl:
    """Tests for fetch_job_from_url()."""

    @patch("pipeline.ingest.httpx.get")
    def test_returns_job_dict(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.text = "<html><head><title>Writer at Acme</title></head><body>Description here</body></html>"
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = fetch_job_from_url("https://boards.greenhouse.io/acme/jobs/1")
        assert result["title"] == "Writer at Acme"
        assert result["url"] == "https://boards.greenhouse.io/acme/jobs/1"
        assert result["source"] == "Greenhouse"
        assert result["feed"] == "Manual Ingest"
        assert "Description" in result["description"]

    @patch("pipeline.ingest.httpx.get")
    def test_http_error_raises(self, mock_get):
        import httpx
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=MagicMock()
        )
        mock_get.return_value = mock_resp

        with pytest.raises(httpx.HTTPStatusError):
            fetch_job_from_url("https://example.com/bad")
