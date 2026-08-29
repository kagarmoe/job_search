"""ATS platform search for job postings using OpenAI web search.

Searches ATS platforms (Greenhouse, Ashby) for technical writer postings
using domain-filtered web search.
"""

from datetime import datetime
from openai import OpenAI

from pipeline.search import parse_json_response

client = OpenAI()

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
    """Search a single ATS platform for job postings.

    Resolves source and feed names from ATS_PLATFORMS based on domain.

    Args:
        domain: The ATS domain to search (e.g. "greenhouse.io").
        since: Optional datetime; if provided, restrict to postings since that date.

    Returns:
        List of dicts with keys: title, url, company, source, feed.
    """
    # Resolve source/feed from platform config
    source = domain.split(".")[0].capitalize()
    feed = f"{source} Search"
    for d, s, f in ATS_PLATFORMS:
        if d == domain:
            source, feed = s, f
            break
    query = f'"technical writer" job postings on {domain}'
    if since is not None:
        query += f" published since {since.strftime('%Y-%m-%d')}"
    query += f"\n{JSON_INSTRUCTIONS}"

    response = client.responses.create(
        model="gpt-4.1",
        tools=[
            {
                "type": "web_search",
                "filters": {"allowed_domains": [domain]},
            }
        ],
        input=query,
    )

    # Extract text from response output items
    text_parts = []
    for item in response.output:
        if getattr(item, "type", None) == "message":
            for content in getattr(item, "content", []):
                if getattr(content, "type", None) in ("output_text", "text"):
                    text_parts.append(content.text)
    raw = "\n".join(text_parts)

    if not raw.strip():
        print(f"WARNING: ATS search returned no text for {domain}")
        return []

    try:
        parsed = parse_json_response(raw)
    except Exception as e:
        print(f"WARNING: Could not parse ATS search response for {domain}: {e}")
        return []

    # Filter out results whose URL doesn't contain the target domain
    jobs = []
    for entry in parsed:
        url = entry.get("url", "")
        if domain not in url:
            print(f"WARNING: Filtered out result with URL not on {domain}: {url}")
            continue
        entry["source"] = source
        entry["feed"] = feed
        jobs.append(entry)

    return jobs


def search_all_platforms(
    since: dict[str, datetime] | None = None,
) -> list[dict]:
    """Search all configured ATS platforms and combine results.

    Args:
        since: Optional dict mapping feed_name to datetime for incremental search.

    Returns:
        Combined list of job dicts from all platforms.
    """
    all_jobs: list[dict] = []

    for domain, source_name, feed_name in ATS_PLATFORMS:
        try:
            since_dt = since.get(feed_name) if since else None
            jobs = search_ats_platform(domain, since=since_dt)
            all_jobs.extend(jobs)
        except Exception as e:
            print(f"ERROR: ATS search failed for {source} ({domain}): {e}")

    return all_jobs
