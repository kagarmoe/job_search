#!/usr/bin/env python3
"""Project integrity tests.

Ensures critical files and components exist.

Run: python test_project.py
"""

import sys
from pathlib import Path


def test_critical_files_exist():
    """Test that critical project files exist."""
    critical_files = [
        "app.py",
        "job_analyzer.py",
        "run_pipeline.py",
        "rss_job_feed.py",
        "startup_search.py",
        "filter_jobs_by_location.py",
        "profile_import.py",
        "db/connection.py",
        "db/jobs.py",
        "db/models.py",
        "db/profile.py",
        "db/feeds.py",
        "db/schema.py",
        "templates/base.html",
        "templates/index.html",
        "templates/job_detail.html",
        "templates/profile.html",
    ]
    
    missing = []
    for file_path in critical_files:
        if not Path(file_path).exists():
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
    from rss_job_feed import fetch_and_parse_jobs
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
    fake_feed.feed.get = lambda k, d=None: "Test Feed" if k == "title" else d
    fake_feed.entries = [old_entry, new_entry]

    with patch("rss_job_feed.feedparser.parse", return_value=fake_feed):
        # No since — both entries returned
        df_all = fetch_and_parse_jobs("https://example.com/feed.xml")
        assert len(df_all) == 2, f"Expected 2 jobs, got {len(df_all)}"
        print("[PASS] since=None returns all entries")

        # since after old entry — only new entry returned
        cutoff = datetime(2026, 2, 15, 0, 0, 0)
        df_new = fetch_and_parse_jobs(
            "https://example.com/feed.xml",
            since={"https://example.com/feed.xml": cutoff},
        )
        assert len(df_new) == 1, f"Expected 1 job, got {len(df_new)}"
        assert df_new.iloc[0]["Job Title"] == "New Job"
        print("[PASS] since filters out old entries")

        # since after both entries — nothing returned
        cutoff_future = datetime(2026, 3, 1, 0, 0, 0)
        df_none = fetch_and_parse_jobs(
            "https://example.com/feed.xml",
            since={"https://example.com/feed.xml": cutoff_future},
        )
        assert len(df_none) == 0, f"Expected 0 jobs, got {len(df_none)}"
        print("[PASS] since after all entries returns empty DataFrame")

        # since for different URL — no filtering applied
        df_other = fetch_and_parse_jobs(
            "https://example.com/feed.xml",
            since={"https://other.com/feed.xml": cutoff},
        )
        assert len(df_other) == 2, f"Expected 2 jobs, got {len(df_other)}"
        print("[PASS] since for unrelated URL does not filter")

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
