#!/usr/bin/env python3
"""Project integrity and pipeline unit tests.

Validates critical files exist and tests core pipeline components
(RSS parsing, location filtering, deduplication, and pipeline orchestration).

Run: python test_project.py
"""

import sys
from pathlib import Path


def test_critical_files_exist():
    """Test that critical project files exist."""
    project_root = Path(__file__).parent
    critical_files = [
        "app.py",
        "run_pipeline.py",
        "profile_import.py",
        "pipeline/__init__.py",
        "pipeline/constants.py",
        "pipeline/rss.py",
        "pipeline/search.py",
        "pipeline/analyzer.py",
        "pipeline/dedup.py",
        "pipeline/location.py",
        "db/connection.py",
        "db/jobs.py",
        "db/models.py",
        "db/profile.py",
        "db/feeds.py",
        "db/schema.py",
        "db/migrate_001_normalize.py",
        "db/migrate_002_add_passed_status.py",
        "db/migrate_003_rename_reviewed_to_interested.py",
        "templates/base.html",
        "templates/index.html",
        "templates/job_detail.html",
        "templates/profile.html",
    ]

    missing = []
    for file_path in critical_files:
        if not (project_root / file_path).exists():
            missing.append(file_path)
            print(f"[FAIL] Missing critical file: {file_path}")
    
    if missing:
        print(f"\n❌ {len(missing)} critical file(s) missing!")
        return False
    
    print(f"[PASS] All {len(critical_files)} critical files exist")
    return True


def test_app_imports():
    """Test that app.py can be imported."""
    try:
        import app
        print("[PASS] app.py imports successfully")
        return True
    except ImportError as e:
        print(f"[FAIL] Failed to import app.py: {e}")
        return False
    except Exception as e:
        print(f"[FAIL] Error importing app.py: {e}")
        return False


def test_rss_since_filtering():
    """Test that the since parameter filters entries by date."""
    from datetime import datetime
    from unittest.mock import patch, MagicMock
    from pipeline.rss import fetch_and_parse_jobs
    import time

    # Build a fake feed with two entries: one old, one new
    old_time = time.struct_time((2026, 2, 10, 12, 0, 0, 0, 41, 0))
    new_time = time.struct_time((2026, 2, 22, 12, 0, 0, 0, 53, 0))

    old_entry = MagicMock()
    old_entry.published_parsed = old_time
    old_entry.get = lambda k, d=None: {
        "title": "Old Job", "link": "https://example.com/old",
        "summary": "desc", "author": "src",
    }.get(k, d)

    new_entry = MagicMock()
    new_entry.published_parsed = new_time
    new_entry.get = lambda k, d=None: {
        "title": "New Job", "link": "https://example.com/new",
        "summary": "desc", "author": "src",
    }.get(k, d)

    fake_feed = MagicMock()
    fake_feed.bozo = False
    fake_feed.feed.get = lambda k, d=None: "Test Feed" if k == "title" else d
    fake_feed.entries = [old_entry, new_entry]

    with patch("pipeline.rss.feedparser.parse", return_value=fake_feed):
        # No since — both entries returned
        all_jobs = fetch_and_parse_jobs("https://example.com/feed.xml")
        assert len(all_jobs) == 2, f"Expected 2 jobs, got {len(all_jobs)}"
        print("[PASS] since=None returns all entries")

        # since after old entry — only new entry returned
        cutoff = datetime(2026, 2, 15, 0, 0, 0)
        new_jobs = fetch_and_parse_jobs(
            "https://example.com/feed.xml",
            since={"https://example.com/feed.xml": cutoff},
        )
        assert len(new_jobs) == 1, f"Expected 1 job, got {len(new_jobs)}"
        assert new_jobs[0]["Job Title"] == "New Job"
        print("[PASS] since filters out old entries")

        # since after both entries — nothing returned
        cutoff_future = datetime(2026, 3, 1, 0, 0, 0)
        no_jobs = fetch_and_parse_jobs(
            "https://example.com/feed.xml",
            since={"https://example.com/feed.xml": cutoff_future},
        )
        assert len(no_jobs) == 0, f"Expected 0 jobs, got {len(no_jobs)}"
        print("[PASS] since after all entries returns empty list")

        # since for different URL — no filtering applied
        other_jobs = fetch_and_parse_jobs(
            "https://example.com/feed.xml",
            since={"https://other.com/feed.xml": cutoff},
        )
        assert len(other_jobs) == 2, f"Expected 2 jobs, got {len(other_jobs)}"
        print("[PASS] since for unrelated URL does not filter")

    return True


def test_location_filtering():
    """Test is_seattle, is_us_wide, and is_truly_remote helpers."""
    from pipeline.location import (
        is_seattle, is_us_wide, is_truly_remote, SEATTLE_METRO,
    )

    # ── SEATTLE_METRO list completeness ──────────────────────────
    expected_cities = {
        "Seattle", "Bellevue", "Redmond", "Kirkland", "Bothell",
        "Renton", "Kent", "Federal Way", "Sammamish", "Issaquah",
        "Tacoma", "Olympia",
    }
    assert set(SEATTLE_METRO) == expected_cities, (
        f"SEATTLE_METRO mismatch: missing={expected_cities - set(SEATTLE_METRO)}, "
        f"extra={set(SEATTLE_METRO) - expected_cities}"
    )
    print(f"[PASS] SEATTLE_METRO contains all {len(expected_cities)} expected cities")

    # ── is_seattle: every metro city in common title formats ─────
    for city in SEATTLE_METRO:
        assert is_seattle(f"Technical Writer in {city}, WA - Acme Corp"), (
            f"is_seattle should match 'in {city}, WA - ...' but didn't"
        )
        assert is_seattle(f"Technical Writer in {city}, WA"), (
            f"is_seattle should match 'in {city}, WA' at end but didn't"
        )
        assert is_seattle(f"Data Librarian ({city}, WA)"), (
            f"is_seattle should match '({city}, WA)' but didn't"
        )
        assert is_seattle(f"Writer - {city}, WA"), (
            f"is_seattle should match '- {city}, WA' but didn't"
        )
    print("[PASS] is_seattle() matches all SEATTLE_METRO cities in multiple title formats")

    # ── is_seattle: non-metro cities should NOT match ────────────
    assert not is_seattle("Technical Writer in San Francisco, CA")
    assert not is_seattle("Technical Writer in Portland, OR")
    assert not is_seattle("Technical Writer - Remote")
    assert not is_seattle("Technical Writer")
    assert not is_seattle("Technical Writer in Kent, OH")  # Kent OH, not Kent WA
    print("[PASS] is_seattle() rejects non-metro cities")

    # ── is_us_wide ───────────────────────────────────────────────
    assert is_us_wide("Senior Writer in United States")
    assert not is_us_wide("Senior Writer in Seattle, WA")
    assert not is_us_wide("United States - Senior Writer")  # not at end
    print("[PASS] is_us_wide() works correctly")

    # ── is_truly_remote: positive description patterns ────────────
    remote_descriptions = [
        "This is a fully remote position.",
        "Location: Remote",
        "Role type: remote",
        "This is a remote position open to candidates in the USA.",
        "100% remote work environment.",
        "This role is completely remote.",
        "This role is entirely remote.",
        "This is listed as remote on our job board.",
        "Remote if located in the US.",
        "remote work opportunity for qualified candidates.",
    ]
    for desc in remote_descriptions:
        assert is_truly_remote(desc), f"Should be remote: '{desc}'"
    print(f"[PASS] is_truly_remote() matches {len(remote_descriptions)} positive description patterns")

    # ── is_truly_remote: positive title patterns ─────────────────
    remote_titles = [
        ("Technical Writer (Remote - US) in Denver, CO", "Some description."),
        ("Technical Writer (Remote)", "Some description."),
        ("Sr. Manager, Technical Writer - Remote", "Some description."),
        ("Content Writer | Remote", "Some description."),
        ("Remote Technical Writer", "Some description."),
    ]
    for title, desc in remote_titles:
        assert is_truly_remote(desc, title), f"Should be remote via title: '{title}'"
    print(f"[PASS] is_truly_remote() matches {len(remote_titles)} positive title patterns")

    # ── is_truly_remote: negative / non-matching ─────────────────
    not_remote = [
        "This is not a remote position.",
        "We do not offer remote work.",
        "Remote operations manager needed on-site.",
        "Remote sensing specialist required.",
        "Not a remote role.",
        "Great office in downtown Seattle.",
        "",
    ]
    for desc in not_remote:
        assert not is_truly_remote(desc), f"Should NOT be remote: '{desc}'"
    print(f"[PASS] is_truly_remote() rejects {len(not_remote)} negative/non-remote descriptions")

    # ── is_truly_remote: negative title patterns ─────────────────
    assert not is_truly_remote("Some description.", "Remote Operations Manager in NYC, NY")
    assert not is_truly_remote("Some description.", "Remote Sensing Analyst")
    assert not is_truly_remote("Some description.", "Remote Control Engineer")
    print("[PASS] is_truly_remote() rejects negative title patterns")

    # ── is_truly_remote: empty/None ──────────────────────────────
    assert not is_truly_remote("")
    assert not is_truly_remote(None)
    print("[PASS] is_truly_remote() handles empty/None")

    return True


def test_seattle_metro_consistency():
    """Test that SEATTLE_METRO is shared from pipeline.constants."""
    from pipeline.constants import SEATTLE_METRO
    from pipeline.location import SEATTLE_METRO as LOC_METRO

    assert LOC_METRO is SEATTLE_METRO, (
        "pipeline.location should import SEATTLE_METRO from pipeline.constants"
    )
    print("[PASS] SEATTLE_METRO is shared from pipeline.constants")
    return True


def test_normalize_title():
    """Test that normalize_title strips location suffixes but preserves company info."""
    from pipeline.dedup import normalize_title

    # "in City, ST" suffix stripped
    assert normalize_title("Technical Writer in Seattle, WA") == "Technical Writer"
    assert normalize_title("Data Analyst in San Francisco, CA - Acme Corp") == "Data Analyst"

    # "(City, ST)" suffix stripped
    assert normalize_title("Sr Engineer (Bellevue, WA)") == "Sr Engineer"

    # "in United States" stripped
    assert normalize_title("Content Writer in United States") == "Content Writer"

    # No location — unchanged
    assert normalize_title("Technical Writer") == "Technical Writer"
    assert normalize_title("Remote Technical Writer") == "Remote Technical Writer"

    # Company prefix preserved (different companies = not duplicates)
    assert normalize_title("Acme Corp - Writer in Seattle, WA") == "Acme Corp - Writer"
    assert normalize_title("Beta Inc - Writer in Portland, OR") == "Beta Inc - Writer"

    print("[PASS] normalize_title() strips location suffixes correctly")
    return True


def test_rss_dedup():
    """Test that fetch_and_parse_jobs deduplicates entries with same title+URL."""
    from unittest.mock import patch, MagicMock
    from pipeline.rss import fetch_and_parse_jobs
    import time

    pub_time = time.struct_time((2026, 2, 20, 12, 0, 0, 0, 51, 0))

    def make_entry(title, link):
        entry = MagicMock()
        entry.published_parsed = pub_time
        entry.get = lambda k, d=None: {
            "title": title, "link": link,
            "summary": "desc", "author": "src",
        }.get(k, d)
        return entry

    # Two entries with identical title+URL
    entry_a = make_entry("Same Job", "https://example.com/job1")
    entry_b = make_entry("Same Job", "https://example.com/job1")
    # One entry with different URL
    entry_c = make_entry("Same Job", "https://example.com/job2")

    fake_feed = MagicMock()
    fake_feed.bozo = False
    fake_feed.feed.get = lambda k, d=None: "Test Feed" if k == "title" else d
    fake_feed.entries = [entry_a, entry_b, entry_c]

    with patch("pipeline.rss.feedparser.parse", return_value=fake_feed):
        jobs = fetch_and_parse_jobs("https://example.com/feed.xml")

    assert len(jobs) == 2, f"Expected 2 unique jobs, got {len(jobs)}"
    urls = {j["URL"] for j in jobs}
    assert urls == {"https://example.com/job1", "https://example.com/job2"}
    print("[PASS] RSS deduplicates entries with same title+URL")
    return True


def test_run_pipeline_calls_job_analyzer():
    """Test that run_pipeline() calls process_jobs from pipeline.analyzer."""
    from unittest.mock import patch, MagicMock
    import run_pipeline as rp

    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = [0]

    with patch.object(rp, 'run_rss_fetch', return_value=(0, 0)), \
         patch.object(rp, 'run_web_search', return_value=(0, 0)), \
         patch('pipeline.analyzer.process_jobs') as mock_process_jobs:
        rp.run_pipeline(conn=mock_conn)

    mock_process_jobs.assert_called_once_with(dry_run=False)
    print("[PASS] run_pipeline() calls process_jobs")
    return True


def main():
    """Run all project tests."""
    print("=" * 60)
    print("Project Integrity Tests")
    print("=" * 60)

    tests = [
        test_critical_files_exist,
        test_app_imports,
        test_rss_since_filtering,
        test_location_filtering,
        test_seattle_metro_consistency,
        test_normalize_title,
        test_rss_dedup,
        test_run_pipeline_calls_job_analyzer,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"[FAIL] Test {test.__name__} crashed: {e}")
            results.append(False)
        print()
    
    # Summary
    passed = sum(results)
    total = len(results)
    
    print("=" * 60)
    if all(results):
        print(f"✅ All {total} tests passed!")
        return 0
    else:
        print(f"❌ {total - passed}/{total} tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
