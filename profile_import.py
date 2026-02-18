#!/usr/bin/env python3
"""Import profile data from LinkedIn_Profile.md into SQLite database.

Parses the markdown resume and populates:
- profile_meta (name, email, title, summary, etc.)
- job_history (work experience)
- education
- skills (with categories)

Usage:
    python profile_import.py [--profile PATH]
"""

import argparse
import re
from pathlib import Path

from db.connection import init_db
from db.profile import (
    set_meta,
    add_job_history,
    add_education,
    add_skill,
)


def parse_profile_markdown(md_path: Path) -> dict:
    """Parse LinkedIn profile markdown and extract structured data."""
    content = md_path.read_text()
    
    profile = {
        "meta": {},
        "job_history": [],
        "education": [],
        "skills": [],
    }
    
    # Extract name (first line, h1)
    name_match = re.search(r'^# (.+)$', content, re.MULTILINE)
    if name_match:
        profile["meta"]["name"] = name_match.group(1).strip()
    
    # Extract current title and location (lines 3-4)
    title_match = re.search(r'\*\*(.+?)\*\*\n(.+)', content)
    if title_match:
        profile["meta"]["title"] = title_match.group(1).strip()
        profile["meta"]["location"] = title_match.group(2).strip()
    
    # Extract contact info
    email_match = re.search(r'- ([\w\.-]+@[\w\.-]+)', content)
    if email_match:
        profile["meta"]["email"] = email_match.group(1)
    
    linkedin_match = re.search(r'\[LinkedIn\]\((https://[^\)]+)\)', content)
    if linkedin_match:
        profile["meta"]["linkedin"] = linkedin_match.group(1)
    
    github_match = re.search(r'\[GitHub\]\((https://[^\)]+)\)', content)
    if github_match:
        profile["meta"]["github"] = github_match.group(1)
    
    # Extract summary (## Summary section)
    summary_match = re.search(r'## Summary\n\n(.+?)(?=\n## )', content, re.DOTALL)
    if summary_match:
        profile["meta"]["summary"] = summary_match.group(1).strip()
    
    # Extract work experience (## Experience section)
    exp_section = re.search(r'## Experience\n\n(.+?)(?=\n## Education)', content, re.DOTALL)
    if exp_section:
        exp_text = exp_section.group(1)
        # Parse each job entry (### Company, **Title**, dates)
        jobs = re.finditer(
            r'### (.+?)\n\n\*\*(.+?)\*\*\n(.+?)\n(.+?)\n\n(.+?)(?=\n### |\Z)',
            exp_text,
            re.DOTALL
        )
        
        sort_order = 0
        for job in jobs:
            company = job.group(1).strip()
            title = job.group(2).strip()
            dates = job.group(3).strip()
            location = job.group(4).strip()
            description = job.group(5).strip()
            
            # Parse dates (e.g., "October 2022 - January 2026")
            date_match = re.match(r'(\w+ \d{4}) - (\w+ \d{4})', dates)
            start_date = date_match.group(1) if date_match else None
            end_date = date_match.group(2) if date_match else None
            
            profile["job_history"].append({
                "company": company,
                "title": title,
                "start_date": start_date,
                "end_date": end_date,
                "location": location,
                "description": description,
                "sort_order": sort_order,
            })
            sort_order += 1
    
    # Extract education (## Education section)
    edu_section = re.search(r'## Education\n\n(.+?)(?=\n## |\Z)', content, re.DOTALL)
    if edu_section:
        edu_text = edu_section.group(1)
        # Parse each education entry (### Institution, degree info)
        schools = re.finditer(
            r'### (.+?)\n\n(.+?)(?=\n### |\Z)',
            edu_text,
            re.DOTALL
        )
        
        sort_order = 0
        for school in schools:
            institution = school.group(1).strip()
            details = school.group(2).strip()
            
            # Try to parse degree and field
            degree_match = re.match(r'([^,]+)(?:, (.+))?', details)
            degree = degree_match.group(1) if degree_match else details
            field = degree_match.group(2) if degree_match and degree_match.group(2) else None
            
            profile["education"].append({
                "institution": institution,
                "degree": degree,
                "field": field,
                "sort_order": sort_order,
            })
            sort_order += 1
    
    # Extract skills from Top Skills and Languages sections
    top_skills = re.search(r'## Top Skills\n\n(.+?)(?=\n## )', content, re.DOTALL)
    if top_skills:
        for line in top_skills.group(1).strip().split('\n'):
            if line.startswith('- '):
                skill_name = line[2:].strip()
                profile["skills"].append({
                    "name": skill_name,
                    "category": "writing",  # Default category
                    "proficiency": "expert",
                })
    
    languages = re.search(r'## Languages\n\n(.+?)(?=\n## )', content, re.DOTALL)
    if languages:
        for line in languages.group(1).strip().split('\n'):
            if line.startswith('- '):
                lang_text = line[2:].strip()
                # Parse "Python" or "German (Professional Working)"
                lang_match = re.match(r'([^\(]+)(?:\s*\((.+)\))?', lang_text)
                skill_name = lang_match.group(1).strip()
                proficiency = lang_match.group(2).lower() if lang_match.group(2) else "advanced"
                
                # Map proficiency text to our enum
                if "professional" in proficiency or "working" in proficiency:
                    prof_level = "advanced"
                else:
                    prof_level = "expert"
                
                # Programming languages vs human languages
                if skill_name in ["Python", "JavaScript", "Ruby"]:
                    category = "tools"
                else:
                    category = "languages"
                
                profile["skills"].append({
                    "name": skill_name,
                    "category": category,
                    "proficiency": prof_level,
                })
    
    return profile


def import_profile(profile: dict, conn) -> None:
    """Import parsed profile data into database."""
    # Import profile metadata
    print("Importing profile metadata...")
    for key, value in profile["meta"].items():
        set_meta(key, value, db=conn)
        print(f"  {key}: {value[:60] if len(str(value)) > 60 else value}...")
    
    # Import job history
    print(f"\nImporting {len(profile['job_history'])} job history entries...")
    for job in profile["job_history"]:
        entry = add_job_history(**job, db=conn)
        print(f"  {job['company']}: {job['title']}")
    
    # Import education
    print(f"\nImporting {len(profile['education'])} education entries...")
    for edu in profile["education"]:
        entry = add_education(**edu, db=conn)
        print(f"  {edu['institution']}: {edu['degree']}")
    
    # Import skills
    print(f"\nImporting {len(profile['skills'])} skills...")
    for skill in profile["skills"]:
        entry = add_skill(**skill, db=conn)
        print(f"  {skill['name']} ({skill['category']})")


def main():
    parser = argparse.ArgumentParser(
        description="Import LinkedIn profile into database"
    )
    parser.add_argument(
        "--profile",
        type=Path,
        default=Path("resumes/LinkedIn_Profile.md"),
        help="Path to LinkedIn profile markdown file",
    )
    args = parser.parse_args()
    
    if not args.profile.exists():
        print(f"Error: Profile not found at {args.profile}")
        return 1
    
    print(f"Parsing profile from {args.profile}...")
    profile = parse_profile_markdown(args.profile)
    
    print(f"\nParsed profile for: {profile['meta'].get('name', 'Unknown')}")
    print(f"  Job history: {len(profile['job_history'])} entries")
    print(f"  Education: {len(profile['education'])} entries")
    print(f"  Skills: {len(profile['skills'])} entries")
    
    # Initialize database
    conn = init_db()
    
    # Import data
    print("\n" + "=" * 60)
    import_profile(profile, conn)
    print("=" * 60)
    print("\n✓ Profile import complete!")
    
    return 0


if __name__ == "__main__":
    exit(main())
