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
SEATTLE_METRO_CITIES = ["Seattle", "Bellevue", "Redmond", "Kirkland", "Bothell", "Renton", "Kent", "Federal Way", "Sammamish", "Issaquah"]

ANALYSIS_PROMPT = """You are analyzing a job posting to determine its location eligibility and extract key information.

CRITICAL: You MUST read the ENTIRE job posting carefully before making any decisions.

TARGET CRITERIA:
- Within 20 miles of Seattle, WA (zip code 98117), OR
- Fully remote work (not hybrid, not occasional remote)

Seattle metro area cities (within 20 miles): Seattle, Bellevue, Redmond, Kirkland, Bothell, Renton, Kent, Federal Way, Sammamish, Issaquah

Analyze this job posting:

TITLE: {title}
DESCRIPTION: {description}
SOURCE: {source}

Your tasks:

1. LOCATION LABEL: Read the ENTIRE posting before deciding
   - Check both title AND full description for location information
   - Look for contradictions (e.g., "remote" in title but "onsite required" in description)
   - Check for hybrid requirements (e.g., "3 days per week in San Francisco office")
   - Verify if location is within Seattle metro OR if truly 100% remote
   
   Return one of these EXACT labels:
   - "Seattle" - Job is clearly in Seattle metro area (within 20 miles of 98117)
   - "Remote" - Job is clearly fully remote (not hybrid, no office requirement)
   - "Review for location" - Cannot determine with certainty OR outside Seattle but not clearly remote

   Examples:
   - "Remote" in title but description says "must be in office 3 days/week in Austin" → "Review for location"
   - Job in Bellevue, WA → "Seattle"
   - Job says "100% remote, work from anywhere" → "Remote"
   - Job in Portland, OR with no remote mention → "Review for location"
   - Hybrid role → "Review for location"

2. PAY RANGE: Extract any salary/compensation information
   - Look for: salary, compensation, pay rate, hourly rate, annual salary
   - Include currency and time period (e.g., "$100,000-$150,000/year", "$50-75/hour")
   - Return "NOT_SPECIFIED" if no pay information found

3. TITLE CLEANUP: Fix any formatting issues in the title
   - Add spaces where missing (e.g., "R0232726Technical Writer" → "R0232726 Technical Writer")
   - Fix obvious concatenation issues
   - Return cleaned title or original if no issues

Return ONLY valid JSON (no markdown):
{{
  "location_label": "Seattle|Remote|Review for location",
  "location_reasoning": "Brief explanation of your decision based on reading the ENTIRE posting",
  "pay_range": "extracted pay or NOT_SPECIFIED",
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
            "pay_range": "NOT_SPECIFIED",
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
        pay_range = analysis.get("pay_range", "NOT_SPECIFIED")
        title_cleaned = analysis.get("title_cleaned", job.title)
        
        print(f"Location: {location_label}")
        print(f"Reasoning: {reasoning}")
        print(f"Pay: {pay_range}")
        
        if title_cleaned != job.title:
            print(f"Title cleaned: {title_cleaned}")
            stats["title_cleaned"] += 1
        
        if pay_range != "NOT_SPECIFIED":
            stats["pay_found"] += 1
        
        # Update statistics
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
            
            # Update title if cleaned
            if title_cleaned != job.title:
                conn.execute("UPDATE jobs SET title = ? WHERE id = ?", (title_cleaned, job.id))
                updates.append("title")
            
            # Store pay range in description if found
            if pay_range != "NOT_SPECIFIED" and job.description and pay_range not in job.description:
                new_desc = f"{job.description}\n\n[Pay Range: {pay_range}]"
                conn.execute("UPDATE jobs SET description = ? WHERE id = ?", (new_desc, job.id))
                updates.append("pay")
            
            if updates:
                conn.commit()
                print(f"✓ Updated: {', '.join(updates)}")
            else:
                print(f"✓ No updates needed")
        else:
            print(f"✓ Would update location_label to '{location_label}' (dry-run)")
    
    # Print summary
    print(f"\n{'='*60}")
    print("ANALYSIS SUMMARY")
    print(f"{'='*60}")
    print(f"Seattle: {stats['seattle']}")
    print(f"Remote: {stats['remote']}")
    print(f"Review for location: {stats['review']}")
    print(f"Pay ranges found: {stats['pay_found']}")
    print(f"Titles cleaned: {stats['title_cleaned']}")
    print(f"\nTotal processed: {len(jobs)}")
    
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
    print(f"Target: Seattle area (20mi from {SEATTLE_ZIP}) or remote")
    print("=" * 60)
    
    stats = process_jobs(job_ids=args.job_id, dry_run=args.dry_run)
    
    return 0


if __name__ == "__main__":
    exit(main())
