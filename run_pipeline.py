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
from db.jobs import upsert_job
from rss_job_feed import fetch_and_parse_jobs, FEED_URL


def run_rss_fetch(conn) -> tuple[int, int]:
    """Fetch jobs from RSS feeds and store to database.
    
    Returns:
        Tuple of (jobs_fetched, jobs_upserted)
    """
    print("=" * 60)
    print("FETCHING RSS FEEDS")
    print("=" * 60)
    
    jobs_df = fetch_and_parse_jobs(FEED_URL)
    
    if jobs_df.empty:
        print("No jobs found in RSS feeds")
        return 0, 0
    
    print(f"\nFound {len(jobs_df)} jobs from RSS feeds")
    
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
                db=conn,
            )
            upserted += 1
        except Exception as e:
            print(f"Error upserting job {row.get('URL')}: {e}")
            continue
    
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
    
    # Initialize database
    conn = init_db()
    
    total_fetched = 0
    total_upserted = 0
    
    # Run RSS fetch unless search-only
    if not args.search_only:
        rss_fetched, rss_upserted = run_rss_fetch(conn)
        total_fetched += rss_fetched
        total_upserted += rss_upserted
    
    # Run web search unless rss-only
    if not args.rss_only:
        search_fetched, search_upserted = run_web_search(conn)
        total_fetched += search_fetched
        total_upserted += search_upserted
    
    # Summary
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)
    print(f"Duration: {duration:.1f} seconds")
    print(f"Jobs fetched: {total_fetched}")
    print(f"Jobs upserted: {total_upserted}")
    
    # Run LLM analyzer unless skipped
    if not args.skip_analyzer:
        print("\n" + "=" * 60)
        print("RUNNING JOB ANALYZER")
        print("=" * 60)
        print("Analyzing new jobs with LLM for location and pay extraction...")
        
        try:
            # Import here to avoid requiring OpenAI when skipping
            from job_analyzer import process_jobs
            process_jobs(dry_run=False)
        except ImportError as e:
            print(f"Warning: Could not import job_analyzer: {e}")
        except Exception as e:
            print(f"Warning: Job analyzer failed: {e}")
            print("Continuing without analysis...")
    
    # Database stats
    job_count = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    new_count = conn.execute("SELECT COUNT(*) FROM jobs WHERE status = 'new'").fetchone()[0]
    
    print(f"\nFinal database summary:")
    print(f"  Total jobs: {job_count}")
    print(f"  New/unreviewed: {new_count}")
    
    print(f"\n{'*' * 60}")


if __name__ == "__main__":
    main()
