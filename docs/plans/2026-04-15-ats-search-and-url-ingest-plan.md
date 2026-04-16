# ATS Search & Manual URL Ingest — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add two new pipeline sources — automated Greenhouse/Ashby search and manual URL ingest — so jobs from ATS platforms are discovered automatically and ad-hoc URLs can be added via CLI or web UI.

**Architecture:** New `pipeline/ats_search.py` module reuses the OpenAI web search pattern from `pipeline/search.py` with `allowed_domains` filters. New `pipeline/ingest.py` fetches a single URL via `httpx` and extracts title/description. Both integrate into `run_pipeline.py` via new CLI flags and `app.py` via a new route.

**Tech Stack:** OpenAI web search (existing), httpx (existing dep), Flask, SQLite, pytest

---

### Task 1: ATS Search Module — Tests

**Files:**
- Create: `tests/test_ats_search.py`

**Step 1: Write tests for `search_ats_platform()`**

```python
"""Tests for pipeline/ats_search.py."""

import json
from unittest.mock import patch, MagicMock

import pytest


class TestSearchAtsPlatform:
    def _mock_response(self, text):
        mock_resp = MagicMock()
        item = MagicMock()
        item.type = "message"
        content = MagicMock()
        content.type = "output_text"
        content.text = text
        item.content = [content]
        mock_resp.output = [item]
        return mock_resp

    def test_returns_parsed_jobs(self):
        from pipeline.ats_search import search_ats_platform

        jobs_json = json.dumps([
            {"title": "Technical Writer", "url": "https://job-boards.greenhouse.io/acme/jobs/123", "company": "Acme"},
        ])

        with patch("pipeline.ats_search.client") as mock_client:
            mock_client.responses.create.return_value = self._mock_response(jobs_json)
            jobs = search_ats_platform("greenhouse.io")

        assert len(jobs) == 1
        assert jobs[0]["url"] == "https://job-boards.greenhouse.io/acme/jobs/123"
        assert jobs[0]["source"] == "Greenhouse"

    def test_filters_out_wrong_domain(self):
        from pipeline.ats_search import search_ats_platform

        jobs_json = json.dumps([
            {"title": "Good", "url": "https://job-boards.greenhouse.io/acme/jobs/1", "company": "Acme"},
            {"title": "Bad", "url": "https://linkedin.com/jobs/view/999", "company": "Other"},
        ])

        with patch("pipeline.ats_search.client") as mock_client:
            mock_client.responses.create.return_value = self._mock_response(jobs_json)
            jobs = search_ats_platform("greenhouse.io")

        assert len(jobs) == 1
        assert "greenhouse.io" in jobs[0]["url"]

    def test_empty_results(self):
        from pipeline.ats_search import search_ats_platform

        with patch("pipeline.ats_search.client") as mock_client:
            mock_client.responses.create.return_value = self._mock_response("[]")
            jobs = search_ats_platform("greenhouse.io")

        assert jobs == []

    def test_includes_since_date_in_query(self):
        from pipeline.ats_search import search_ats_platform
        from datetime import datetime

        since = datetime(2026, 4, 10)

        with patch("pipeline.ats_search.client") as mock_client:
            mock_client.responses.create.return_value = self._mock_response("[]")
            search_ats_platform("greenhouse.io", since=since)

        call_args = mock_client.responses.create.call_args
        assert "April 10, 2026" in call_args.kwargs["input"]

    def test_ashby_domain(self):
        from pipeline.ats_search import search_ats_platform

        jobs_json = json.dumps([
            {"title": "Writer", "url": "https://jobs.ashbyhq.com/vapi/abc-123", "company": "Vapi"},
        ])

        with patch("pipeline.ats_search.client") as mock_client:
            mock_client.responses.create.return_value = self._mock_response(jobs_json)
            jobs = search_ats_platform("ashbyhq.com")

        assert len(jobs) == 1
        assert jobs[0]["source"] == "Ashby"


class TestSearchAllPlatforms:
    def test_combines_results_from_all_platforms(self):
        from pipeline.ats_search import search_all_platforms

        with patch("pipeline.ats_search.search_ats_platform") as mock_search:
            mock_search.side_effect = [
                [{"title": "GH Job", "url": "https://greenhouse.io/1", "company": "A", "source": "Greenhouse", "feed": "Greenhouse Search"}],
                [{"title": "Ashby Job", "url": "https://ashbyhq.com/2", "company": "B", "source": "Ashby", "feed": "Ashby Search"}],
            ]
            jobs = search_all_platforms()

        assert len(jobs) == 2
        assert mock_search.call_count == 2
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_ats_search.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline.ats_search'`

**Step 3: Commit**

```bash
git add tests/test_ats_search.py
git commit -m "test: add tests for ATS search module"
```

---

### Task 2: ATS Search Module — Implementation

**Files:**
- Create: `pipeline/ats_search.py`

**Step 1: Implement the module**

```python
"""Search ATS platforms (Greenhouse, Ashby) for job postings.

Uses OpenAI web search with allowed_domains filter to find
technical writer postings on each platform.
"""

from datetime import datetime
from openai import OpenAI
from pipeline.search import parse_json_response

client = OpenAI()

# ATS platforms: (domain, source_name, feed_name)
ATS_PLATFORMS = [
    ("greenhouse.io", "Greenhouse", "Greenhouse Search"),
    ("ashbyhq.com", "Ashby", "Ashby Search"),
]

JSON_INSTRUCTIONS = """
Return ONLY a valid JSON array (no markdown, no preamble). Each element:
{
  "title": "Job Title",
  "url": "direct URL to the job posting",
  "company": "Company Name"
}
If no results found, return an empty array: []
"""


def search_ats_platform(
    domain: str,
    since: datetime | None = None,
) -> list[dict]:
    """Search a single ATS platform for technical writer postings.

    Args:
        domain: The ATS domain to search (e.g. "greenhouse.io").
        since: Only return postings after this date.

    Returns:
        List of dicts with keys: title, url, company, source, feed.
    """
    # Find platform config
    source_name = domain.split(".")[0].capitalize()
    feed_name = f"{source_name} Search"
    for d, s, f in ATS_PLATFORMS:
        if d == domain:
            source_name = s
            feed_name = f
            break

    date_clause = ""
    if since:
        date_clause = f" posted since {since.strftime('%B %d, %Y')}"

    query = (
        f'Search for all "technical writer" job postings on {domain}'
        f"{date_clause}. "
        f"{JSON_INSTRUCTIONS}"
    )

    response = client.responses.create(
        model="gpt-4.1",
        tools=[{
            "type": "web_search",
            "filters": {"allowed_domains": [domain]},
        }],
        input=query,
    )

    # Extract text from response
    text_parts = []
    for item in response.output:
        if getattr(item, "type", None) == "message":
            for content in getattr(item, "content", []):
                if getattr(content, "type", None) in ("output_text", "text"):
                    text_parts.append(content.text)

    raw = "\n".join(text_parts)
    if not raw.strip():
        print(f"WARNING: ATS search returned no content for {domain}")
        return []

    try:
        jobs = parse_json_response(raw)
    except Exception as e:
        print(f"ERROR: Could not parse ATS search response for {domain}: {e}")
        return []

    # Filter: only keep URLs that actually contain the target domain
    filtered = []
    for job in jobs:
        url = job.get("url", "")
        if domain not in url:
            print(f"WARNING: Filtering out off-domain result: {url}")
            continue
        job["source"] = source_name
        job["feed"] = feed_name
        filtered.append(job)

    print(f"Found {len(filtered)} jobs on {domain} ({len(jobs) - len(filtered)} filtered out)")
    return filtered


def search_all_platforms(
    since: dict[str, datetime] | None = None,
) -> list[dict]:
    """Search all configured ATS platforms.

    Args:
        since: Dict mapping feed name to last-fetch datetime.

    Returns:
        Combined list of jobs from all platforms.
    """
    if since is None:
        since = {}

    all_jobs = []
    for domain, source_name, feed_name in ATS_PLATFORMS:
        cutoff = since.get(feed_name)
        if cutoff:
            print(f"Searching {domain} (since {cutoff.strftime('%Y-%m-%d')})...")
        else:
            print(f"Searching {domain} (full search)...")

        try:
            jobs = search_ats_platform(domain, since=cutoff)
            all_jobs.extend(jobs)
        except Exception as e:
            print(f"ERROR: ATS search failed for {domain}: {type(e).__name__}: {e}")

    return all_jobs
```

**Step 2: Run tests to verify they pass**

Run: `python -m pytest tests/test_ats_search.py -v`
Expected: All 6 tests PASS

**Step 3: Commit**

```bash
git add pipeline/ats_search.py
git commit -m "feat: add ATS search module for Greenhouse and Ashby"
```

---

### Task 3: Integrate ATS Search into Pipeline

**Files:**
- Modify: `run_pipeline.py`

**Step 1: Write the test**

Add to `test_project.py` or create `tests/test_pipeline_integration.py`:

```python
"""Tests for ATS search pipeline integration."""

from unittest.mock import patch, MagicMock


def test_run_pipeline_calls_ats_search():
    import run_pipeline as rp

    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = [0]

    with patch.object(rp, "run_rss_fetch", return_value=(0, 0)), \
         patch.object(rp, "run_web_search", return_value=(0, 0)), \
         patch.object(rp, "run_ats_search", return_value=(0, 0)) as mock_ats, \
         patch("pipeline.analyzer.process_jobs"):
        rp.run_pipeline(conn=mock_conn)

    mock_ats.assert_called_once_with(mock_conn)


def test_run_pipeline_skips_ats_with_rss_only():
    import run_pipeline as rp

    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = [0]

    with patch.object(rp, "run_rss_fetch", return_value=(0, 0)), \
         patch.object(rp, "run_ats_search", return_value=(0, 0)) as mock_ats, \
         patch("pipeline.analyzer.process_jobs"):
        rp.run_pipeline(conn=mock_conn, rss_only=True)

    mock_ats.assert_not_called()


def test_run_pipeline_ats_only():
    import run_pipeline as rp

    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = [0]

    with patch.object(rp, "run_rss_fetch", return_value=(0, 0)) as mock_rss, \
         patch.object(rp, "run_web_search", return_value=(0, 0)) as mock_web, \
         patch.object(rp, "run_ats_search", return_value=(0, 0)) as mock_ats, \
         patch("pipeline.analyzer.process_jobs"):
        rp.run_pipeline(conn=mock_conn, ats_only=True)

    mock_rss.assert_not_called()
    mock_web.assert_not_called()
    mock_ats.assert_called_once_with(mock_conn)
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_pipeline_integration.py -v`
Expected: FAIL — `run_pipeline` has no `run_ats_search` or `ats_only` parameter

**Step 3: Add `run_ats_search()` and integrate into `run_pipeline()`**

Add `run_ats_search()` to `run_pipeline.py` following the same pattern as `run_web_search()`:

```python
def run_ats_search(conn) -> tuple[int, int]:
    """Search ATS platforms for jobs and store to database.

    Returns:
        Tuple of (jobs_found, jobs_upserted)
    """
    print("\n" + "=" * 60)
    print("ATS PLATFORM SEARCH")
    print("=" * 60)

    try:
        from pipeline.ats_search import search_all_platforms, ATS_PLATFORMS
    except ImportError as e:
        print(f"ERROR: Failed to import pipeline.ats_search: {e}")
        return 0, 0

    # Load last-fetch timestamps for ATS feeds
    since = get_all_last_fetches(db=conn)
    # Map feed names to their timestamps
    ats_since = {}
    for domain, source_name, feed_name in ATS_PLATFORMS:
        for url, ts in since.items():
            if feed_name.lower() in url.lower():
                ats_since[feed_name] = ts
                break

    try:
        jobs = search_all_platforms(since=ats_since)
    except Exception as e:
        print(f"ERROR: ATS search failed ({type(e).__name__}): {e}")
        return 0, 0

    if not jobs:
        print("No jobs found from ATS platforms")
        return 0, 0

    print(f"\nFound {len(jobs)} jobs from ATS platforms")

    upserted = 0
    failures = 0
    for job in jobs:
        if not job.get("url"):
            print(f"WARNING: Skipping ATS result with no URL: {job.get('title', 'unknown')}")
            continue
        try:
            upsert_job(
                title=job.get("title", ""),
                url=job["url"],
                description=job.get("description"),
                source=job.get("source", "ATS"),
                feed=job.get("feed", "ATS Search"),
                db=conn,
            )
            upserted += 1
        except Exception as e:
            failures += 1
            print(f"Error upserting job {job.get('url')}: {e}")
            if failures > 5:
                print(f"ERROR: Too many upsert failures ({failures}), aborting ATS store")
                break

    # Update last_fetch for each ATS feed
    now = datetime.now()
    for domain, source_name, feed_name in ATS_PLATFORMS:
        set_last_fetch(feed_name, now, db=conn)

    print(f"Stored {upserted} jobs from ATS platforms")
    return len(jobs), upserted
```

Update `run_pipeline()` signature and body — add `ats_only` parameter:

```python
def run_pipeline(conn=None, rss_only=False, search_only=False, ats_only=False, skip_analyzer=False):
```

In the body, after the web search block and before the analyzer:

```python
    if not rss_only and not search_only:
        ats_fetched, ats_upserted = run_ats_search(conn)
        total_fetched += ats_fetched
        total_upserted += ats_upserted
```

For `ats_only`, wrap RSS and web search in `if not ats_only:` and always run ATS when `ats_only`.

Add `--ats-only` CLI flag in `main()`.

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_pipeline_integration.py tests/test_ats_search.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add run_pipeline.py tests/test_pipeline_integration.py
git commit -m "feat: integrate ATS search into pipeline with --ats-only flag"
```

---

### Task 4: Manual URL Ingest — Tests

**Files:**
- Create: `tests/test_ingest.py`

**Step 1: Write tests**

```python
"""Tests for pipeline/ingest.py."""

from unittest.mock import patch, MagicMock

import pytest


class TestIngestUrl:
    def _mock_httpx_response(self, html, status_code=200):
        mock = MagicMock()
        mock.status_code = status_code
        mock.text = html
        mock.raise_for_status = MagicMock()
        if status_code >= 400:
            mock.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
        return mock

    def test_extracts_title_from_html(self):
        from pipeline.ingest import fetch_job_from_url

        html = "<html><head><title>Technical Writer at Acme - Greenhouse</title></head><body><p>Write docs</p></body></html>"

        with patch("pipeline.ingest.httpx.get", return_value=self._mock_httpx_response(html)):
            result = fetch_job_from_url("https://job-boards.greenhouse.io/acme/jobs/123")

        assert "Technical Writer" in result["title"]
        assert result["url"] == "https://job-boards.greenhouse.io/acme/jobs/123"
        assert result["source"] == "Greenhouse"

    def test_derives_source_from_greenhouse_url(self):
        from pipeline.ingest import fetch_job_from_url

        html = "<html><head><title>Writer</title></head><body>Desc</body></html>"

        with patch("pipeline.ingest.httpx.get", return_value=self._mock_httpx_response(html)):
            result = fetch_job_from_url("https://job-boards.greenhouse.io/co/jobs/1")

        assert result["source"] == "Greenhouse"

    def test_derives_source_from_ashby_url(self):
        from pipeline.ingest import fetch_job_from_url

        html = "<html><head><title>Writer</title></head><body>Desc</body></html>"

        with patch("pipeline.ingest.httpx.get", return_value=self._mock_httpx_response(html)):
            result = fetch_job_from_url("https://jobs.ashbyhq.com/company/abc")

        assert result["source"] == "Ashby"

    def test_unknown_domain_uses_domain_as_source(self):
        from pipeline.ingest import fetch_job_from_url

        html = "<html><head><title>Writer</title></head><body>Desc</body></html>"

        with patch("pipeline.ingest.httpx.get", return_value=self._mock_httpx_response(html)):
            result = fetch_job_from_url("https://careers.example.com/jobs/1")

        assert result["source"] == "careers.example.com"

    def test_http_error_raises(self):
        from pipeline.ingest import fetch_job_from_url

        with patch("pipeline.ingest.httpx.get", return_value=self._mock_httpx_response("", status_code=404)):
            with pytest.raises(Exception):
                fetch_job_from_url("https://example.com/bad")
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_ingest.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline.ingest'`

**Step 3: Commit**

```bash
git add tests/test_ingest.py
git commit -m "test: add tests for manual URL ingest"
```

---

### Task 5: Manual URL Ingest — Implementation

**Files:**
- Create: `pipeline/ingest.py`

**Step 1: Implement the module**

```python
"""Ingest a single job posting by URL.

Fetches the page, extracts title and description, and returns
a dict ready for upsert_job().
"""

import re
from urllib.parse import urlparse

import httpx

# Map domain patterns to source names
_DOMAIN_SOURCES = {
    "greenhouse.io": "Greenhouse",
    "ashbyhq.com": "Ashby",
    "lever.co": "Lever",
}


def _derive_source(url: str) -> str:
    """Derive a human-readable source name from a URL's domain."""
    hostname = urlparse(url).hostname or ""
    for pattern, name in _DOMAIN_SOURCES.items():
        if pattern in hostname:
            return name
    return hostname


def _extract_title(html: str) -> str:
    """Extract the page title from HTML."""
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if match:
        title = match.group(1).strip()
        # Clean common suffixes like " - Greenhouse", " | Ashby"
        title = re.sub(r"\s*[-|–]\s*(Greenhouse|Ashby|Lever).*$", "", title, flags=re.IGNORECASE)
        return title
    return "Untitled"


def _extract_body_text(html: str) -> str:
    """Extract visible text from HTML body."""
    # Remove script and style blocks
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.IGNORECASE | re.DOTALL)
    # Strip tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text[:10000]  # Cap at 10k chars


def fetch_job_from_url(url: str) -> dict:
    """Fetch a job posting page and extract basic data.

    Args:
        url: Full URL of the job posting.

    Returns:
        Dict with keys: title, url, description, source, feed.

    Raises:
        On HTTP errors or connection failures.
    """
    resp = httpx.get(url, follow_redirects=True, timeout=30)
    resp.raise_for_status()

    html = resp.text
    title = _extract_title(html)
    description = _extract_body_text(html)
    source = _derive_source(url)

    return {
        "title": title,
        "url": url,
        "description": description,
        "source": source,
        "feed": "Manual Ingest",
    }
```

**Step 2: Run tests to verify they pass**

Run: `python -m pytest tests/test_ingest.py -v`
Expected: All 5 tests PASS

**Step 3: Commit**

```bash
git add pipeline/ingest.py
git commit -m "feat: add manual URL ingest module"
```

---

### Task 6: Add `--ingest-url` CLI Flag

**Files:**
- Modify: `run_pipeline.py`
- Create: `tests/test_ingest_cli.py`

**Step 1: Write the test**

```python
"""Tests for --ingest-url CLI integration."""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from db.connection import init_db, close_db
from db.jobs import get_job_by_url


def test_ingest_url_stores_job():
    import run_pipeline as rp

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        conn = init_db(db_path)

        mock_result = {
            "title": "Technical Writer",
            "url": "https://job-boards.greenhouse.io/acme/jobs/123",
            "description": "Write docs",
            "source": "Greenhouse",
            "feed": "Manual Ingest",
        }

        with patch("pipeline.ingest.fetch_job_from_url", return_value=mock_result):
            rp.ingest_url("https://job-boards.greenhouse.io/acme/jobs/123", conn)

        job = get_job_by_url("https://job-boards.greenhouse.io/acme/jobs/123", db=conn)
        assert job is not None
        assert job.title == "Technical Writer"
        assert job.source == "Greenhouse"
    finally:
        close_db()
        Path(db_path).unlink(missing_ok=True)
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ingest_cli.py -v`
Expected: FAIL — `run_pipeline` has no `ingest_url` function

**Step 3: Add `ingest_url()` function and CLI flag**

Add to `run_pipeline.py`:

```python
def ingest_url(url: str, conn) -> None:
    """Fetch a single URL and store it as a job."""
    from pipeline.ingest import fetch_job_from_url

    print(f"Ingesting: {url}")
    job_data = fetch_job_from_url(url)

    upsert_job(
        title=job_data["title"],
        url=job_data["url"],
        description=job_data.get("description"),
        source=job_data.get("source", "Manual"),
        feed=job_data.get("feed", "Manual Ingest"),
        db=conn,
    )
    print(f"Stored: {job_data['title']} ({job_data['source']})")
```

Add to the argparse in `main()`:

```python
parser.add_argument(
    "--ingest-url",
    type=str,
    help="Ingest a single job posting URL and exit",
)
```

In `main()`, before `run_pipeline()`:

```python
if args.ingest_url:
    ingest_url(args.ingest_url, conn)
    return  # Exit without running the full pipeline
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_ingest_cli.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add run_pipeline.py tests/test_ingest_cli.py
git commit -m "feat: add --ingest-url CLI flag for manual URL ingest"
```

---

### Task 7: Web UI Ingest Route

**Files:**
- Modify: `app.py`
- Modify: `templates/base.html`
- Create: `tests/test_ingest_route.py`

**Step 1: Write the test**

```python
"""Tests for POST /ingest route."""

from unittest.mock import patch


class TestIngestRoute:
    def test_ingest_valid_url(self, app_client, db_conn):
        mock_result = {
            "title": "Technical Writer at Acme",
            "url": "https://job-boards.greenhouse.io/acme/jobs/123",
            "description": "Write docs",
            "source": "Greenhouse",
            "feed": "Manual Ingest",
        }

        with patch("app.fetch_job_from_url", return_value=mock_result):
            resp = app_client.post("/ingest", data={"url": "https://job-boards.greenhouse.io/acme/jobs/123"})

        assert resp.status_code == 302  # redirect to job detail

    def test_ingest_missing_url_returns_400(self, app_client):
        resp = app_client.post("/ingest", data={})
        assert resp.status_code == 400

    def test_ingest_empty_url_returns_400(self, app_client):
        resp = app_client.post("/ingest", data={"url": ""})
        assert resp.status_code == 400
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ingest_route.py -v`
Expected: FAIL — 404, route doesn't exist

**Step 3: Add the route to `app.py`**

Add import at top of `app.py`:

```python
from db.jobs import upsert_job  # add to existing imports
```

Add the route:

```python
@app.route('/ingest', methods=['GET', 'POST'])
def ingest():
    """Ingest a job posting by URL."""
    if request.method == 'GET':
        return render_template('ingest.html')

    url = request.form.get('url', '').strip()
    if not url:
        return jsonify({'error': 'URL required'}), 400

    from pipeline.ingest import fetch_job_from_url

    try:
        job_data = fetch_job_from_url(url)
    except Exception as e:
        return jsonify({'error': f'Failed to fetch URL: {e}'}), 400

    job = upsert_job(
        title=job_data["title"],
        url=job_data["url"],
        description=job_data.get("description"),
        source=job_data.get("source", "Manual"),
        feed=job_data.get("feed", "Manual Ingest"),
    )

    return redirect(url_for('job_detail', job_id=job.id))
```

**Step 4: Create `templates/ingest.html`**

```html
{% extends "base.html" %}

{% block title %}Add Job - Job Search{% endblock %}

{% block content %}
<h1>Add Job by URL</h1>
<form method="post" action="{{ url_for('ingest') }}" class="ingest-form">
    <label for="url">Job Posting URL:</label>
    <input type="url" name="url" id="url" placeholder="https://job-boards.greenhouse.io/..." required>
    <button type="submit" class="btn-primary">Add Job</button>
</form>
{% endblock %}
```

**Step 5: Add "Add Job" link to navbar in `templates/base.html`**

Add after the Review link:

```html
<a href="{{ url_for('ingest') }}">Add Job</a>
```

**Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_ingest_route.py -v`
Expected: All 3 PASS

**Step 7: Commit**

```bash
git add app.py templates/ingest.html templates/base.html tests/test_ingest_route.py
git commit -m "feat: add web UI for manual URL ingest with /ingest route"
```

---

### Task 8: Full Integration Verification

**Step 1: Run the entire test suite**

```bash
python -m pytest tests/ -v
python test_project.py
python -m db.smoke_test
```

Expected: All pass

**Step 2: Manual smoke test of ATS search (optional, costs tokens)**

```bash
python run_pipeline.py --ats-only --skip-analyzer
```

**Step 3: Manual smoke test of URL ingest**

```bash
python run_pipeline.py --ingest-url https://job-boards.greenhouse.io/runpod/jobs/5179915008
```

**Step 4: Final commit and push**

```bash
git push
```
