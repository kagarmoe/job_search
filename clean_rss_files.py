#!/usr/bin/env python3
"""
Combine all rss_*.csv files in the jobs directory into a single file,
with deduplication based on job URLs and HTML cleaning.
"""
import csv
import glob
import re
from pathlib import Path
from html import unescape


def clean_html(text: str) -> str:
    """
    Remove HTML tags and unescape HTML entities from text.

    Args:
        text: Text containing HTML

    Returns:
        Cleaned text without HTML tags
    """
    if not text:
        return ""

    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)

    # Replace multiple spaces with single space
    text = re.sub(r'\s+', ' ', text)

    # Unescape HTML entities (e.g., &amp; -> &, &lt; -> <)
    text = unescape(text)

    # Normalize all apostrophes to standard single quote
    # U+2018 ('), U+2019 ('), backtick (`)
    text = text.replace('\u2018', "'").replace('\u2019', "'").replace('`', "'")

    # Normalize dashes to standard hyphen-minus (ASCII hyphen)
    # En dash (–), Em dash (—), minus sign (−), horizontal bar (―)
    text = text.replace('–', '-').replace('—', '-').replace('−', '-').replace('―', '-')

    # Strip leading/trailing whitespace
    text = text.strip()

    return text


def deduplicate_csv(input_file: Path, output_file: Path, key_column: str = "URL") -> tuple[int, int]:
    """
    Deduplicate a CSV file based on a key column.

    Args:
        input_file: Path to input CSV file
        output_file: Path to output deduplicated CSV file
        key_column: Column name to use for deduplication (default: "URL")

    Returns:
        Tuple of (original_count, deduplicated_count)
    """
    seen_keys = set()
    unique_rows = []
    header = None
    original_count = 0

    # Read and deduplicate
    with open(input_file, 'r', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        header = reader.fieldnames

        for row in reader:
            original_count += 1
            key = row.get(key_column, "")

            if key and key not in seen_keys:
                seen_keys.add(key)

                # Clean HTML from Description field
                if "Description" in row:
                    row["Description"] = clean_html(row["Description"])

                unique_rows.append(row)

    # Write deduplicated data
    with open(output_file, 'w', newline='', encoding='utf-8') as outfile:
        writer = csv.DictWriter(outfile, fieldnames=header)
        writer.writeheader()
        writer.writerows(unique_rows)

    return original_count, len(unique_rows)


# Find all RSS CSV files
jobs_dir = Path("jobs")
rss_files = sorted(jobs_dir.glob("rss_*.csv"))

print(f"Found {len(rss_files)} RSS CSV files to combine:")
for f in rss_files:
    print(f"  - {f.name}")

# Output file
output_file = jobs_dir / "rss_jobs_combined.csv"

# Track statistics
total_rows = 0
rows_per_file = {}

# Combine files
with open(output_file, 'w', newline='', encoding='utf-8') as outfile:
    writer = None

    for i, input_file in enumerate(rss_files):
        with open(input_file, 'r', encoding='utf-8') as infile:
            reader = csv.reader(infile)

            # Read header
            header = next(reader)

            # Write header only once (from first file)
            if i == 0:
                writer = csv.writer(outfile)
                writer.writerow(header)

            # Write all data rows
            file_rows = 0
            for row in reader:
                writer.writerow(row)
                file_rows += 1
                total_rows += 1

            rows_per_file[input_file.name] = file_rows

print(f"\n✓ Combined {total_rows} rows into {output_file.name}")
print("\nBreakdown by file:")
for filename, count in rows_per_file.items():
    print(f"  {filename}: {count} rows")

# Deduplicate and clean HTML
print("\n--- Deduplicating & Cleaning HTML ---")
deduplicated_file = jobs_dir / "rss_jobs_deduplicated.csv"
original, unique = deduplicate_csv(output_file, deduplicated_file, key_column="URL")

duplicates_removed = original - unique
print(f"✓ Processed {output_file.name}")
print(f"  Original rows: {original}")
print(f"  Duplicates removed: {duplicates_removed}")
print(f"  Final unique rows: {unique}")
print(f"\n✓ Final cleaned file: {deduplicated_file.name}")
