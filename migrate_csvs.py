#!/usr/bin/env python3
"""Migrate all CSV files in jobs/ into the SQLite database."""

import csv
from pathlib import Path

from db.connection import init_db
from db.jobs import upsert_job

JOBS_DIR = Path("jobs")


def migrate_csv(filepath: Path, conn) -> tuple[int, int]:
    """Load a single CSV into the database.

    Returns:
        Tuple of (rows_read, rows_inserted_or_updated)
    """
    rows_read = 0
    rows_upserted = 0

    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows_read += 1
            title = row.get("Job Title", "").strip()
            url = row.get("URL", "").strip()

            if not title or not url:
                continue

            upsert_job(
                title=title,
                url=url,
                description=row.get("Description", "").strip() or None,
                posted_date=row.get("Posted Date", "").strip() or None,
                source=row.get("Source", "").strip() or None,
                feed=row.get("Feed", "").strip() or None,
                db=conn,
            )
            rows_upserted += 1

    return rows_read, rows_upserted


def main():
    conn = init_db()

    csv_files = sorted(JOBS_DIR.glob("*.csv"))
    print(f"Found {len(csv_files)} CSV files in {JOBS_DIR}/\n")

    total_read = 0
    total_upserted = 0

    for filepath in csv_files:
        read, upserted = migrate_csv(filepath, conn)
        total_read += read
        total_upserted += upserted
        print(f"  {filepath.name}: {read} rows read, {upserted} upserted")

    # Check final count
    count = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    print(f"\nTotal: {total_read} rows read, {total_upserted} upserted")
    print(f"Jobs in database: {count} (duplicates across files were merged)")


if __name__ == "__main__":
    main()
