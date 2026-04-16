#!/usr/bin/env python3
"""Unified job search pipeline.

Fetches jobs from all configured sources (RSS feeds and web search),
deduplicates by URL, and stores directly to SQLite database.

Usage:
    python run_pipeline.py              # Full run (RSS + web search)
    python run_pipeline.py --rss-only   # RSS feeds only
    python run_pipeline.py --search-only # Web search only
"""

import argparse
import sys
from datetime import datetime

from db.connection import init_db
from db.feeds import get_all_last_fetches, set_last_fetch
from db.jobs import upsert_job
from pipeline.rss import fetch_and_parse_jobs, FEED_URL

def run_rss_fetch(conn) -> tuple[int, int]:
    """Fetch jobs from RSS feeds and store to database.

    Uses per-feed last-fetch timestamps to only retrieve new entries.
    Falls back to a full fetch for feeds without a recorded timestamp.

    Returns:
        Tuple of (jobs_fetched, jobs_upserted)
    """
    print("=" * 60)
    print("FETCHING RSS FEEDS")
    print("=" * 60)

    # Load per-feed last-fetch timestamps (incremental mode)
    since = get_all_last_fetches(db=conn)

    jobs = fetch_and_parse_jobs(FEED_URL, since=since)

    if not jobs:
        print("No new jobs found in RSS feeds")
        return 0, 0

    print(f"\nFound {len(jobs)} new jobs from RSS feeds")

    # Store each job to database, tracking which succeeded
    upserted = 0
    failures = 0
    upserted_jobs = []
    for job in jobs:
        try:
            posted = job.get("Posted Date")
            upsert_job(
                title=job["Job Title"],
                url=job["URL"],
                description=job.get("Description"),
                posted_date=posted.strftime("%Y-%m-%d") if posted else None,
                source=job.get("Source"),
                feed=job.get("Feed"),
                feed_url=job.get("Feed URL"),
                db=conn,
            )
            upserted += 1
            upserted_jobs.append(job)
        except Exception as e:
            failures += 1
            print(f"Error upserting job {job.get('URL')}: {e}")
            if failures > 5:
                print(f"ERROR: Too many upsert failures ({failures}), aborting RSS fetch")
                break

    # Record the newest entry timestamp per feed URL — only from successfully upserted jobs
    for url in FEED_URL:
        feed_rows = [j for j in upserted_jobs if j.get("Feed URL") == url]
        if feed_rows:
            newest = max(j["Posted Date"] for j in feed_rows)
            set_last_fetch(url, newest, db=conn)

    print(f"Stored {upserted} jobs from RSS feeds")
    return len(jobs), upserted


def run_web_search(conn) -> tuple[int, int]:
    """Run web search for jobs and store to database.
    
    Returns:
        Tuple of (jobs_found, jobs_upserted)
    """
    print("\n" + "=" * 60)
    print("WEB SEARCH")
    print("=" * 60)
    
    # Lazy import to avoid requiring OPENAI_API_KEY when not using web search
    try:
        from pipeline.search import search_daily
    except ImportError as e:
        if "openai" in str(e).lower():
            print("Skipping web search: openai package not installed")
        else:
            print(f"ERROR: Failed to import pipeline.search: {e}")
        return 0, 0
    
    try:
        jobs = search_daily()
    except Exception as e:
        print(f"ERROR: Web search failed ({type(e).__name__}): {e}")
        return 0, 0
    
    if not jobs:
        print("No jobs found from web search")
        return 0, 0
    
    print(f"\nFound {len(jobs)} jobs from web search")
    
    # Store each job to database
    upserted = 0
    failures = 0
    for job in jobs:
        if not job.get("url"):
            print(f"WARNING: Skipping web search result with no URL: {job.get('title', 'unknown')}")
            continue
        try:
            upsert_job(
                title=job.get("title", ""),
                url=job["url"],
                description=job.get("description"),
                posted_date=job.get("posted_date"),
                source=job.get("source", "Web Search"),
                feed=job.get("feed", "Web Search"),
                db=conn,
            )
            upserted += 1
        except Exception as e:
            failures += 1
            print(f"Error upserting job {job.get('url')}: {e}")
            if failures > 5:
                print(f"ERROR: Too many upsert failures ({failures}), aborting web search store")
                break
    
    print(f"Stored {upserted} jobs from web search")
    return len(jobs), upserted


def run_ats_search(conn) -> tuple[int, int]:
    """Search ATS platforms for jobs and store to database."""
    print("\n" + "=" * 60)
    print("ATS PLATFORM SEARCH")
    print("=" * 60)

    try:
        from pipeline.ats_search import search_all_platforms, ATS_PLATFORMS
    except ImportError as e:
        print(f"ERROR: Failed to import pipeline.ats_search: {e}")
        return 0, 0

    # Build since dict from last_fetch timestamps
    all_fetches = get_all_last_fetches(db=conn)
    ats_since = {}
    for domain, source_name, feed_name in ATS_PLATFORMS:
        for url, ts in all_fetches.items():
            if feed_name in url:
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
                print(f"ERROR: Too many failures ({failures}), aborting")
                break

    # Update last_fetch for each ATS feed
    now = datetime.now()
    for domain, source_name, feed_name in ATS_PLATFORMS:
        set_last_fetch(feed_name, now, db=conn)

    print(f"Stored {upserted} jobs from ATS platforms")
    return len(jobs), upserted


def ingest_url(url: str, conn) -> None:
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


def run_pipeline(conn=None, rss_only=False, search_only=False, ats_only=False, skip_analyzer=False):
    """Run the full job search pipeline.

    Fetches jobs from configured sources, then runs the LLM analyzer
    on new jobs unless skip_analyzer is True.

    Args:
        conn: Database connection. Created via init_db() if not provided.
        rss_only: Only run RSS feed fetch.
        search_only: Only run web search.
        ats_only: Only run ATS platform search.
        skip_analyzer: Skip LLM job analysis step.

    Returns:
        Tuple of (total_fetched, total_upserted).
    """
    if conn is None:
        conn = init_db()

    total_fetched = 0
    total_upserted = 0

    if not search_only and not ats_only:
        rss_fetched, rss_upserted = run_rss_fetch(conn)
        total_fetched += rss_fetched
        total_upserted += rss_upserted

    if not rss_only and not ats_only:
        search_fetched, search_upserted = run_web_search(conn)
        total_fetched += search_fetched
        total_upserted += search_upserted

    if not rss_only and not search_only:
        ats_fetched, ats_upserted = run_ats_search(conn)
        total_fetched += ats_fetched
        total_upserted += ats_upserted

    if not skip_analyzer:
        print("\n" + "=" * 60)
        print("RUNNING JOB ANALYZER")
        print("=" * 60)
        print("Analyzing new jobs with LLM for location and pay extraction...")
        try:
            from pipeline.analyzer import process_jobs
            process_jobs(dry_run=False)
        except Exception as e:
            print(f"ERROR: Job analyzer failed: {type(e).__name__}: {e}")
            print("Continuing without analysis — new jobs will need manual review.")

    return total_fetched, total_upserted


def main():
    parser = argparse.ArgumentParser(
        description="Run unified job search pipeline"
    )
    parser.add_argument(
        "--rss-only",
        action="store_true",
        help="Run only RSS feed fetch",
    )
    parser.add_argument(
        "--search-only",
        action="store_true",
        help="Run only web search",
    )
    parser.add_argument(
        "--ats-only",
        action="store_true",
        help="Run only ATS platform search",
    )
    parser.add_argument(
        "--skip-analyzer",
        action="store_true",
        help="Skip LLM job analysis step",
    )
    parser.add_argument(
        "--ingest-url",
        type=str,
        metavar="URL",
        help="Ingest a single job posting by URL (no pipeline run)",
    )
    args = parser.parse_args()

    # Handle --ingest-url: ingest and return early
    if args.ingest_url:
        conn = init_db()
        ingest_url(args.ingest_url, conn)
        return

    # Validate arguments
    exclusive = sum([args.rss_only, args.search_only, args.ats_only])
    if exclusive > 1:
        print("Error: Cannot specify more than one of --rss-only, --search-only, --ats-only")
        sys.exit(1)

    start_time = datetime.now()
    print(f"\n{'*' * 60}")
    print(f"JOB SEARCH PIPELINE")
    print(f"Started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'*' * 60}\n")

    conn = init_db()

    total_fetched, total_upserted = run_pipeline(
        conn=conn,
        rss_only=args.rss_only,
        search_only=args.search_only,
        ats_only=args.ats_only,
        skip_analyzer=args.skip_analyzer,
    )

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)
    print(f"Duration: {duration:.1f} seconds")
    print(f"Jobs fetched: {total_fetched}")
    print(f"Jobs upserted: {total_upserted}")

    # Database stats
    job_count = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    new_count = conn.execute("SELECT COUNT(*) FROM jobs WHERE status = 'new'").fetchone()[0]

    print(f"\nFinal database summary:")
    print(f"  Total jobs: {job_count}")
    print(f"  New/unreviewed: {new_count}")

    print(f"\n{'*' * 60}")


if __name__ == "__main__":
    main()
