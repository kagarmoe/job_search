"""Location filtering for job postings.

Provides helpers to identify Seattle-area, US-wide, and remote job postings
using regex patterns against title and description text. The main() function
uses these to filter a jobs table.
"""

import re

from pipeline.constants import SEATTLE_METRO
from db.jobs import list_jobs, delete_job

# Single regex matching any metro city followed by ", WA" anywhere in a title
_SEATTLE_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(c) for c in SEATTLE_METRO) + r"),\s*WA\b",
    re.IGNORECASE,
)

# Patterns that indicate truly remote (checked against description)
REMOTE_POSITIVE = re.compile(
    r"(?:fully\s+remote|location\s*:\s*remote|role\s+(?:type|is)\s*:\s*remote|"
    r"remote\s+(?:position|role|work|opportunity|\()|"
    r"\bremote\b.*\bUSA\b|\bUSA\b.*\bremote\b|"
    r"(?:100%|completely|entirely)\s+remote|"
    r"listed\s+as\s+remote|"
    r"\bremote\s+if\s+located)",
    re.IGNORECASE,
)

# Patterns that negate remote (checked against description and title)
REMOTE_NEGATIVE = re.compile(
    r"not\s+(?:a\s+)?remote|not\s+offer\s+remote|remote\s+(?:operations?|assistance|sensing|control)",
    re.IGNORECASE,
)

# "Remote" in a title used as a location indicator (not part of a compound term)
_REMOTE_TITLE_RE = re.compile(r"\bremote\b", re.IGNORECASE)


def is_seattle(title: str) -> bool:
    """Match any SEATTLE_METRO city followed by ', WA' anywhere in the title."""
    return bool(_SEATTLE_RE.search(title))


def is_us_wide(title: str) -> bool:
    """Jobs listed as 'in United States' — may be remote, keep for review."""
    return title.endswith("in United States")


def is_truly_remote(description: str | None, title: str = "") -> bool:
    """Check if a job is truly remote based on description and/or title.

    Checks the title for 'Remote' as a location indicator (e.g. '(Remote - US)'),
    then falls back to description-based pattern matching.
    """
    # Title check: "Remote" in title, unless it's "Remote Operations" etc.
    if title and _REMOTE_TITLE_RE.search(title) and not REMOTE_NEGATIVE.search(title):
        return True

    # Description check
    if not description:
        return False
    return bool(REMOTE_POSITIVE.search(description)) and not bool(
        REMOTE_NEGATIVE.search(description)
    )


def main():
    all_jobs = list_jobs(order_by="title ASC")

    keep = []
    remove = []

    for job in all_jobs:
        desc = job.description or ""

        if is_seattle(job.title):
            keep.append((job.id, job.title, "seattle"))
        elif is_us_wide(job.title):
            keep.append((job.id, job.title, "us-wide"))
        elif is_truly_remote(desc, job.title):
            keep.append((job.id, job.title, "remote"))
        else:
            remove.append((job.id, job.title))

    print(f"=== KEEP ({len(keep)}) ===\n")
    for jid, title, reason in keep:
        print(f"  [{reason:7s}] {title}")

    print(f"\n=== REMOVE ({len(remove)}) ===\n")
    for jid, title in remove:
        print(f"  {title}")

    if remove:
        for jid, title in remove:
            delete_job(jid)
        print(f"\nDeleted {len(remove)} jobs from database.")

    remaining = len(all_jobs) - len(remove)
    print(f"Jobs remaining: {remaining}")


if __name__ == "__main__":
    main()
