from openai import OpenAI
import json
import csv
import re
from pathlib import Path
from datetime import datetime

client = OpenAI()

ALLOWED_DOMAINS = ["builtin.com", "wellfound.com"]

ROLE_TITLES = [
    "technical writer", "taxonomy", "information architecture"
]

JSON_INSTRUCTIONS = """
Return ONLY a valid JSON array (no markdown, no preamble). Each element:
{
  "title": "Company hiring [Job Title] in [Location]",
  "url": "direct URL to the job posting",
  "description": "Full description: responsibilities, qualifications, compensation if listed",
  "posted_date": "YYYY-MM-DD",
  "source": "builtin.com or wellfound.com",
  "feed": "Web Search"
}
If no results found, return an empty array: []
"""


def run_search(query: str) -> str:
    """Run a web search via OpenAI and return the text content of the response."""
    response = client.responses.create(
        model="gpt-4.1",
        tools=[
            {
                "type": "web_search",
                "filters": {"allowed_domains": ALLOWED_DOMAINS},
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
    return "\n".join(text_parts)


def parse_json_response(raw: str) -> list[dict]:
    """Extract and parse a JSON array from a raw text response."""
    # Strip markdown code fences if present
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    # Find the outermost JSON array
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1:
        text = text[start : end + 1]

    return json.loads(text)


def save_jobs_csv(jobs: list[dict], filename: str) -> Path:
    """Save job listings to CSV matching rss_jobs column structure."""
    output_path = Path("jobs")
    output_path.mkdir(exist_ok=True)
    csv_file = output_path / filename

    fieldnames = ["Job Title", "URL", "Description", "Posted Date", "Source", "Feed"]

    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for job in jobs:
            writer.writerow({
                "Job Title": job.get("title", ""),
                "URL": job.get("url", ""),
                "Description": job.get("description", ""),
                "Posted Date": job.get("posted_date", ""),
                "Source": job.get("source", "Web Search"),
                "Feed": job.get("feed", "Web Search"),
            })

    print(f"Saved {len(jobs)} jobs to {csv_file}")
    return csv_file


def search_since(since_date: str) -> list[dict]:
    """
    One-off search for all relevant roles posted since a given date.

    Args:
        since_date: Date string like "January 1, 2026"
    """
    roles = ", ".join(ROLE_TITLES)
    query = f"""Search builtin.com and wellfound.com for job postings published since {since_date}.

Find all postings matching these roles: {roles}

Preferences:
- Remote, hybrid, or Seattle/Bellevue/Redmond/Kirkland area
- Exclude pure staffing agencies
{JSON_INSTRUCTIONS}"""

    print(f"Searching for jobs since {since_date}...")
    raw = run_search(query)

    try:
        jobs = parse_json_response(raw)
        print(f"Found {len(jobs)} jobs")
        return jobs
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Could not parse response as JSON: {e}")
        # Save raw response as fallback
        today = datetime.now().strftime("%Y-%m-%d")
        fallback = Path("jobs") / f"search_raw_{today}.txt"
        Path("jobs").mkdir(exist_ok=True)
        fallback.write_text(raw)
        print(f"Raw response saved to {fallback}")
        return []


def search_daily() -> list[dict]:
    """Search for jobs posted in the last 24 hours."""
    roles = ", ".join(ROLE_TITLES)
    query = f"""Search builtin.com and wellfound.com for job postings published within the last 24 hours.

Find all postings matching these roles: {roles}

Preferences:
- Remote, hybrid, or Seattle/Bellevue/Redmond/Kirkland area
- Exclude pure staffing agencies
{JSON_INSTRUCTIONS}"""

    print("Searching for jobs from the last 24 hours...")
    raw = run_search(query)

    try:
        jobs = parse_json_response(raw)
        print(f"Found {len(jobs)} jobs")
        return jobs
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Could not parse response as JSON: {e}")
        today = datetime.now().strftime("%Y-%m-%d")
        fallback = Path("jobs") / f"search_raw_{today}.txt"
        Path("jobs").mkdir(exist_ok=True)
        fallback.write_text(raw)
        print(f"Raw response saved to {fallback}")
        return []


if __name__ == "__main__":
    today = datetime.now().strftime("%Y-%m-%d")

    # One-off: search since Jan 1, 2026
    jobs = search_since("January 1, 2026")
    if jobs:
        save_jobs_csv(jobs, f"search_jobs_since_2026-01-01_{today}.csv")
