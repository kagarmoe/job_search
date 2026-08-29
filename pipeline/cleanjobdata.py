"""Fetch job listings from the CleanJobData API.

Returns job dicts in the same shape as pipeline.rss.fetch_and_parse_jobs
so the existing upsert/analyzer path can be reused unchanged.
"""

import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime
from urllib.error import HTTPError

API_URL = "https://api.cleanjobdata.com/jobs"

# Mirrors pipeline.search.ROLE_TITLES
QUERIES = ["technical writer", "taxonomy", "information architecture"]

REQUEST_SPACING_SECONDS = 12  # be polite; API 429s on rapid requests
RETRY_429_SECONDS = 45


def _api_key() -> str:
    key = os.environ.get("CLEANJOBDATA_API_KEY")
    if not key:
        raise RuntimeError(
            "CLEANJOBDATA_API_KEY environment variable is not set. "
            "Export it (it lives in ~/.zshrc) before running the CleanJobData fetch."
        )
    return key


def _parse_published(value) -> datetime:
    """Parse an ISO timestamp like '2026-08-27T18:14:36.000Z' to naive datetime."""
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.replace(tzinfo=None)
    except (ValueError, TypeError):
        return datetime.now()


def map_job(record: dict, query: str) -> dict:
    """Map one CleanJobData API record to the RSS-pipeline dict shape."""
    return {
        "Job Title": record.get("title", "N/A"),
        "URL": record.get("application_url", "N/A"),
        "Description": record.get("description", "N/A"),
        "Posted Date": _parse_published(record.get("published")),
        "Source": "CleanJobData",
        "Feed": query,
        "Feed URL": f"cleanjobdata:{query}",
    }


def _get(params: dict) -> dict:
    url = f"{API_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {_api_key()}",
            # WAF returns 403 to urllib's default Python-urllib/3.x user-agent
            "User-Agent": "job-search-pipeline/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.load(resp)
    except HTTPError as e:
        if e.code == 429:
            print(f"CleanJobData rate limited; retrying in {RETRY_429_SECONDS}s")
            time.sleep(RETRY_429_SECONDS)
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.load(resp)
        raise


def fetch_jobs(queries=QUERIES, since=None):
    """Fetch jobs from CleanJobData for each query keyword.

    Args:
        queries: List of title keywords to search.
        since: Dict mapping query -> datetime cutoff (from per-feed last-fetch).
               Queries not in the dict fall back to max_age=7d.

    Returns:
        List of RSS-shaped job dicts, deduplicated by URL, newest-first.
    """
    if since is None:
        since = {}

    jobs = []
    seen_urls = set()

    for i, query in enumerate(queries):
        if i:
            time.sleep(REQUEST_SPACING_SECONDS)

        # City-level location filtering is broken server-side (silently dropped),
        # so we fetch US remote jobs and let the analyzer do location triage —
        # same as the RSS path.
        params = {
            "title": query,
            "location": "US",
            "remote": "true",
            "limit": 50,
            "extra_fields": "description",
        }
        cutoff = since.get(query)
        if cutoff:
            params["published_after"] = cutoff.isoformat()
            print(f"CleanJobData query: {query!r} (since {cutoff.isoformat()})")
        else:
            params["max_age"] = "7d"
            print(f"CleanJobData query: {query!r} (full fetch, 7d)")

        try:
            data = _get(params)
        except Exception as e:
            print(f"WARNING: CleanJobData fetch failed for {query!r}: {e}")
            continue

        for record in data.get("data", []):
            job = map_job(record, query)
            if job["URL"] in seen_urls:
                continue
            seen_urls.add(job["URL"])
            jobs.append(job)

    jobs.sort(key=lambda j: j["Posted Date"], reverse=True)
    return jobs
