"""Tests for pipeline/ats_search.py ATS platform search."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from pipeline.ats_search import search_ats_platform, search_all_platforms, ATS_PLATFORMS


class TestSearchAtsPlatform:
    """Tests for search_ats_platform()."""

    @patch("pipeline.ats_search.client")
    def test_returns_parsed_jobs(self, mock_client):
        """Returns parsed jobs from mocked OpenAI response."""
        raw_json = (
            '[{"title": "Technical Writer", '
            '"url": "https://boards.greenhouse.io/acme/jobs/123", '
            '"company": "Acme Corp"}]'
        )
        text_content = MagicMock()
        text_content.type = "output_text"
        text_content.text = raw_json

        message = MagicMock()
        message.type = "message"
        message.content = [text_content]

        mock_client.responses.create.return_value = MagicMock(output=[message])

        jobs = search_ats_platform("greenhouse.io", source="Greenhouse", feed="Greenhouse Search")
        assert len(jobs) == 1
        assert jobs[0]["title"] == "Technical Writer"
        assert jobs[0]["url"] == "https://boards.greenhouse.io/acme/jobs/123"
        assert jobs[0]["company"] == "Acme Corp"
        assert jobs[0]["source"] == "Greenhouse"
        assert jobs[0]["feed"] == "Greenhouse Search"

    @patch("pipeline.ats_search.client")
    def test_filters_out_urls_without_target_domain(self, mock_client):
        """Discards results whose URL does not contain the target domain."""
        raw_json = (
            '['
            '{"title": "Good Job", "url": "https://boards.greenhouse.io/acme/jobs/1", "company": "Acme"},'
            '{"title": "Bad Job", "url": "https://linkedin.com/jobs/2", "company": "Other"}'
            ']'
        )
        text_content = MagicMock()
        text_content.type = "output_text"
        text_content.text = raw_json

        message = MagicMock()
        message.type = "message"
        message.content = [text_content]

        mock_client.responses.create.return_value = MagicMock(output=[message])

        jobs = search_ats_platform("greenhouse.io", source="Greenhouse", feed="Greenhouse Search")
        assert len(jobs) == 1
        assert jobs[0]["title"] == "Good Job"

    @patch("pipeline.ats_search.client")
    def test_returns_empty_list_for_empty_results(self, mock_client):
        """Returns empty list when search yields no results."""
        text_content = MagicMock()
        text_content.type = "output_text"
        text_content.text = "[]"

        message = MagicMock()
        message.type = "message"
        message.content = [text_content]

        mock_client.responses.create.return_value = MagicMock(output=[message])

        jobs = search_ats_platform("greenhouse.io", source="Greenhouse", feed="Greenhouse Search")
        assert jobs == []

    @patch("pipeline.ats_search.client")
    def test_includes_since_date_in_query(self, mock_client):
        """Includes 'since date' clause in query when since is provided."""
        text_content = MagicMock()
        text_content.type = "output_text"
        text_content.text = "[]"

        message = MagicMock()
        message.type = "message"
        message.content = [text_content]

        mock_client.responses.create.return_value = MagicMock(output=[message])

        since = datetime(2026, 4, 10, 12, 0, 0)
        search_ats_platform("greenhouse.io", source="Greenhouse", feed="Greenhouse Search", since=since)

        call_args = mock_client.responses.create.call_args
        query = call_args.kwargs["input"]
        assert "2026-04-10" in query

    @patch("pipeline.ats_search.client")
    def test_works_for_ashby_domain(self, mock_client):
        """Works for ashbyhq.com domain with source='Ashby'."""
        raw_json = (
            '[{"title": "Tech Writer", '
            '"url": "https://jobs.ashbyhq.com/company/123", '
            '"company": "StartupCo"}]'
        )
        text_content = MagicMock()
        text_content.type = "output_text"
        text_content.text = raw_json

        message = MagicMock()
        message.type = "message"
        message.content = [text_content]

        mock_client.responses.create.return_value = MagicMock(output=[message])

        jobs = search_ats_platform("ashbyhq.com", source="Ashby", feed="Ashby Search")
        assert len(jobs) == 1
        assert jobs[0]["source"] == "Ashby"
        assert jobs[0]["feed"] == "Ashby Search"

        call_args = mock_client.responses.create.call_args
        tools = call_args.kwargs["tools"]
        assert tools[0]["filters"]["allowed_domains"] == ["ashbyhq.com"]


class TestSearchAllPlatforms:
    """Tests for search_all_platforms()."""

    @patch("pipeline.ats_search.search_ats_platform")
    def test_combines_results_from_all_platforms(self, mock_search):
        """Combines results from all ATS platforms."""
        mock_search.side_effect = [
            [{"title": "GH Job", "url": "https://greenhouse.io/1", "company": "A", "source": "Greenhouse", "feed": "Greenhouse Search"}],
            [{"title": "Ashby Job", "url": "https://ashbyhq.com/2", "company": "B", "source": "Ashby", "feed": "Ashby Search"}],
        ]

        jobs = search_all_platforms()
        assert len(jobs) == 2
        assert jobs[0]["title"] == "GH Job"
        assert jobs[1]["title"] == "Ashby Job"

    @patch("pipeline.ats_search.search_ats_platform")
    def test_calls_search_once_per_platform(self, mock_search):
        """Calls search_ats_platform once per configured platform."""
        mock_search.return_value = []

        search_all_platforms()
        assert mock_search.call_count == len(ATS_PLATFORMS)
