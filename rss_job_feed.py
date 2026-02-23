import pandas as pd
import feedparser
from datetime import datetime, timedelta
from pathlib import Path

# RSS feed URLs - can be a single URL string or a list of URLs
FEED_URL = [
    "https://rss.app/feeds/51cgVZegdBeT9hKP.xml",
    "https://rss.app/feeds/XYgV02vToQ4o46ti.xml",
    "https://rss.app/feeds/WvTYHnV8Unk3O0ho.xml",
    "https://rss.app/feeds/W9LM5JvGa5oUynNf.xml"
]

def fetch_and_parse_jobs(feed_url=FEED_URL, hours_back=None, since=None):
    """
    Fetch jobs from RSS XML feed(s) and parse into DataFrame.

    Args:
        feed_url: URL string or list of URLs for XML RSS feeds
        hours_back: If specified, only return jobs from the last N hours
        since: Dict mapping feed URL to datetime cutoff. Entries older than
               the cutoff are skipped. Feeds not in the dict get a full fetch.

    Returns:
        DataFrame with job listings
    """
    # Convert single URL to list for uniform processing
    if isinstance(feed_url, str):
        feed_url = [feed_url]

    if since is None:
        since = {}

    all_jobs = []

    # Process each feed
    for url in feed_url:
        cutoff = since.get(url)
        if cutoff:
            print(f"Fetching feed: {url}  (since {cutoff.isoformat()})")
        else:
            print(f"Fetching feed: {url}  (full fetch)")
        feed = feedparser.parse(url)

        # Get feed title for source tracking
        feed_title = feed.feed.get('title', url)

        for entry in feed.entries:
            # Parse the published date
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                pub_date = datetime(*entry.published_parsed[:6])
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                pub_date = datetime(*entry.updated_parsed[:6])
            else:
                pub_date = datetime.now()

            # Filter by time window if specified
            if hours_back:
                cutoff_time = datetime.now() - timedelta(hours=hours_back)
                if pub_date < cutoff_time:
                    continue

            # Filter by per-feed last-fetch timestamp
            if cutoff and pub_date <= cutoff:
                continue

            # Extract job details
            all_jobs.append({
                'Job Title': entry.get('title', 'N/A'),
                'URL': entry.get('link', 'N/A'),
                'Description': entry.get('summary', 'N/A'),
                'Posted Date': pub_date,
                'Source': entry.get('author', feed_title),
                'Feed': feed_title,
                'Feed URL': url,
            })

    # Create DataFrame
    jobs_df = pd.DataFrame(all_jobs)

    # Sort by date (newest first)
    if not jobs_df.empty:
        jobs_df = jobs_df.sort_values('Posted Date', ascending=False)
        # Remove duplicate job postings (same title and URL)
        jobs_df = jobs_df.drop_duplicates(subset=['Job Title', 'URL'], keep='first')

    return jobs_df


def save_jobs_table(df, output_dir="jobs", filename=None):
    """Save jobs DataFrame to CSV and markdown table."""
    if filename is None:
        today = datetime.now().strftime("%Y-%m-%d")
        filename = f"rss_jobs_{today}"

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Save as CSV
    csv_file = output_path / f"{filename}.csv"
    df.to_csv(csv_file, index=False)
    print(f"✓ Saved CSV to {csv_file}")

    return csv_file


if __name__ == "__main__":
    # Fetch all jobs from feed
    print("Fetching jobs from RSS feed...")
    jobs_df = fetch_and_parse_jobs()

    print(f"\nFound {len(jobs_df)} jobs")
    print("\nMost recent jobs:")
    print(jobs_df.head(10).to_string())

    # Save to files
    print("\nSaving results...")
    save_jobs_table(jobs_df)

    # # Example: Filter to last 24 hours
    # recent_jobs = fetch_and_parse_jobs(hours_back=24)
    # if len(recent_jobs) > 0:
    #     print(f"\n{len(recent_jobs)} jobs posted in last 24 hours")
    #     save_jobs_table(recent_jobs, filename=f"rss_jobs_{datetime.now().strftime('%Y-%m-%d')}")
    # else:
    #     print("\nNo jobs posted in the last 24 hours")
