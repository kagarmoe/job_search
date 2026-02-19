"""DDL statements for the job_search database.

All statements use IF NOT EXISTS so init_db() is idempotent.
"""

SCHEMA_SQL = """
-- Jobs table: core entity for all job listings
CREATE TABLE IF NOT EXISTS jobs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT NOT NULL,
    url             TEXT NOT NULL UNIQUE,
    description     TEXT,
    posted_date     TEXT,
    source          TEXT,
    feed            TEXT,
    score           REAL CHECK (score IS NULL OR (score >= 0 AND score <= 10)),
    score_rationale TEXT,
    status          TEXT NOT NULL DEFAULT 'new'
                        CHECK (status IN ('new', 'reviewed', 'applied', 'rejected', 'offer')),
    location_label  TEXT CHECK (location_label IS NULL OR location_label IN ('Seattle', 'Remote', 'Review for location')),
    job_type        TEXT,
    pay_range       TEXT,
    contract_duration TEXT,
    resume_md           TEXT,
    resume_pdf_path     TEXT,
    cover_letter_md     TEXT,
    cover_letter_pdf_path TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now'))
);

-- Trigger to auto-update updated_at on any row change
CREATE TRIGGER IF NOT EXISTS jobs_updated_at
    AFTER UPDATE ON jobs
    FOR EACH ROW
BEGIN
    UPDATE jobs SET updated_at = strftime('%Y-%m-%dT%H:%M:%S', 'now')
    WHERE id = OLD.id;
END;

-- Profile metadata: key-value store for singleton fields
CREATE TABLE IF NOT EXISTS profile_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Job history (work experience)
CREATE TABLE IF NOT EXISTS job_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    company     TEXT NOT NULL,
    title       TEXT NOT NULL,
    start_date  TEXT,
    end_date    TEXT,
    location    TEXT,
    description TEXT,
    sort_order  INTEGER
);

-- Education
CREATE TABLE IF NOT EXISTS education (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    institution TEXT NOT NULL,
    degree      TEXT,
    field       TEXT,
    start_date  TEXT,
    end_date    TEXT,
    description TEXT,
    sort_order  INTEGER
);

-- Certifications
CREATE TABLE IF NOT EXISTS certifications (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    issuer      TEXT,
    date_earned TEXT,
    sort_order  INTEGER
);

-- Honors and awards
CREATE TABLE IF NOT EXISTS honors (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    issuer      TEXT,
    description TEXT,
    sort_order  INTEGER
);

-- Skills with taxonomy categories
CREATE TABLE IF NOT EXISTS skills (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    category    TEXT NOT NULL
                    CHECK (category IN (
                        'writing', 'api_dev_tools', 'ai_ml',
                        'content_strategy', 'taxonomy_ia', 'tools', 'languages'
                    )),
    proficiency TEXT CHECK (proficiency IS NULL OR proficiency IN (
                        'expert', 'advanced', 'intermediate', 'familiar'
                    )),
    sort_order  INTEGER
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_jobs_status      ON jobs (status);
CREATE INDEX IF NOT EXISTS idx_jobs_score       ON jobs (score);
CREATE INDEX IF NOT EXISTS idx_jobs_posted_date ON jobs (posted_date);
CREATE INDEX IF NOT EXISTS idx_jobs_status_score ON jobs (status, score DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_location_label ON jobs (location_label);
CREATE INDEX IF NOT EXISTS idx_skills_category  ON skills (category);
"""
