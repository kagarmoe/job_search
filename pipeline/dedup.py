"""Deduplicate job postings based on normalized titles.

Groups jobs by normalized title (location suffix stripped), clusters by
posting date, and keeps the posting with the richest description.
"""

import argparse
import re
from collections import defaultdict
from datetime import datetime

from db.connection import get_db
from db.jobs import delete_job


def __parse_date(d):
    """Parse a date string from the database for dedup clustering."""
    if not d:
        return datetime.min
    try:
        return datetime.fromisoformat(d.split(" ")[0])
    except ValueError:
        return datetime.min


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

        jobs.sort(key=lambda j: __parse_date(j["posted_date"]))

        # Cluster by time window
        clusters: list[list[dict]] = []
        for job in jobs:
            job_date = _parse_date(job["posted_date"])
            if clusters and (job_date - _parse_date(clusters[-1][0]["posted_date"])).days <= window_days:
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
        description="Remove duplicate job postings based on normalized title"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview deduplication without making changes",
    )
    args = parser.parse_args()

    print("Job Deduplication")
    print("=" * 60)
    deduplicate_jobs(dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    exit(main())
