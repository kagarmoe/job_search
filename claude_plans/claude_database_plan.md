# Database Schema Reference

SQLite database at `job_search.db` (project root, gitignored).
Connection uses WAL mode, Row factory, and foreign_keys=ON.
All DDL uses IF NOT EXISTS — `init_db()` is idempotent.

## Tables

### sources

Normalized job sources (e.g., "LinkedIn", "builtin.com").

| Column | Type              | Notes |
|--------|-------------------|-------|
| id     | INTEGER PK        | autoincrement |
| name   | TEXT NOT NULL UNIQUE | source name |

### feeds

Normalized feed info. Absorbs the former `feed_fetch_log` table.

| Column     | Type              | Notes |
|------------|-------------------|-------|
| id         | INTEGER PK        | autoincrement |
| name       | TEXT NOT NULL UNIQUE | feed title |
| url        | TEXT UNIQUE       | RSS feed URL; NULL for non-RSS feeds |
| source_id  | INTEGER FK        | REFERENCES sources(id) |
| last_fetch | TEXT              | ISO-8601 datetime of newest entry seen |

### jobs

Core entity for all job listings.

| Column                | Type              | Notes |
|-----------------------|-------------------|-------|
| id                    | INTEGER PK        | autoincrement |
| title                 | TEXT NOT NULL      | |
| url                   | TEXT NOT NULL UNIQUE | dedup key |
| description           | TEXT              | |
| posted_date           | TEXT              | ISO 8601 |
| source_id             | INTEGER FK        | REFERENCES sources(id) |
| feed_id               | INTEGER FK        | REFERENCES feeds(id) |
| score                 | REAL              | 0-10; NULL until scored |
| score_rationale       | TEXT              | LLM explanation |
| status                | TEXT NOT NULL DEFAULT 'new' | CHECK: new\|reviewed\|applied\|rejected\|offer |
| location_label        | TEXT              | CHECK: Seattle\|Remote\|Review for location |
| job_type              | TEXT              | |
| pay_range             | TEXT              | |
| contract_duration     | TEXT              | |
| resume_md             | TEXT              | per-job tailored resume markdown |
| resume_pdf_path       | TEXT              | filesystem path to generated PDF |
| cover_letter_md       | TEXT              | per-job cover letter markdown |
| cover_letter_pdf_path | TEXT              | filesystem path to generated PDF |
| created_at            | TEXT NOT NULL      | auto-set on insert |
| updated_at            | TEXT NOT NULL      | auto-set on insert and update (via trigger) |

### profile_meta

Key-value store for singleton profile fields.

| Column | Type           | Notes |
|--------|----------------|-------|
| key    | TEXT PK        | name, title, location, email, linkedin_url, github_url, summary |
| value  | TEXT NOT NULL   | |

### job_history

Work experience entries.

| Column      | Type           | Notes |
|-------------|----------------|-------|
| id          | INTEGER PK     | autoincrement |
| company     | TEXT NOT NULL   | |
| title       | TEXT NOT NULL   | |
| start_date  | TEXT           | YYYY-MM or YYYY |
| end_date    | TEXT           | NULL = current |
| location    | TEXT           | |
| description | TEXT           | |
| sort_order  | INTEGER        | controls resume display order |

### education

| Column      | Type           | Notes |
|-------------|----------------|-------|
| id          | INTEGER PK     | autoincrement |
| institution | TEXT NOT NULL   | |
| degree      | TEXT           | |
| field       | TEXT           | |
| start_date  | TEXT           | |
| end_date    | TEXT           | |
| description | TEXT           | |
| sort_order  | INTEGER        | |

### certifications

| Column      | Type           | Notes |
|-------------|----------------|-------|
| id          | INTEGER PK     | autoincrement |
| name        | TEXT NOT NULL   | |
| issuer      | TEXT           | |
| date_earned | TEXT           | |
| sort_order  | INTEGER        | |

### honors

| Column      | Type           | Notes |
|-------------|----------------|-------|
| id          | INTEGER PK     | autoincrement |
| name        | TEXT NOT NULL   | |
| issuer      | TEXT           | |
| description | TEXT           | |
| sort_order  | INTEGER        | |

### skills

| Column      | Type              | Notes |
|-------------|-------------------|-------|
| id          | INTEGER PK        | autoincrement |
| name        | TEXT NOT NULL UNIQUE | |
| category    | TEXT NOT NULL      | CHECK: writing\|api_dev_tools\|ai_ml\|content_strategy\|taxonomy_ia\|tools\|languages |
| proficiency | TEXT              | CHECK: expert\|advanced\|intermediate\|familiar |
| sort_order  | INTEGER           | |

## Indexes

| Index                    | Column(s)          | Notes |
|--------------------------|--------------------|-------|
| jobs(url)                | url                | implicit UNIQUE constraint |
| idx_jobs_status          | status             | filter by status |
| idx_jobs_score           | score              | sort by relevance |
| idx_jobs_posted_date     | posted_date        | sort by recency |
| idx_jobs_status_score    | status, score DESC | composite for "new jobs by best score" |
| idx_jobs_location_label  | location_label     | filter by location |
| idx_jobs_source_id       | source_id          | FK join optimization |
| idx_jobs_feed_id         | feed_id            | FK join optimization |
| idx_feeds_source_id      | source_id          | FK join optimization |
| idx_skills_category      | category           | filter skills by taxonomy category |

## Triggers

- **jobs_updated_at** — AFTER UPDATE on jobs, auto-sets `updated_at` to current timestamp.

## Module Structure

```
db/
  __init__.py                # exports get_db(), init_db(), close_db()
  connection.py              # get_db() with WAL mode, Row factory, foreign_keys
  schema.py                  # all DDL as string constants
  models.py                  # dataclasses: Source, Feed, Job, Skill, etc.
  feeds.py                   # sources/feeds CRUD + fetch timestamp helpers
  jobs.py                    # full CRUD for jobs (upsert resolves names to IDs)
  profile.py                 # CRUD for profile tables
  smoke_test.py              # comprehensive smoke test suite
  migrate_001_normalize.py   # migration: denormalized → normalized schema
```

## Key Design: upsert_job()

Uses `INSERT ... ON CONFLICT(url) DO UPDATE` for dedup. Updates title, description,
posted_date, source_id, and feed_id but preserves user-set fields (score, status,
location_label, resume, cover letter).

Callers pass human-readable source/feed names as strings. The function resolves
them to FK IDs internally via `get_or_create_source()` / `get_or_create_feed()`.
An optional `feed_url` parameter populates `feeds.url` for RSS feeds.

## Key Design: list_jobs()

JOINs sources and feeds tables to return `Job` objects with human-readable
`source` and `feed` name strings for display. Supports filtering by status,
source name, min_score, and configurable ordering.
