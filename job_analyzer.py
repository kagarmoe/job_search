#!/usr/bin/env python3
"""LLM-powered job analyzer for location verification and data extraction.

Analyzes job postings to:
1. Verify if job is truly Seattle-area (within 20 miles of 98117) or remote
2. Extract pay range information
3. Clean up title formatting issues

Jobs that clearly don't meet location criteria are marked for deletion.
Uncertain cases are kept for manual review.

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

ANALYSIS_PROMPT = """You are analyzing a job posting to determine if it meets location criteria and extract key information.

TARGET LOCATION: Within 20 miles of Seattle, WA (zip 98117) OR fully remote work allowed.

Analyze this job posting carefully:

TITLE: {title}
DESCRIPTION: {description}
SOURCE: {source}

Your tasks:
1. LOCATION DECISION: Determine if this job meets our criteria
   - Read the ENTIRE posting carefully
   - Look for location information in both title and description
   - Pay special attention to remote work policies (some jobs claim remote in title but require onsite in description)
   - Check for Seattle metro area locations: Seattle, Bellevue, Redmond, Kirkland, Bothell, etc.
   - IMPORTANT: If a job says "remote" in title but then says "on-site required" or "hybrid with X days onsite in [far location]", it does NOT meet criteria
   
   Return one of:
   - "KEEP" - Clearly meets criteria (Seattle area OR truly remote)
   - "DELETE" - Clearly does not meet criteria (wrong location, not remote)
   - "UNCERTAIN" - Cannot determine from posting (keep for manual review)

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
  "location_decision": "KEEP|DELETE|UNCERTAIN",
  "location_reasoning": "Brief explanation of your decision",
  "pay_range": "extracted pay or NOT_SPECIFIED",
  "title_cleaned": "cleaned title text",
  "remote_work": true|false|null
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
            "location_decision": "UNCERTAIN",
            "location_reasoning": f"Analysis failed: {str(e)}",
            "pay_range": "NOT_SPECIFIED",
            "title_cleaned": job.title,
            "remote_work": None
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
        "kept": 0,
        "deleted": 0,
        "uncertain": 0,
        "pay_found": 0,
        "title_cleaned": 0
    }
    
    for job in jobs:
        print(f"\n{'='*60}")
        print(f"Job {job.id}: {job.title[:80]}")
        print(f"{'='*60}")
        
        # Analyze job
        analysis = analyze_job(job)
        
        decision = analysis.get("location_decision", "UNCERTAIN")
        reasoning = analysis.get("location_reasoning", "")
        pay_range = analysis.get("pay_range", "NOT_SPECIFIED")
        title_cleaned = analysis.get("title_cleaned", job.title)
        remote_work = analysis.get("remote_work")
        
        print(f"Decision: {decision}")
        print(f"Reasoning: {reasoning}")
        print(f"Pay: {pay_range}")
        print(f"Remote: {remote_work}")
        
        if title_cleaned != job.title:
            print(f"Title cleaned: {title_cleaned}")
            stats["title_cleaned"] += 1
        
        if pay_range != "NOT_SPECIFIED":
            stats["pay_found"] += 1
        
        # Take action based on decision
        if decision == "DELETE":
            stats["deleted"] += 1
            if not dry_run:
                delete_job(job.id)
                print(f"❌ DELETED")
            else:
                print(f"❌ Would delete (dry-run)")
        
        elif decision == "KEEP":
            stats["kept"] += 1
            if not dry_run:
                # Update job with cleaned title and pay info if found
                updates = []
                if title_cleaned != job.title:
                    conn.execute("UPDATE jobs SET title = ? WHERE id = ?", (title_cleaned, job.id))
                    updates.append("title")
                
                # Store pay range in description metadata or create a new field
                # For now, we'll add it as a note at the end of description if not present
                if pay_range != "NOT_SPECIFIED" and job.description and pay_range not in job.description:
                    new_desc = f"{job.description}\n\n[Pay Range: {pay_range}]"
                    conn.execute("UPDATE jobs SET description = ? WHERE id = ?", (new_desc, job.id))
                    updates.append("pay")
                
                if updates:
                    conn.commit()
                    print(f"✓ KEPT (updated: {', '.join(updates)})")
                else:
                    print(f"✓ KEPT")
            else:
                print(f"✓ Would keep (dry-run)")
        
        else:  # UNCERTAIN
            stats["uncertain"] += 1
            print(f"⚠️  UNCERTAIN - kept for manual review")
    
    # Print summary
    print(f"\n{'='*60}")
    print("ANALYSIS SUMMARY")
    print(f"{'='*60}")
    print(f"Kept: {stats['kept']}")
    print(f"Deleted: {stats['deleted']}")
    print(f"Uncertain: {stats['uncertain']}")
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
