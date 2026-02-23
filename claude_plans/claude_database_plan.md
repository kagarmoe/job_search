Plan: Set Up Database (kimberlygarmoe-1)

 Context

 The project stores job data in CSV files and profile data in a markdown file. We
  need a SQLite database as the foundation for all downstream epics: data
 pipeline, profile backend, scoring, job tracking, resume/cover letter
 generation, and Flask web app.

 Database Schema (Normalized — kimberlygarmoe-17)

 sources table — normalized job sources

 Column: id    | Type: INTEGER PK    | Notes: autoincrement
 Column: name  | Type: TEXT NOT NULL UNIQUE | Notes: "LinkedIn", "builtin.com", etc.

 feeds table — normalized feed info (absorbs former feed_fetch_log)

 Column: id         | Type: INTEGER PK    | Notes: autoincrement
 Column: name       | Type: TEXT NOT NULL UNIQUE | Notes: feed title
 Column: url        | Type: TEXT UNIQUE   | Notes: RSS feed URL (NULL for non-RSS)
 Column: source_id  | Type: INTEGER FK    | Notes: REFERENCES sources(id)
 Column: last_fetch | Type: TEXT          | Notes: ISO-8601 datetime of newest entry seen

 jobs table (serves Epics 2, 4, 5, 6)

 Column: id         | Type: INTEGER PK    | Notes: autoincrement
 Column: title      | Type: TEXT NOT NULL  | Notes:
 Column: url        | Type: TEXT NOT NULL UNIQUE | Notes: dedup key
 Column: description| Type: TEXT           | Notes: cleaned text, not HTML
 Column: posted_date| Type: TEXT           | Notes: ISO 8601
 Column: source_id  | Type: INTEGER FK     | Notes: REFERENCES sources(id)
 Column: feed_id    | Type: INTEGER FK     | Notes: REFERENCES feeds(id)
 Column: score      | Type: REAL           | Notes: 0-10, NULL until scored (Epic 4)
 Column: score_rationale | Type: TEXT      | Notes: LLM explanation (Epic 4)
 Column: status     | Type: TEXT NOT NULL DEFAULT 'new' | Notes: new|reviewed|applied|rejected|offer
 Column: location_label | Type: TEXT       | Notes: Seattle|Remote|Review for location
 Column: job_type   | Type: TEXT           | Notes:
 Column: pay_range  | Type: TEXT           | Notes:
 Column: contract_duration | Type: TEXT    | Notes:
 Column: resume_md  | Type: TEXT           | Notes: per-job tailored resume (Epic 6)
 Column: resume_pdf_path | Type: TEXT      | Notes: filesystem path (Epic 6)
 Column: cover_letter_md | Type: TEXT      | Notes: per-job cover letter (Epic 6)
 Column: cover_letter_pdf_path | Type: TEXT| Notes: filesystem path (Epic 6)
 Column: created_at | Type: TEXT           | Notes: auto-set on insert
 Column: updated_at | Type: TEXT           | Notes: auto-set on insert/update

 CHECK constraints: status IN allowed values, score 0-10 range.

 profile_meta table (Epic 3) — key-value for singleton fields

 Column: key
 Type: TEXT PK
 Notes: name, title, location, email, linkedin_url, github_url, summary
 ────────────────────────────────────────
 Column: value
 Type: TEXT NOT NULL
 Notes:

 job_history table (Epic 3)

 ┌─────────────┬───────────────┬────────────────────────────────────────┐
 │   Column    │     Type      │                 Notes                  │
 ├─────────────┼───────────────┼────────────────────────────────────────┤
 │ id          │ INTEGER PK    │                                        │
 ├─────────────┼───────────────┼────────────────────────────────────────┤
 │ company     │ TEXT NOT NULL │                                        │
 ├─────────────┼───────────────┼────────────────────────────────────────┤
 │ title       │ TEXT NOT NULL │                                        │
 ├─────────────┼───────────────┼────────────────────────────────────────┤
 │ start_date  │ TEXT          │ "YYYY-MM" or "YYYY" (profile has both) │
 ├─────────────┼───────────────┼────────────────────────────────────────┤
 │ end_date    │ TEXT          │ NULL = current                         │
 ├─────────────┼───────────────┼────────────────────────────────────────┤
 │ location    │ TEXT          │                                        │
 ├─────────────┼───────────────┼────────────────────────────────────────┤
 │ description │ TEXT          │                                        │
 ├─────────────┼───────────────┼────────────────────────────────────────┤
 │ sort_order  │ INTEGER       │ controls resume display order          │
 └─────────────┴───────────────┴────────────────────────────────────────┘

 education table (Epic 3)

 ┌─────────────┬───────────────┬───────┐
 │   Column    │     Type      │ Notes │
 ├─────────────┼───────────────┼───────┤
 │ id          │ INTEGER PK    │       │
 ├─────────────┼───────────────┼───────┤
 │ institution │ TEXT NOT NULL │       │
 ├─────────────┼───────────────┼───────┤
 │ degree      │ TEXT          │       │
 ├─────────────┼───────────────┼───────┤
 │ field       │ TEXT          │       │
 ├─────────────┼───────────────┼───────┤
 │ start_date  │ TEXT          │       │
 ├─────────────┼───────────────┼───────┤
 │ end_date    │ TEXT          │       │
 ├─────────────┼───────────────┼───────┤
 │ description │ TEXT          │       │
 ├─────────────┼───────────────┼───────┤
 │ sort_order  │ INTEGER       │       │
 └─────────────┴───────────────┴───────┘

 certifications table (Epic 3)

 ┌─────────────┬───────────────┬───────┐
 │   Column    │     Type      │ Notes │
 ├─────────────┼───────────────┼───────┤
 │ id          │ INTEGER PK    │       │
 ├─────────────┼───────────────┼───────┤
 │ name        │ TEXT NOT NULL │       │
 ├─────────────┼───────────────┼───────┤
 │ issuer      │ TEXT          │       │
 ├─────────────┼───────────────┼───────┤
 │ date_earned │ TEXT          │       │
 ├─────────────┼───────────────┼───────┤
 │ sort_order  │ INTEGER       │       │
 └─────────────┴───────────────┴───────┘

 honors table (Epic 3)

 ┌─────────────┬───────────────┬───────┐
 │   Column    │     Type      │ Notes │
 ├─────────────┼───────────────┼───────┤
 │ id          │ INTEGER PK    │       │
 ├─────────────┼───────────────┼───────┤
 │ name        │ TEXT NOT NULL │       │
 ├─────────────┼───────────────┼───────┤
 │ issuer      │ TEXT          │       │
 ├─────────────┼───────────────┼───────┤
 │ description │ TEXT          │       │
 ├─────────────┼───────────────┼───────┤
 │ sort_order  │ INTEGER       │       │
 └─────────────┴───────────────┴───────┘

 skills table (Epic 3)

 Column: id
 Type: INTEGER PK
 Notes:
 ────────────────────────────────────────
 Column: name
 Type: TEXT NOT NULL UNIQUE
 Notes:
 ────────────────────────────────────────
 Column: category
 Type: TEXT NOT NULL
 Notes: writing|api_dev_tools|ai_ml|content_strategy|taxonomy_ia|tools|languages
 ────────────────────────────────────────
 Column: proficiency
 Type: TEXT
 Notes: expert|advanced|intermediate|familiar
 ────────────────────────────────────────
 Column: sort_order
 Type: INTEGER
 Notes:

 Indexes

 - jobs(url) — UNIQUE (implicit from constraint)
 - jobs(status) — filter by status
 - jobs(score) — sort by relevance
 - jobs(posted_date) — sort by recency
 - jobs(status, score DESC) — composite for "new jobs by best score"
 - jobs(source_id) — FK join optimization
 - jobs(feed_id) — FK join optimization
 - jobs(location_label) — filter by location
 - feeds(source_id) — FK join optimization
 - skills(category) — filter skills by taxonomy category

 Module Structure

 db/
   __init__.py                # exports get_db(), init_db()
   connection.py              # get_db() with WAL mode, Row factory
   schema.py                  # all DDL as string constants
   models.py                  # dataclasses: Source, Feed, Job, Skill, etc.
   feeds.py                   # sources/feeds CRUD + fetch timestamps
   jobs.py                    # full CRUD for jobs (upsert resolves names→IDs)
   profile.py                 # stub CRUD for profile tables
   migrate_001_normalize.py   # migration: denormalized → normalized schema


 - DB file: job_search.db at project root (added to .gitignore)
 - get_db() sets row_factory=sqlite3.Row, journal_mode=WAL, foreign_keys=ON
 - init_db() runs executescript() with all DDL — idempotent via IF NOT EXISTS

 Key design: upsert_job()

 Uses INSERT ... ON CONFLICT(url) DO UPDATE to handle dedup. Updates
 title/description/date/source_id/feed_id but preserves user-set fields
 (score, status, resume, cover letter).

 Callers pass human-readable source/feed names as strings. The function
 resolves them to FK IDs internally via get_or_create_source/feed helpers.
 An optional feed_url parameter populates the feeds.url column for RSS feeds.

 Implementation Steps

 1. Create db/ directory
 2. Write db/schema.py — all CREATE TABLE + CREATE INDEX statements
 3. Write db/connection.py — get_db(), close_db()
 4. Write db/models.py — dataclasses for all tables
 5. Write db/jobs.py — full CRUD for jobs table
 6. Write db/profile.py — stub CRUD for profile tables
 7. Write db/__init__.py — package exports
 8. Add job_search.db to .gitignore
 9. Write + run a smoke test to verify schema creation, insert, dedup, and
 queries

 Scope Boundary

 This issue (kimberlygarmoe-1): schema, db module, CRUD helpers, .gitignore,
 smoke test

 Downstream issues (not touched):
 - CSV migration → kimberlygarmoe-2.4
 - Profile data population → kimberlygarmoe-3.3
 - Scoring logic → Epic 4
 - Resume/cover letter generation → Epic 6
 - Flask integration → Epic 8

 Verification

 1. Run python -m db.setup (or equivalent) — creates job_search.db with all
 tables
 2. Run smoke test: insert a job, retrieve it, insert same URL again (verify
 upsert), list with filters, update status
 3. Verify .gitignore excludes job_search.db