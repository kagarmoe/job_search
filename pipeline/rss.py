"""Fetch job listings from RSS feeds.

Parses configured RSS XML feeds and returns job listings as plain dicts.
Supports incremental fetching via per-feed timestamp cutoffs.
"""

import feedparser
from datetime import datetime, timedelta

# RSS feed URLs - can be a single URL string or a list of URLs
FEED_URL = [
    "https://rss.app/feeds/51cgVZegdBeT9hKP.xml",
    "https://rss.app/feeds/XYgV02vToQ4o46ti.xml",
    "https://rss.app/feeds/WvTYHnV8Unk3O0ho.xml",
    "https://rss.app/feeds/W9LM5JvGa5oUynNf.xml",
]


def fetch_and_parse_jobs(feed_url=FEED_URL, hours_back=None, since=None):
    """Fetch jobs from RSS XML feed(s) and return as list of dicts.

    Args:
        feed_url: URL string or list of URLs for XML RSS feeds.
        hours_back: If specified, only return jobs from the last N hours.
        since: Dict mapping feed URL to datetime cutoff. Entries older than
               the cutoff are skipped. Feeds not in the dict get a full fetch.

    Returns:
        List of dicts with keys: Job Title, URL, Description, Posted Date,
        Source, Feed, Feed URL. Sorted newest-first, deduplicated by
        (Job Title, URL).
    """
    if isinstance(feed_url, str):
        feed_url = [feed_url]

    if since is None:
        since = {}

    all_jobs = []
    seen = set()

    for url in feed_url:
        cutoff = since.get(url)
        if cutoff:
            print(f"Fetching feed: {url}  (since {cutoff.isoformat()})")
        else:
            print(f"Fetching feed: {url}  (full fetch)")
        feed = feedparser.parse(url)

        if feed.bozo:
            print(f"WARNING: Feed parse error for {url}: {feed.bozo_exception}")
        status = getattr(feed, "status", None)
        if isinstance(status, int) and status >= 400:
            print(f"WARNING: Feed returned HTTP {status} for {url}")
            continue

        feed_title = feed.feed.get("title", url)

        for entry in feed.entries:
            # Parse the published date
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                pub_date = datetime(*entry.published_parsed[:6])
            elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
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

            title = entry.get("title", "N/A")
            link = entry.get("link", "N/A")

            # Deduplicate by (title, URL)
            key = (title, link)
            if key in seen:
                continue
            seen.add(key)

            all_jobs.append(
                {
                    "Job Title": title,
                    "URL": link,
                    "Description": entry.get("summary", "N/A"),
                    "Posted Date": pub_date,
                    "Source": entry.get("author", feed_title),
                    "Feed": feed_title,
                    "Feed URL": url,
                }
            )

    # Sort by date (newest first)
    all_jobs.sort(key=lambda j: j["Posted Date"], reverse=True)

    return all_jobs
