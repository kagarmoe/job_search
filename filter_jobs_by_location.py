#!/usr/bin/env python3
"""Filter the jobs database to only keep Seattle metro and truly remote jobs.

Removes jobs that are not in the greater Seattle area and not truly remote.
"""

import re
import sqlite3

SEATTLE_METRO = ["Seattle", "Bellevue", "Redmond", "Kirkland", "Bothell", "Renton", "Kent", "Federal Way", "Sammamish", "Issaquah", "Tacoma", "Olympia"]

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


def is_truly_remote(description: str, title: str = "") -> bool:
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
    conn = sqlite3.connect("job_search.db")
    conn.row_factory = sqlite3.Row

    rows = conn.execute("SELECT id, title, description FROM jobs ORDER BY title").fetchall()

    keep = []
    remove = []

    for row in rows:
        title = row["title"]
        desc = row["description"] or ""

        if is_seattle(title):
            keep.append((row["id"], title, "seattle"))
        elif is_us_wide(title):
            keep.append((row["id"], title, "us-wide"))
        elif is_truly_remote(desc, title):
            keep.append((row["id"], title, "remote"))
        else:
            remove.append((row["id"], title))

    print(f"=== KEEP ({len(keep)}) ===\n")
    for id, title, reason in keep:
        print(f"  [{reason:7s}] {title}")

    print(f"\n=== REMOVE ({len(remove)}) ===\n")
    for id, title in remove:
        print(f"  {title}")

    if remove:
        ids = [r[0] for r in remove]
        placeholders = ",".join("?" * len(ids))
        conn.execute(f"DELETE FROM jobs WHERE id IN ({placeholders})", ids)
        conn.commit()
        print(f"\nDeleted {len(remove)} jobs from database.")

    remaining = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    print(f"Jobs remaining: {remaining}")
    conn.close()


if __name__ == "__main__":
    main()
