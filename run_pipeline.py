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
from pathlib import Path

from db.connection import init_db
from db.feeds import get_all_last_fetches, set_last_fetch
from db.jobs import upsert_job
from rss_job_feed import fetch_and_parse_jobs, FEED_URL
from job_analyzer import process_jobs

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

    jobs_df = fetch_and_parse_jobs(FEED_URL, since=since)

    if jobs_df.empty:
        print("No new jobs found in RSS feeds")
        return 0, 0

    print(f"\nFound {len(jobs_df)} new jobs from RSS feeds")

    # Store each job to database
    upserted = 0
    for _, row in jobs_df.iterrows():
        try:
            upsert_job(
                title=row["Job Title"],
                url=row["URL"],
                description=row.get("Description"),
                posted_date=row.get("Posted Date").strftime("%Y-%m-%d") if row.get("Posted Date") else None,
                source=row.get("Source"),
                feed=row.get("Feed"),
                feed_url=row.get("Feed URL"),
                db=conn,
            )
            upserted += 1
        except Exception as e:
            print(f"Error upserting job {row.get('URL')}: {e}")
            continue

    # Record the newest entry timestamp per feed URL for next run
    for url in FEED_URL:
        feed_rows = jobs_df[jobs_df["Feed URL"] == url]
        if not feed_rows.empty:
            newest = feed_rows["Posted Date"].max()
            set_last_fetch(url, newest, db=conn)

    print(f"Stored {upserted} jobs from RSS feeds")
    return len(jobs_df), upserted


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
        from startup_search import search_daily
    except ImportError as e:
        print(f"Failed to import startup_search: {e}")
        return 0, 0
    
    try:
        jobs = search_daily()
    except Exception as e:
        print(f"Web search failed: {e}")
        return 0, 0
    
    if not jobs:
        print("No jobs found from web search")
        return 0, 0
    
    print(f"\nFound {len(jobs)} jobs from web search")
    
    # Store each job to database
    upserted = 0
    for job in jobs:
        try:
            upsert_job(
                title=job.get("title", ""),
                url=job.get("url", ""),
                description=job.get("description"),
                posted_date=job.get("posted_date"),
                source=job.get("source", "Web Search"),
                feed=job.get("feed", "Web Search"),
                db=conn,
            )
            upserted += 1
        except Exception as e:
            print(f"Error upserting job {job.get('url')}: {e}")
            continue
    
    print(f"Stored {upserted} jobs from web search")
    return len(jobs), upserted


def run_pipeline(conn=None, rss_only=False, search_only=False, skip_analyzer=False):
    """Run the full job search pipeline.

    Fetches jobs from configured sources, then runs the LLM analyzer
    on new jobs unless skip_analyzer is True.

    Args:
        conn: Database connection. Created via init_db() if not provided.
        rss_only: Only run RSS feed fetch.
        search_only: Only run web search.
        skip_analyzer: Skip LLM job analysis step.

    Returns:
        Tuple of (total_fetched, total_upserted).
    """
    if conn is None:
        conn = init_db()

    total_fetched = 0
    total_upserted = 0

    if not search_only:
        rss_fetched, rss_upserted = run_rss_fetch(conn)
        total_fetched += rss_fetched
        total_upserted += rss_upserted

    if not rss_only:
        search_fetched, search_upserted = run_web_search(conn)
        total_fetched += search_fetched
        total_upserted += search_upserted

    if not skip_analyzer:
        print("\n" + "=" * 60)
        print("RUNNING JOB ANALYZER")
        print("=" * 60)
        print("Analyzing new jobs with LLM for location and pay extraction...")
        try:
            process_jobs(dry_run=False)
        except Exception as e:
            print(f"Warning: Job analyzer failed: {e}")
            print("Continuing without analysis...")

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
        "--skip-analyzer",
        action="store_true",
        help="Skip LLM job analysis step",
    )
    args = parser.parse_args()

    # Validate arguments
    if args.rss_only and args.search_only:
        print("Error: Cannot specify both --rss-only and --search-only")
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
