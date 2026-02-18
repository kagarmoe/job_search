#!/usr/bin/env python3
"""
Clean all rss_*.csv files in the jobs directory in-place:
deduplicate based on job URLs and strip HTML from descriptions.
"""
import csv
import re
from pathlib import Path
from html import unescape


def clean_html(text: str) -> str:
    """Remove HTML tags and unescape HTML entities from text."""
    if not text:
        return ""

    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)

    # Replace multiple spaces with single space
    text = re.sub(r'\s+', ' ', text)

    # Unescape HTML entities (e.g., &amp; -> &, &lt; -> <)
    text = unescape(text)

    # Normalize all apostrophes to standard single quote
    text = text.replace('\u2018', "'").replace('\u2019', "'").replace('`', "'")

    # Normalize dashes to standard hyphen-minus
    text = text.replace('\u2013', '-').replace('\u2014', '-').replace('\u2212', '-').replace('\u2015', '-')

    return text.strip()


def clean_csv(filepath: Path) -> tuple[int, int]:
    """Clean a single CSV file in-place: dedup by URL and strip HTML.

    Returns:
        Tuple of (original_count, final_count)
    """
    seen_urls = set()
    unique_rows = []
    header = None
    original_count = 0

    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames

        for row in reader:
            original_count += 1
            url = row.get("URL", "")

            if url and url not in seen_urls:
                seen_urls.add(url)

                if "Description" in row:
                    row["Description"] = clean_html(row["Description"])

                unique_rows.append(row)

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(unique_rows)

    return original_count, len(unique_rows)


jobs_dir = Path("jobs")
rss_files = sorted(jobs_dir.glob("rss_*.csv"))

print(f"Found {len(rss_files)} RSS CSV files to clean:\n")

for filepath in rss_files:
    original, final = clean_csv(filepath)
    dupes = original - final
    print(f"  {filepath.name}: {original} -> {final} rows ({dupes} duplicates removed)")

print(f"\n✓ Done. Cleaned {len(rss_files)} files in-place.")
