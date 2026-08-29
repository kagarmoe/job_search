#!/usr/bin/env python3
"""Test CleanJobData API record -> RSS-shaped dict mapping. No network."""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.cleanjobdata import map_job

# Trimmed from a live API probe (cjd_probe_1.json)
SAMPLE_RECORD = {
    "id": "85373028",
    "title": "Senior Technical Writer",
    "location": "USA - Remote",
    "application_url": "https://job-boards.greenhouse.io/pingidentity/jobs/8731505002",
    "published": "2026-08-27T18:14:36.000Z",
    "has_remote": True,
    "salary_min": 95000,
    "salary_max": 115000,
    "salary_text": "$95,000–$115,000",
    "company": {"name": "Ping Identity"},
    "description": "<div><p><strong>About Ping Identity:</strong></p></div>",
}


def test_map_job_shape():
    """map_job produces the exact dict shape rss.py produces."""
    job = map_job(SAMPLE_RECORD, "technical writer")

    expected_keys = {
        "Job Title", "URL", "Description", "Posted Date",
        "Source", "Feed", "Feed URL",
    }
    if set(job.keys()) != expected_keys:
        print(f"  FAIL: keys mismatch: {sorted(job.keys())}")
        return False
    if job["Job Title"] != "Senior Technical Writer":
        print(f"  FAIL: Job Title = {job['Job Title']!r}")
        return False
    if job["URL"] != SAMPLE_RECORD["application_url"]:
        print(f"  FAIL: URL = {job['URL']!r}")
        return False
    if job["Posted Date"] != datetime(2026, 8, 27, 18, 14, 36):
        print(f"  FAIL: Posted Date = {job['Posted Date']!r} (want naive datetime)")
        return False
    if job["Source"] != "CleanJobData":
        print(f"  FAIL: Source = {job['Source']!r}")
        return False
    if job["Feed"] != "technical writer":
        print(f"  FAIL: Feed = {job['Feed']!r}")
        return False
    if job["Feed URL"] != "cleanjobdata:technical writer":
        print(f"  FAIL: Feed URL = {job['Feed URL']!r}")
        return False
    # Missing fields must not crash and must yield the rss.py defaults
    minimal = map_job({}, "taxonomy")
    if minimal["Job Title"] != "N/A" or minimal["URL"] != "N/A":
        print("  FAIL: missing fields should default to 'N/A'")
        return False
    if not isinstance(minimal["Posted Date"], datetime):
        print("  FAIL: Posted Date must be a datetime even when unparseable")
        return False
    return True


def main():
    tests = [("map_job output shape", test_map_job_shape)]
    failed = 0
    for name, fn in tests:
        print(f"Running: {name}")
        if fn():
            print("  PASS")
        else:
            failed += 1
    if failed:
        print(f"\n{failed} test(s) failed")
        return 1
    print("\nAll tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
