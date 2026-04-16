"""Tests for pipeline integration — run_pipeline() with ATS search."""

from unittest.mock import patch, MagicMock

import pytest


class TestRunPipelineAtsIntegration:
    """Tests for run_pipeline() ATS search integration."""

    @patch("run_pipeline.run_web_search", return_value=(0, 0))
    @patch("run_pipeline.run_ats_search", return_value=(5, 3))
    @patch("run_pipeline.run_rss_fetch", return_value=(0, 0))
    def test_default_run_calls_ats_search(self, mock_rss, mock_ats, mock_web, db_conn):
        from run_pipeline import run_pipeline
        run_pipeline(conn=db_conn, skip_analyzer=True)
        mock_ats.assert_called_once_with(db_conn)

    @patch("run_pipeline.run_web_search", return_value=(0, 0))
    @patch("run_pipeline.run_ats_search", return_value=(0, 0))
    @patch("run_pipeline.run_rss_fetch", return_value=(0, 0))
    def test_rss_only_skips_ats_search(self, mock_rss, mock_ats, mock_web, db_conn):
        from run_pipeline import run_pipeline
        run_pipeline(conn=db_conn, rss_only=True, skip_analyzer=True)
        mock_ats.assert_not_called()

    @patch("run_pipeline.run_web_search", return_value=(0, 0))
    @patch("run_pipeline.run_ats_search", return_value=(0, 0))
    @patch("run_pipeline.run_rss_fetch", return_value=(0, 0))
    def test_search_only_skips_ats_search(self, mock_rss, mock_ats, mock_web, db_conn):
        from run_pipeline import run_pipeline
        run_pipeline(conn=db_conn, search_only=True, skip_analyzer=True)
        mock_ats.assert_not_called()

    @patch("run_pipeline.run_web_search", return_value=(0, 0))
    @patch("run_pipeline.run_ats_search", return_value=(5, 3))
    @patch("run_pipeline.run_rss_fetch", return_value=(0, 0))
    def test_ats_only_skips_rss_and_web(self, mock_rss, mock_ats, mock_web, db_conn):
        from run_pipeline import run_pipeline
        run_pipeline(conn=db_conn, ats_only=True, skip_analyzer=True)
        mock_rss.assert_not_called()
        mock_web.assert_not_called()
        mock_ats.assert_called_once_with(db_conn)
