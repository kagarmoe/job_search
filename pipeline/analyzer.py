"""LLM-powered job analyzer for location verification and data extraction.

Analyzes job postings to:
1. Verify if job is in the Seattle metro area or truly remote
2. Identify employment type (full-time, contract, part-time)
3. Extract pay range information
4. Extract contract duration for contract roles
5. Clean up title formatting issues

Jobs are labeled:
- "Seattle" - In one of the configured metro area cities
- "Remote" - Clearly fully remote
- "Review for location" - Agent is uncertain, needs manual review
- "DELETE" - Does not meet criteria; removed from database
"""

import argparse
import json
import openai
from openai import OpenAI

from db.jobs import list_jobs, get_job, update_analysis, delete_job
from pipeline.constants import SEATTLE_METRO

client = OpenAI()

# All placeholders use .replace() to avoid crashing on job content
# containing curly braces (common in tech job descriptions with JSON/code).
ANALYSIS_PROMPT = """You are analyzing a job posting to determine its location eligibility and extract key information.

CRITICAL: You MUST read the ENTIRE job posting carefully before making any decisions.

TARGET CRITERIA:
- Located in the Seattle metro area (see city list below), OR
- Fully remote work (not hybrid, not occasional remote)

Seattle metro area cities: {METRO_CITIES}
Any job in one of these cities meets the location criteria.

Analyze this job posting:

TITLE: {title}
DESCRIPTION: {description}
SOURCE: {source}

Your tasks:

1. LOCATION LABEL: Read the ENTIRE posting before deciding
   - Check both title AND full description for location information
   - Look for contradictions (e.g., "remote" in title but "onsite required" in description)
   - Check for hybrid requirements (e.g., "3 days per week in San Francisco office")
   - Verify if location is in one of the Seattle metro cities listed above OR if truly 100% remote

   Return one of these EXACT labels:
   - "Seattle" - Job is clearly in one of the Seattle metro area cities listed above
   - "Remote" - Job is clearly fully remote (not hybrid, no office requirement)
   - "Review for location" - Cannot determine with certainty, needs manual review
   - "DELETE" - Clearly does NOT meet criteria (wrong location AND not remote)

2. JOB TYPE: Identify employment type
   - Look for: full-time, full time, FTE, permanent, salaried
   - Look for: contract, contractor, hourly, temp, temporary, C2C, corp-to-corp, freelance, W2 contract
   - Look for: part-time, part time

   Return one of these EXACT types:
   - "Full-time" - Permanent, salaried, FTE position
   - "Contract" - Contract, hourly, temporary position
   - "Part-time" - Part-time position
   - "Not specified" - Cannot determine from posting

3. PAY RANGE: Extract salary/compensation information with time period
   - For salaried/full-time: "$100,000-$150,000/year" or "$100K-$150K/year"
   - For hourly/contract: "$50-75/hour" or "$50-$75/hr"
   - Look for: salary, compensation, pay rate, hourly rate, annual salary, base pay
   - Include currency symbol ($) and time period (/year, /hour, /yr, /hr)
   - Return "NOT_SPECIFIED" if no pay information found

4. CONTRACT DURATION: For contract jobs only, extract contract length
   - Look for: "3 month contract", "6 months", "12-month", "1 year contract"
   - Look for: "contract to hire", "C2H", "temp to perm"
   - Format examples: "3 months", "6 months", "12 months", "Contract-to-hire"
   - Return "NOT_SPECIFIED" if not a contract job or duration not mentioned
   - Only relevant for Contract job types

5. TITLE CLEANUP: Fix any formatting issues in the title
   - Add spaces where missing (e.g., "R0232726Technical Writer" → "R0232726 Technical Writer")
   - Fix obvious concatenation issues
   - Return cleaned title or original if no issues

Return ONLY valid JSON (no markdown):
{
  "location_label": "Seattle|Remote|Review for location|DELETE",
  "location_reasoning": "Brief explanation of your decision based on reading the ENTIRE posting",
  "job_type": "Full-time|Contract|Part-time|Not specified",
  "pay_range": "extracted pay with time period or NOT_SPECIFIED",
  "contract_duration": "duration for contracts (e.g., '6 months', 'Contract-to-hire') or NOT_SPECIFIED",
  "title_cleaned": "cleaned title text"
}
""".replace("{METRO_CITIES}", ", ".join(SEATTLE_METRO))


def analyze_job(job) -> dict:
    """Analyze a job posting using the OpenAI LLM.

    Returns a dict with keys: location_label, location_reasoning,
    job_type, pay_range, contract_duration, title_cleaned.
    On failure, returns safe defaults with location_label='Review for location'.
    Raises on authentication, rate limit, connection, and timeout errors.
    """
    prompt = ANALYSIS_PROMPT.replace(
        "{title}", job.title
    ).replace(
        "{description}", job.description or "No description provided"
    ).replace(
        "{source}", job.source or "Unknown"
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a precise job posting analyzer. Return only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )

        result = json.loads(response.choices[0].message.content)
        return result

    except (openai.AuthenticationError, openai.RateLimitError,
            openai.APIConnectionError, openai.APITimeoutError):
        raise
    except json.JSONDecodeError as e:
        print(f"ERROR: LLM returned invalid JSON for job {job.id}: {e}")
        return {
            "location_label": "Review for location",
            "location_reasoning": f"ANALYSIS FAILED (invalid JSON): {str(e)}",
            "job_type": "Not specified",
            "pay_range": "NOT_SPECIFIED",
            "contract_duration": "NOT_SPECIFIED",
            "title_cleaned": job.title,
        }
    except Exception as e:
        print(f"ERROR: Unexpected error analyzing job {job.id}: {type(e).__name__}: {e}")
        return {
            "location_label": "Review for location",
            "location_reasoning": f"ANALYSIS FAILED ({type(e).__name__}): {str(e)}",
            "job_type": "Not specified",
            "pay_range": "NOT_SPECIFIED",
            "contract_duration": "NOT_SPECIFIED",
            "title_cleaned": job.title,
        }


def process_jobs(job_ids=None, dry_run=False):
    """Analyze jobs via LLM and update the database with results.

    By default analyzes all jobs with status 'new'. Jobs labeled
    'DELETE' by the analyzer are removed from the database.

    Args:
        job_ids: Specific job IDs to analyze. Defaults to all 'new' jobs.
        dry_run: If True, print results without modifying the database.

    Returns:
        Dict of stats: seattle, remote, review, deleted, pay_found, title_cleaned.
    """
    if job_ids:
        jobs = []
        for jid in job_ids:
            job = get_job(jid)
            if job:
                jobs.append(job)
            else:
                print(f"WARNING: Job ID {jid} not found, skipping")
    else:
        jobs = list_jobs(status="new")

    print(f"Analyzing {len(jobs)} jobs...")

    stats = {
        "seattle": 0,
        "remote": 0,
        "review": 0,
        "deleted": 0,
        "pay_found": 0,
        "title_cleaned": 0,
    }

    for job in jobs:
        print(f"\n{'='*60}")
        print(f"Job {job.id}: {job.title[:80]}")
        print(f"{'='*60}")

        analysis = analyze_job(job)

        location_label = analysis.get("location_label", "Review for location")
        reasoning = analysis.get("location_reasoning", "")
        job_type = analysis.get("job_type", "Not specified")
        pay_range = analysis.get("pay_range", "NOT_SPECIFIED")
        contract_duration = analysis.get("contract_duration", "NOT_SPECIFIED")
        title_cleaned = analysis.get("title_cleaned", job.title)

        print(f"Location: {location_label}")
        print(f"Reasoning: {reasoning}")
        print(f"Job Type: {job_type}")
        print(f"Pay: {pay_range}")
        if contract_duration != "NOT_SPECIFIED":
            print(f"Contract Duration: {contract_duration}")

        if title_cleaned != job.title:
            print(f"Title cleaned: {title_cleaned}")
            stats["title_cleaned"] += 1

        if pay_range != "NOT_SPECIFIED":
            stats["pay_found"] += 1

        if location_label == "DELETE":
            stats["deleted"] += 1
            if not dry_run:
                delete_job(job.id)
                print("DELETED - does not meet location criteria")
            else:
                print("Would delete (dry-run)")
            continue

        if location_label == "Seattle":
            stats["seattle"] += 1
        elif location_label == "Remote":
            stats["remote"] += 1
        else:
            stats["review"] += 1

        if not dry_run:
            kwargs = {"location_label": location_label}
            if job_type != "Not specified":
                kwargs["job_type"] = job_type
            if pay_range != "NOT_SPECIFIED":
                kwargs["pay_range"] = pay_range
            if contract_duration != "NOT_SPECIFIED":
                kwargs["contract_duration"] = contract_duration
            if title_cleaned != job.title:
                kwargs["title"] = title_cleaned

            update_analysis(job.id, **kwargs)
            print(f"Updated: {', '.join(kwargs.keys())}")
        else:
            dry_run_msg = f"Would update: location_label='{location_label}', job_type='{job_type}', pay_range='{pay_range}'"
            if contract_duration != "NOT_SPECIFIED":
                dry_run_msg += f", contract_duration='{contract_duration}'"
            print(f"{dry_run_msg} (dry-run)")

    # Print summary
    print(f"\n{'='*60}")
    print("ANALYSIS SUMMARY")
    print(f"{'='*60}")
    print(f"Seattle: {stats['seattle']}")
    print(f"Remote: {stats['remote']}")
    print(f"Review for location: {stats['review']}")
    print(f"Deleted: {stats['deleted']}")
    print(f"Pay ranges found: {stats['pay_found']}")
    print(f"Titles cleaned: {stats['title_cleaned']}")
    print(f"\nTotal processed: {len(jobs)}")
    print(f"Total kept: {stats['seattle'] + stats['remote'] + stats['review']}")

    if dry_run:
        print("\n(DRY RUN - no changes made)")

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Analyze job postings with LLM for location and data extraction"
    )
    parser.add_argument(
        "--job-id",
        type=int,
        action="append",
        help="Analyze specific job ID (can specify multiple times)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview analysis without making changes",
    )
    args = parser.parse_args()

    print("Job Analyzer")
    print("=" * 60)
    print("Target: Seattle metro area cities or remote")
    print("=" * 60)

    stats = process_jobs(job_ids=args.job_id, dry_run=args.dry_run)

    return 0


if __name__ == "__main__":
    exit(main())
