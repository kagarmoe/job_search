#!/usr/bin/env python3
"""LLM-powered job analyzer for location verification and data extraction.

Analyzes job postings to:
1. Verify if job is within 20 miles of 98117 (Seattle area) or truly remote
2. Extract pay range information
3. Clean up title formatting issues

Jobs are labeled:
- "Seattle" - Within 20 miles of Seattle zip 98117
- "Remote" - Clearly fully remote
- "Review for location" - Agent is uncertain, needs manual review

Usage:
    python job_analyzer.py              # Analyze all new jobs
    python job_analyzer.py --job-id 123 # Analyze specific job
    python job_analyzer.py --dry-run    # Preview without making changes
"""

import argparse
import json
import re
from datetime import datetime
from openai import OpenAI

from db.connection import get_db
from db.jobs import list_jobs, get_job, update_status, delete_job

client = OpenAI()

SEATTLE_ZIP = "98117"
SEATTLE_METRO_CITIES = ["Seattle", "Bellevue", "Redmond", "Kirkland", "Bothell", "Renton", "Kent", "Federal Way", "Sammamish", "Issaquah", "Tacoma", "Olympia"]

ANALYSIS_PROMPT = """You are analyzing a job posting to determine its location eligibility and extract key information.

CRITICAL: You MUST read the ENTIRE job posting carefully before making any decisions.

TARGET CRITERIA:
- Located in the Seattle metro area (see city list below), OR
- Fully remote work (not hybrid, not occasional remote)

Seattle metro area cities: Seattle, Bellevue, Redmond, Kirkland, Bothell, Renton, Kent, Federal Way, Sammamish, Issaquah, Tacoma, Olympia
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
{{
  "location_label": "Seattle|Remote|Review for location|DELETE",
  "location_reasoning": "Brief explanation of your decision based on reading the ENTIRE posting",
  "job_type": "Full-time|Contract|Part-time|Not specified",
  "pay_range": "extracted pay with time period or NOT_SPECIFIED",
  "contract_duration": "duration for contracts (e.g., '6 months', 'Contract-to-hire') or NOT_SPECIFIED",
  "title_cleaned": "cleaned title text"
}}
"""


def analyze_job(job) -> dict:
    """Analyze a job posting using LLM."""
    prompt = ANALYSIS_PROMPT.format(
        title=job.title,
        description=job.description or "No description provided",
        source=job.source or "Unknown"
    )
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a precise job posting analyzer. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        return result
    
    except Exception as e:
        print(f"Error analyzing job {job.id}: {e}")
        return {
            "location_label": "Review for location",
            "location_reasoning": f"Analysis failed: {str(e)}",
            "job_type": "Not specified",
            "pay_range": "NOT_SPECIFIED",
            "contract_duration": "NOT_SPECIFIED",
            "title_cleaned": job.title
        }


def process_jobs(job_ids=None, dry_run=False):
    """Process jobs through analyzer."""
    conn = get_db()
    
    # Get jobs to analyze
    if job_ids:
        jobs = [get_job(jid) for jid in job_ids if get_job(jid)]
    else:
        # Analyze all jobs with status 'new'
        jobs = list_jobs(status='new')
    
    print(f"Analyzing {len(jobs)} jobs...")
    
    stats = {
        "seattle": 0,
        "remote": 0,
        "review": 0,
        "deleted": 0,
        "pay_found": 0,
        "title_cleaned": 0
    }
    
    for job in jobs:
        print(f"\n{'='*60}")
        print(f"Job {job.id}: {job.title[:80]}")
        print(f"{'='*60}")
        
        # Analyze job
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
        
        # Handle DELETE decision - remove jobs that clearly don't meet criteria
        if location_label == "DELETE":
            stats["deleted"] += 1
            if not dry_run:
                delete_job(job.id)
                print(f"❌ DELETED - does not meet location criteria")
            else:
                print(f"❌ Would delete (dry-run)")
            continue
        
        # Update statistics for kept jobs
        if location_label == "Seattle":
            stats["seattle"] += 1
        elif location_label == "Remote":
            stats["remote"] += 1
        else:
            stats["review"] += 1
        
        # Update job in database
        if not dry_run:
            updates = []
            
            # Update location label
            conn.execute("UPDATE jobs SET location_label = ? WHERE id = ?", (location_label, job.id))
            updates.append("location")
            
            # Update job type
            if job_type != "Not specified":
                conn.execute("UPDATE jobs SET job_type = ? WHERE id = ?", (job_type, job.id))
                updates.append("job_type")
            
            # Update pay range
            if pay_range != "NOT_SPECIFIED":
                conn.execute("UPDATE jobs SET pay_range = ? WHERE id = ?", (pay_range, job.id))
                updates.append("pay_range")
            
            # Update contract duration
            if contract_duration != "NOT_SPECIFIED":
                conn.execute("UPDATE jobs SET contract_duration = ? WHERE id = ?", (contract_duration, job.id))
                updates.append("contract_duration")
            
            # Update title if cleaned
            if title_cleaned != job.title:
                conn.execute("UPDATE jobs SET title = ? WHERE id = ?", (title_cleaned, job.id))
                updates.append("title")
            
            if updates:
                conn.commit()
                print(f"✓ Updated: {', '.join(updates)}")
            else:
                print(f"✓ No updates needed")
        else:
            dry_run_msg = f"✓ Would update: location_label='{location_label}', job_type='{job_type}', pay_range='{pay_range}'"
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


def normalize_title(title: str) -> str:
    """Strip location suffix from a job title for dedup comparison.

    Preserves the company/source prefix so that different companies
    with the same role title are NOT treated as duplicates.
    """
    t = title
    # Strip " in City, STATE" / " in City, STATE - extra"
    t = re.sub(r"\s+in\s+[\w\s]+,\s*\w{2}(\s*-.*)?$", "", t)
    # Strip "(City, STATE)" at end
    t = re.sub(r"\s*\([\w\s]+,\s*\w{2}\)\s*$", "", t)
    # Strip " in United States"
    t = re.sub(r"\s+in\s+United States$", "", t)
    return t.strip()


def deduplicate_jobs(dry_run: bool = False, window_days: int = 30) -> dict:
    """Remove duplicate job postings based on normalized title.

    Groups jobs by normalized title (location suffix stripped), then
    clusters by posting date within *window_days*. Within each cluster
    keeps the posting with the richest description (longest) and deletes
    the rest.

    Jobs re-posted more than *window_days* apart are treated as separate
    openings and kept.
    """
    conn = get_db()

    rows = conn.execute("""
        SELECT id, title, posted_date, description,
               LENGTH(description) AS desc_len
        FROM jobs ORDER BY title
    """).fetchall()

    from collections import defaultdict
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        norm = normalize_title(r["title"])
        groups[norm].append({
            "id": r["id"],
            "title": r["title"],
            "posted_date": r["posted_date"],
            "desc_len": r["desc_len"] or 0,
        })

    stats = {"groups": 0, "duplicates": 0, "deleted": 0}

    for norm, jobs in sorted(groups.items()):
        if len(jobs) < 2:
            continue

        stats["groups"] += 1

        # Parse dates for clustering
        def parse_date(d):
            if not d:
                return datetime.min
            try:
                return datetime.fromisoformat(d.split(" ")[0])
            except ValueError:
                return datetime.min

        jobs.sort(key=lambda j: parse_date(j["posted_date"]))

        # Cluster by time window
        clusters: list[list[dict]] = []
        for job in jobs:
            job_date = parse_date(job["posted_date"])
            if clusters and (job_date - parse_date(clusters[-1][0]["posted_date"])).days <= window_days:
                clusters[-1].append(job)
            else:
                clusters.append([job])

        for cluster in clusters:
            if len(cluster) < 2:
                continue

            # Keep the one with the richest description
            cluster.sort(key=lambda j: j["desc_len"], reverse=True)
            keep = cluster[0]
            dupes = cluster[1:]
            stats["duplicates"] += len(dupes)

            print(f"\n  Keeping: id={keep['id']} '{keep['title'][:70]}' (desc={keep['desc_len']})")
            for d in dupes:
                print(f"  Deleting: id={d['id']} '{d['title'][:70]}' (desc={d['desc_len']})")
                if not dry_run:
                    delete_job(d["id"])
                    stats["deleted"] += 1

    print(f"\n{'='*60}")
    print("DEDUP SUMMARY")
    print(f"{'='*60}")
    print(f"Duplicate groups found: {stats['groups']}")
    print(f"Duplicate postings: {stats['duplicates']}")
    print(f"Deleted: {stats['deleted']}")
    if dry_run:
        print("(DRY RUN - no changes made)")

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
    parser.add_argument(
        "--dedup",
        action="store_true",
        help="Remove duplicate job postings (no LLM analysis)",
    )
    args = parser.parse_args()

    if args.dedup:
        print("Job Deduplication")
        print("=" * 60)
        deduplicate_jobs(dry_run=args.dry_run)
        return 0

    print("Job Analyzer")
    print("=" * 60)
    print(f"Target: Seattle metro area cities or remote")
    print("=" * 60)

    stats = process_jobs(job_ids=args.job_id, dry_run=args.dry_run)

    return 0


if __name__ == "__main__":
    exit(main())
