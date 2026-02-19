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


def main():
    """Run all project tests."""
    print("=" * 60)
    print("Project Integrity Tests")
    print("=" * 60)
    
    tests = [
        test_critical_files_exist,
        test_app_imports,
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
