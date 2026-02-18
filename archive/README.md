# Archive

This directory contains scripts that are no longer actively used but preserved for reference.

## Scripts

### `clean_rss_files.py`
**Status**: Archived 2026-02-18  
**Reason**: No longer needed with unified pipeline

Originally cleaned RSS CSV files in-place (deduplicated by URL, stripped HTML from descriptions). The unified pipeline (`run_pipeline.py`) now stores jobs directly to the database, bypassing the CSV workflow entirely.

**Historical usage**:
```bash
python clean_rss_files.py  # Cleaned all jobs/rss_*.csv files
```

### `migrate_csvs.py`
**Status**: Archived 2026-02-18  
**Reason**: One-time migration complete

Originally migrated CSV files from `jobs/` directory into the SQLite database. The initial migration is complete, and new jobs are now added directly via the pipeline.

**Historical usage**:
```bash
python migrate_csvs.py  # Imported all jobs/*.csv into job_search.db
```

**Note**: If you need to manually import CSV files in the future, this script is still functional. You can move it back to the root directory or run it from here:
```bash
python archive/migrate_csvs.py
```

---

## Active Scripts

See the root directory for currently maintained scripts:
- `run_pipeline.py` - Unified job fetching pipeline
- `rss_job_feed.py` - RSS feed fetcher (used by pipeline)
- `startup_search.py` - Web search (used by pipeline)
- `filter_jobs_by_location.py` - Database location filter utility
