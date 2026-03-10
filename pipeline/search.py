"""Web search for job postings using OpenAI.

Searches configured job boards for relevant postings and returns
structured results as dicts.
"""

import json
import re
from openai import OpenAI

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
    result = "\n".join(text_parts)
    if not result.strip():
        print(f"WARNING: Web search returned no text content for query: {query[:100]}")
    return result


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


def search_since(since_date: str) -> list[dict]:
    """One-off search for all relevant roles posted since a given date.

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
        print(f"ERROR: Could not parse web search response as JSON: {e}")
        print(f"Raw response (first 500 chars): {raw[:500]}")
        raise ValueError(f"Web search response could not be parsed: {e}") from e


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
        print(f"ERROR: Could not parse web search response as JSON: {e}")
        print(f"Raw response (first 500 chars): {raw[:500]}")
        raise ValueError(f"Web search response could not be parsed: {e}") from e
