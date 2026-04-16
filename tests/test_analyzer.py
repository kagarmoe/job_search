"""Tests for pipeline/analyzer.py (kimberlygarmoe-35, kimberlygarmoe-36)."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import openai
import pytest

from db.connection import init_db, close_db
from db.jobs import upsert_job, get_job, list_jobs
from db.models import Job


@pytest.fixture
def analyzer_db():
    """Temp database for analyzer integration tests."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    conn = init_db(db_path)
    yield conn
    close_db()
    Path(db_path).unlink(missing_ok=True)
    Path(db_path + "-wal").unlink(missing_ok=True)
    Path(db_path + "-shm").unlink(missing_ok=True)


def _make_job(title="Test Writer", job_id=1, description="Write docs", source="Test"):
    """Create a Job dataclass for testing."""
    return Job(id=job_id, title=title, description=description, source=source)


class TestAnalyzeJobErrorHandling:
    """Tests for analyze_job() error branching (kimberlygarmoe-35)."""

    def test_valid_json_response_returns_dict(self):
        from pipeline.analyzer import analyze_job

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "location_label": "Seattle",
            "location_reasoning": "Located in Seattle",
            "job_type": "Full-time",
            "pay_range": "$100K-$150K/year",
            "contract_duration": "NOT_SPECIFIED",
            "title_cleaned": "Test Writer",
        })

        with patch("pipeline.analyzer.client") as mock_client:
            mock_client.chat.completions.create.return_value = mock_response
            result = analyze_job(_make_job())

        assert result["location_label"] == "Seattle"
        assert result["job_type"] == "Full-time"

    def test_auth_error_raises(self):
        from pipeline.analyzer import analyze_job

        with patch("pipeline.analyzer.client") as mock_client:
            mock_client.chat.completions.create.side_effect = openai.AuthenticationError(
                message="Invalid API key",
                response=MagicMock(status_code=401),
                body=None,
            )
            with pytest.raises(openai.AuthenticationError):
                analyze_job(_make_job())

    def test_rate_limit_error_raises(self):
        from pipeline.analyzer import analyze_job

        with patch("pipeline.analyzer.client") as mock_client:
            mock_client.chat.completions.create.side_effect = openai.RateLimitError(
                message="Rate limited",
                response=MagicMock(status_code=429),
                body=None,
            )
            with pytest.raises(openai.RateLimitError):
                analyze_job(_make_job())

    def test_connection_error_raises(self):
        from pipeline.analyzer import analyze_job

        with patch("pipeline.analyzer.client") as mock_client:
            mock_client.chat.completions.create.side_effect = openai.APIConnectionError(
                request=MagicMock(),
            )
            with pytest.raises(openai.APIConnectionError):
                analyze_job(_make_job())

    def test_invalid_json_raises(self):
        from pipeline.analyzer import analyze_job

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "not valid json"

        with patch("pipeline.analyzer.client") as mock_client:
            mock_client.chat.completions.create.return_value = mock_response
            with pytest.raises(json.JSONDecodeError):
                analyze_job(_make_job())


class TestProcessJobs:
    """Integration tests for process_jobs() orchestration (kimberlygarmoe-36)."""

    def _make_analysis(self, label="Seattle", job_type="Full-time"):
        return {
            "location_label": label,
            "location_reasoning": "test",
            "job_type": job_type,
            "pay_range": "NOT_SPECIFIED",
            "contract_duration": "NOT_SPECIFIED",
            "title_cleaned": "Test Writer",
        }

    def test_delete_label_removes_job(self, analyzer_db):
        from pipeline.analyzer import process_jobs

        job = upsert_job("Bad Job", "https://example.com/bad", db=analyzer_db)
        assert get_job(job.id, db=analyzer_db) is not None

        with patch("pipeline.analyzer.client") as mock_client, \
             patch("pipeline.analyzer.list_jobs", return_value=[get_job(job.id, db=analyzer_db)]), \
             patch("db.jobs.get_db", return_value=analyzer_db):
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = json.dumps(
                self._make_analysis(label="DELETE")
            )
            mock_client.chat.completions.create.return_value = mock_response

            stats = process_jobs()

        assert stats["deleted"] == 1
        assert get_job(job.id, db=analyzer_db) is None

    def test_seattle_label_updates_job(self, analyzer_db):
        from pipeline.analyzer import process_jobs

        job = upsert_job("Good Job", "https://example.com/good", db=analyzer_db)

        with patch("pipeline.analyzer.client") as mock_client, \
             patch("pipeline.analyzer.list_jobs", return_value=[get_job(job.id, db=analyzer_db)]), \
             patch("db.jobs.get_db", return_value=analyzer_db):
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = json.dumps(
                self._make_analysis(label="Seattle")
            )
            mock_client.chat.completions.create.return_value = mock_response

            stats = process_jobs()

        assert stats["seattle"] == 1
        updated = get_job(job.id, db=analyzer_db)
        assert updated.location_label == "Seattle"

    def test_failed_analysis_skips_job(self, analyzer_db):
        from pipeline.analyzer import process_jobs

        job = upsert_job("Fail Job", "https://example.com/fail", db=analyzer_db)

        with patch("pipeline.analyzer.client") as mock_client, \
             patch("pipeline.analyzer.list_jobs", return_value=[get_job(job.id, db=analyzer_db)]):
            mock_client.chat.completions.create.side_effect = ValueError("parse error")

            stats = process_jobs()

        assert stats["failed"] == 1
        # Job should still exist and be unchanged (status='new')
        still_there = get_job(job.id, db=analyzer_db)
        assert still_there is not None
        assert still_there.status == "new"

    def test_fatal_error_aborts_batch(self, analyzer_db):
        from pipeline.analyzer import process_jobs

        job = upsert_job("Fatal Job", "https://example.com/fatal", db=analyzer_db)

        with patch("pipeline.analyzer.client") as mock_client, \
             patch("pipeline.analyzer.list_jobs", return_value=[get_job(job.id, db=analyzer_db)]):
            mock_client.chat.completions.create.side_effect = openai.AuthenticationError(
                message="bad key",
                response=MagicMock(status_code=401),
                body=None,
            )
            with pytest.raises(openai.AuthenticationError):
                process_jobs()

    def test_stats_counts_are_accurate(self, analyzer_db):
        from pipeline.analyzer import process_jobs

        jobs = []
        for i, label in enumerate(["Seattle", "Remote", "Review for location"]):
            j = upsert_job(f"Job {i}", f"https://example.com/{i}", db=analyzer_db)
            jobs.append(get_job(j.id, db=analyzer_db))

        responses = []
        for label in ["Seattle", "Remote", "Review for location"]:
            mock_resp = MagicMock()
            mock_resp.choices = [MagicMock()]
            mock_resp.choices[0].message.content = json.dumps(
                self._make_analysis(label=label)
            )
            responses.append(mock_resp)

        with patch("pipeline.analyzer.client") as mock_client, \
             patch("pipeline.analyzer.list_jobs", return_value=jobs):
            mock_client.chat.completions.create.side_effect = responses

            stats = process_jobs()

        assert stats["seattle"] == 1
        assert stats["remote"] == 1
        assert stats["review"] == 1
        assert stats["deleted"] == 0
        assert stats["failed"] == 0
