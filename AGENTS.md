# AGENTS.md

**Agent guide for the job_search repository**

This repository contains a Python-based job search automation system that aggregates job listings from RSS feeds and web searches, stores them in SQLite, and uses Beads for issue tracking. The project is designed to help automate and organize a personal job search workflow.

---

## Project Overview

**Type**: Python 3.10+ application with SQLite database  
**Purpose**: Aggregate job listings from multiple sources, filter by location/preferences, store in database, and manage application workflow  
**Owner**: Individual job seeker (Kimberly Garmoe)  
**Target roles**: Technical Writer, Information Architecture, Taxonomy, Content Strategy

---

## Core Components

### 1. **Database Layer** (`db/`)

SQLite database (`job_search.db`) with the following structure:

- **`jobs`** - Core entity for all job listings
  - Fields: `id`, `title`, `url` (unique), `description`, `posted_date`, `source`, `feed`
  - Tracking: `score` (0-10), `score_rationale`, `status` (new|reviewed|applied|rejected|offer)
  - Application materials: `resume_md`, `resume_pdf_path`, `cover_letter_md`, `cover_letter_pdf_path`
  - Timestamps: `created_at`, `updated_at` (auto-updated via trigger)
  - URL is the unique key - upserts preserve user-set fields (score, status, resumes)

- **Profile tables** - Resume/profile data
  - `profile_meta` - Key-value store for singleton fields (name, email, etc.)
  - `job_history` - Work experience
  - `education` - Degrees and institutions
  - `certifications` - Professional certifications
  - `honors` - Awards and recognition
  - `skills` - Skills with taxonomy categories (writing, api_dev_tools, ai_ml, content_strategy, taxonomy_ia, tools, languages)

**Database modules**:
- `db/connection.py` - Thread-safe connection management, WAL mode, Row factory
- `db/schema.py` - DDL statements (idempotent - all use IF NOT EXISTS)
- `db/models.py` - Dataclasses for all entities with `from_row()` methods
- `db/jobs.py` - CRUD operations: `upsert_job()`, `get_job()`, `list_jobs()`, `update_status()`, `update_score()`, `delete_job()`
- `db/profile.py` - Profile CRUD operations (mostly stubs for future expansion)

**Database initialization**:
```python
from db.connection import init_db
conn = init_db()  # Creates all tables if they don't exist
```

**Testing**:
```bash
python -m db.smoke_test  # Comprehensive smoke test using temp database
```

### 2. **Job Aggregation Scripts**

#### `rss_job_feed.py`
Fetches jobs from RSS feeds and saves to CSV.

**Configuration**:
- `FEED_URL` - List of RSS feed URLs (currently 4 RSS.app feeds)
- Configured for technical writing, taxonomy, and information architecture roles

**Key functions**:
- `fetch_and_parse_jobs(feed_url, hours_back=None)` - Returns pandas DataFrame
- `save_jobs_table(df, output_dir="jobs", filename=None)` - Saves to CSV
- Deduplicates by (title, URL) and sorts by posted date (newest first)

**Usage**:
```bash
python rss_job_feed.py  # Fetches all jobs, saves to jobs/rss_jobs_YYYY-MM-DD.csv
```

#### `startup_search.py`
Uses OpenAI web search to find jobs on specific domains.

**Configuration**:
- `ALLOWED_DOMAINS` = ["builtin.com", "wellfound.com"]
- `ROLE_TITLES` = ["technical writer", "taxonomy", "information architecture"]
- `JSON_INSTRUCTIONS` - Structured output format for LLM

**Key functions**:
- `search_since(since_date)` - One-off historical search
- `search_daily()` - Last 24 hours only
- `run_search(query)` - Executes web search via OpenAI API
- `parse_json_response(raw)` - Extracts JSON from LLM response
- `save_jobs_csv(jobs, filename)` - Saves to CSV matching RSS column structure

**Output format**: CSV with columns matching `rss_job_feed.py` format:
- Job Title, URL, Description, Posted Date, Source, Feed

**Usage**:
```bash
python startup_search.py  # Runs search_since("January 1, 2026")
```

**API requirement**: Requires `OPENAI_API_KEY` environment variable set.

### 3. **Data Processing Scripts**

#### `filter_jobs_by_location.py`
Filters database to keep only Seattle metro area and truly remote jobs.

**Location logic**:
- **Keep**: Seattle, Bellevue, Redmond, Kirkland, Bothell (exact city matches)
- **Keep**: Jobs listed as "United States" (may be remote, flagged for review)
- **Keep**: Jobs with strong remote indicators in description (regex patterns)
- **Remove**: All other locations

**Remote detection**:
- Positive patterns: "fully remote", "location: remote", "100% remote", etc.
- Negative patterns: "not remote", "not offer remote", etc.

**Usage**:
```bash
python filter_jobs_by_location.py  # Deletes non-matching jobs from database
```

**Warning**: This script DELETES rows from the database. Review the output before confirming.

#### `profile_import.py`
Imports profile data from LinkedIn markdown into the database.

**Purpose**: One-time import of your resume/profile data into the profile tables (job_history, education, skills, profile_meta).

**Usage**:
```bash
python profile_import.py  # Imports resumes/LinkedIn_Profile.md
python profile_import.py --profile path/to/profile.md  # Custom path
```

**What it imports**:
- Profile metadata (name, title, location, email, LinkedIn, GitHub, summary)
- Job history (company, title, dates, location, description)
- Education (institution, degree, field)
- Skills (from Top Skills and Languages sections)

**Note**: Run once to populate your profile. Re-running will duplicate entries unless you clear tables first.

#### `job_analyzer.py`
**LLM-powered job analyzer** - uses GPT-4o to filter jobs and extract structured data.

**Purpose**: Automatically filters jobs by location eligibility and extracts pay range information from descriptions.

**Location logic**:
- **Keep**: Seattle metro area (within 20 miles of zip code 98117)
- **Keep**: Truly remote positions (verified by reading full description)
- **Delete**: Jobs that clearly don't meet criteria
- **Uncertain**: When unclear, defaults to keeping the job
- Reads entire posting to catch contradictions (e.g., "remote" in title but "onsite required" in description)

**Seattle metro cities**: Seattle, Bellevue, Redmond, Kirkland, Bothell, Renton, Kent, Federal Way, Sammamish, Issaquah

**Features**:
- Extracts pay range from descriptions when provided
- Cleans up title formatting issues (e.g., missing spaces after job numbers)
- Provides decision reasoning for each job (KEEP, DELETE, or UNCERTAIN)
- Stores pay range by appending to description: `[Pay Range: ...]`
- Batch processing with progress reporting and summary statistics

**Usage**:
```bash
python job_analyzer.py                  # Analyze all 'new' jobs
python job_analyzer.py --job-id 123     # Analyze specific job
python job_analyzer.py --dry-run        # Test without modifying database
```

**Output**:
- Deletes jobs that clearly don't meet location criteria
- Updates job titles if formatting issues detected
- Appends pay range to descriptions when found
- Prints summary: jobs analyzed, kept, deleted, uncertain

**API requirement**: Requires `OPENAI_API_KEY` environment variable (uses GPT-4o model).

**Integration**: Automatically runs after job fetch in `run_pipeline.py` (can be skipped with `--skip-analyzer`).

#### `run_pipeline.py`
**Unified job search pipeline** - orchestrates fetching from all sources and stores directly to database.

**Features**:
- Fetches from RSS feeds and web search in a single run
- Stores directly to database (no intermediate CSV files)
- Automatic deduplication via URL (database handles this with upserts)
- Runs job analyzer automatically after fetch (LLM-powered filtering and data extraction)
- Command-line options for selective execution
- Progress reporting and summary statistics

**Usage**:
```bash
python run_pipeline.py                  # Full run (RSS + web search + analyzer)
python run_pipeline.py --rss-only       # RSS feeds only (no API key needed)
python run_pipeline.py --search-only    # Web search only (requires OPENAI_API_KEY)
python run_pipeline.py --skip-analyzer  # Skip LLM analyzer step
```

**Output**:
- Stores jobs directly to `job_search.db`
- Runs analyzer to filter by location and extract pay ranges
- Reports jobs fetched, jobs upserted, analyzer results, and database summary
- Execution time and statistics

**Note**: This is the recommended way to fetch jobs instead of running individual scripts.

**Automated scheduling**: See `SCHEDULER.md` for launchd configuration to run the pipeline daily.

### 4. **Data Files**

#### `jobs/` directory
- CSV files with job listings (various sources and dates)
- `manual_job_additions.csv` - Manually curated jobs
- `rss_jobs_*.csv` - RSS feed outputs (dated)
- `2026-02-16.json` - JSON format job data (alternate format)

**Standard CSV structure**:
```
Job Title, URL, Description, Posted Date, Source, Feed
```

#### `resumes/` directory
- `LinkedIn_Profile.md` - Markdown resume/profile
- `LinkedIn_Profile.pdf` - PDF version
- `LinkedIn_Profile.docx` - Word version

**Profile summary** (from LinkedIn_Profile.md):
- Senior Technical Writer specializing in complex infrastructure, security, cryptography
- Background: AWS (cryptographic/identity infrastructure), Chef (infrastructure automation), Tecton (ML feature store)
- Skills: Information architecture, taxonomy design, content governance, docs-as-code
- Domain expertise: Security documentation, cryptography, regulated systems, knowledge management

---

## Beads Integration

**Beads** is a CLI-based issue tracking system integrated with this repository.

### Configuration

`.beads/config.yaml`:
- Issue prefix: `kimberlygarmoe`
- No-DB mode: Uses JSONL only (no SQLite for issues)
- Data: `.beads/issues.jsonl`, `.beads/interactions.jsonl`

### Beadspace (GitHub Pages Dashboard)

**CI/CD**: `.github/workflows/beadspace.yml`
- Triggers on changes to `.beads/**` or `.beadspace/**`
- Converts `.beads/issues.jsonl` → `.beadspace/issues.json`
- Deploys to GitHub Pages

**Branch**: `beadspace` (current branch) - used for beadspace deployments

---

## Python Environment

**Version**: Python 3.10+  
**Virtual environment**: `.venv/` (present, should be activated)

### Key Dependencies

From installed packages:
- `pandas` (2.3.3) - Data manipulation for job listings
- `feedparser` (6.0.12) - RSS feed parsing
- `openai` (2.15.0) - Web search and LLM interactions
- `openai-agents` (0.7.0) - Agent framework
- `numpy` (2.2.6) - Pandas dependency
- `httpx` (0.28.1) - HTTP client
- `mcp` (1.25.0) - Model Context Protocol
- Standard library: `sqlite3`, `csv`, `json`, `pathlib`, `datetime`

**No requirements.txt found** - dependencies are installed but not formally tracked. If recreating environment, key packages are:
```bash
pip install pandas feedparser openai openai-agents
```

### Environment Variables

- `OPENAI_API_KEY` - Required for `startup_search.py` web searches

---

## Common Workflows

### 1. **Run the unified pipeline (RECOMMENDED)**
```bash
python run_pipeline.py
# Fetches from RSS + web search + runs analyzer
# Stores directly to database, filters by location, extracts pay ranges
# Output: Updates job_search.db with new jobs
```

Options:
```bash
python run_pipeline.py --rss-only       # RSS feeds only (faster, no API key)
python run_pipeline.py --search-only    # Web search only (requires OPENAI_API_KEY)
python run_pipeline.py --skip-analyzer  # Skip LLM analyzer (faster, keeps all jobs)
```

### 2. **Analyze jobs with LLM (location filtering + pay extraction)**
```bash
python job_analyzer.py
# Analyzes all 'new' jobs: filters by location, extracts pay ranges
# Uses GPT-4o to read entire posting and make intelligent decisions
```

Options:
```bash
python job_analyzer.py --job-id 123  # Analyze specific job
python job_analyzer.py --dry-run     # Test without modifying database
```

**Note**: The analyzer runs automatically in `run_pipeline.py` unless you use `--skip-analyzer`.

### 3. **Import profile data (one-time setup)**
```bash
python profile_import.py
# Imports resumes/LinkedIn_Profile.md into database
```

### 4. **Filter by location (legacy, rule-based)**
```bash
python filter_jobs_by_location.py
# Removes non-Seattle/non-remote jobs from database
# Note: job_analyzer.py is recommended instead (LLM-powered, more accurate)
```

### 5. **Query database programmatically**
```python
from db.connection import get_db
from db.jobs import list_jobs

# List all new jobs
new_jobs = list_jobs(status="new", order_by="posted_date DESC", limit=10)

# List high-scoring jobs
good_jobs = list_jobs(min_score=7.0, order_by="score DESC")

# Get specific job
from db.jobs import get_job
job = get_job(123)
```

### 6. **Run database smoke tests**
```bash
python -m db.smoke_test
# Tests all database operations with temp database
```

### Archived scripts

**Note**: The following scripts have been moved to `archive/` as they are no longer needed with the unified pipeline:

- `clean_rss_files.py` - Cleaned CSV files (pipeline now stores directly to DB)
- `migrate_csvs.py` - One-time CSV migration (already complete)

See `archive/README.md` for details and historical usage.

---

## Code Conventions

### Python Style
- Modern Python 3.10+ syntax
- Type hints used consistently: `str | None`, `list[dict]`, etc.
- Dataclasses for models (`from dataclasses import dataclass`)
- `from __future__ import annotations` for forward references
- Pathlib preferred over os.path
- f-strings for formatting

### Database Patterns
- **Thread-safe connections**: Use `get_db()` for cached connections
- **Optional db parameter**: All CRUD functions accept `db: sqlite3.Connection | None = None`
- **Row factory**: Connections use `sqlite3.Row` (dict-like access)
- **Idempotent DDL**: All schema statements use `IF NOT EXISTS`
- **Upsert pattern**: `ON CONFLICT(url) DO UPDATE` preserves user data
- **Validation**: CHECK constraints for enums and ranges

### CSV Handling
- Pandas for complex operations (RSS feeds)
- Standard library `csv` module for simple operations (migration, search output)
- Consistent column names: "Job Title", "URL", "Description", "Posted Date", "Source", "Feed"

### File Organization
- Scripts at repo root (single-purpose, runnable)
- `db/` package for all database code
- `jobs/` for data files (CSVs, JSON) - legacy artifacts
- `resumes/` for profile/resume documents
- `logs/` for pipeline execution logs
- `archive/` for deprecated scripts (reference only)
- `.beads/` for issue tracking data (gitignored)
- `.beadspace/` for dashboard artifacts
- `com.kimberlygarmoe.job_search.plist` - launchd configuration for daily runs

---

## Important Constraints & Gotchas

### Database
1. **URL uniqueness**: `jobs.url` is the unique key - upserts on this field
2. **Status enum**: Must be one of: `new`, `reviewed`, `applied`, `rejected`, `offer`
3. **Score range**: Must be NULL or 0-10 (enforced by CHECK constraint)
4. **Updated_at trigger**: Automatically updates on any row change
5. **WAL mode**: Database uses Write-Ahead Logging for better concurrency

### Job Sources
1. **RSS feeds**: May have duplicate entries across feeds - deduplicate before saving
2. **Dates**: RSS entries use `published_parsed` or `updated_parsed`, may be missing
3. **Web search JSON**: LLM responses may include markdown fences - `parse_json_response()` strips them
4. **CSV files**: Legacy workflow - pipeline now stores directly to database

### Location Filtering
1. **Destructive operation**: `filter_jobs_by_location.py` DELETES rows - no undo
2. **Remote detection**: Regex-based, not perfect - review "United States" jobs manually
3. **City matching**: Exact string matching in title (e.g., "in Seattle, WA")

### File Formats
1. **CSV encoding**: Use UTF-8 encoding for all CSV operations
2. **Column consistency**: All job CSVs must have the same 6 columns in order
3. **JSON structure**: Web search output expects specific field names (title, url, description, etc.)

---

## Testing

**Smoke test**: `python -m db.smoke_test`
- Tests all database operations (CRUD, upserts, filters, constraints)
- Uses temporary database (no pollution of project data)
- Comprehensive assertions for all operations
- ~150 lines, covers all major functionality

**No automated tests for scripts** - manual testing required for:
- RSS feed fetching
- Web searches
- Pipeline integration
- Location filtering

---

## Git Workflow

**Main branch**: `main` (default branch for production code)  
**CI/CD**: GitHub Actions workflow for Beadspace deployment (`.github/workflows/beadspace.yml`)

### Commit Message Format

This project uses **Conventional Commits** for clear, structured commit history.

**Format**: `<type>(<scope>): <description>`

**Types**:
- `feat` - New feature
- `fix` - Bug fix
- `docs` - Documentation only
- `style` - Code style (formatting, semicolons, etc.)
- `refactor` - Code change that neither fixes a bug nor adds a feature
- `perf` - Performance improvement
- `test` - Adding or updating tests
- `chore` - Maintenance (dependencies, build, etc.)
- `ci` - CI/CD changes

**Scope** (optional): Component affected (pipeline, db, scheduler, docs, etc.)

**Examples**:
```
feat(pipeline): add support for LinkedIn RSS feeds
fix(db): correct upsert behavior for duplicate URLs
docs(readme): add installation instructions
refactor(pipeline): extract common fetching logic
chore(deps): update pandas to 2.3.4
```

**Breaking changes**: Add `!` after type/scope and `BREAKING CHANGE:` in footer:
```
feat(db)!: change job status enum values

BREAKING CHANGE: status field now uses lowercase values (new, applied, rejected)
```

**Template**:
```
<type>(<scope>): <short summary>

<optional body: explain what and why, not how>

<optional footer: breaking changes, issue references>


💘 Generated with Crush



Assisted-by: Claude Sonnet 4.5 via Crush <crush@charm.land>
```

---

## Extending the System

### Adding a new job source
1. Create a function that returns job data in standardized format
2. Follow the pattern in `rss_job_feed.py` or `startup_search.py`
3. Import the function in `run_pipeline.py` and call from pipeline
4. Or create a standalone script that uses `db.jobs.upsert_job()` directly

### Adding a new status/enum
1. Update CHECK constraint in `db/schema.py`
2. Update any validation logic in `db/jobs.py`
3. Consider backward compatibility (existing rows)

### Adding profile fields
1. Add field to appropriate table in `db/schema.py`
2. Update dataclass in `db/models.py`
3. Add CRUD operations to `db/profile.py`
4. Update `db/smoke_test.py` to test new operations
5. Update `profile_import.py` parser if importing from markdown

### Scoring/ranking jobs
Job scoring is supported but not yet automated:
- Use `update_score(job_id, score, rationale)` to score jobs
- Score range: 0-10 (enforced by database)
- `score_rationale` field for explanation
- Query with `list_jobs(min_score=7.0, order_by="score DESC")`

---

## External Resources

- **Beads**: CLI issue tracker - see `.beads/README.md` for documentation
- **RSS.app**: RSS feed aggregation service (4 feeds configured)
- **OpenAI API**: Web search capability (requires API key)
- **GitHub Pages**: Beadspace dashboard hosting

---

## Future Considerations

Based on codebase structure and comments:

1. **Profile backend** (Epic 3 mentioned in `db/profile.py`) - populate profile tables from resume
2. **Resume generation** - Fields exist for job-specific resumes (`resume_md`, `resume_pdf_path`)
3. **Cover letter generation** - Fields exist (`cover_letter_md`, `cover_letter_pdf_path`)
4. **Automated scoring** - Score field exists but no scoring logic implemented
5. **Web interface** - Beadspace provides issue tracking UI, could expand for job management
6. **Automated job status tracking** - Status field exists, could track application progress

---

## Quick Reference Commands

```bash
# Run unified pipeline (RECOMMENDED)
python run_pipeline.py                  # Full run (RSS + web search + analyzer)
python run_pipeline.py --rss-only       # RSS only
python run_pipeline.py --search-only    # Web search only
python run_pipeline.py --skip-analyzer  # Skip LLM analyzer

# Analyze jobs (LLM-powered location filtering + pay extraction)
python job_analyzer.py                  # Analyze all 'new' jobs
python job_analyzer.py --job-id 123     # Analyze specific job
python job_analyzer.py --dry-run        # Test without DB changes

# Filter by location (legacy rule-based)
python filter_jobs_by_location.py

# Test database
python -m db.smoke_test

# Activate virtual environment
source .venv/bin/activate  # macOS/Linux
.venv\Scripts\activate     # Windows

# Check database
sqlite3 job_search.db "SELECT COUNT(*) FROM jobs;"
sqlite3 job_search.db "SELECT status, COUNT(*) FROM jobs GROUP BY status;"

# Daily scheduler (launchd)
# See SCHEDULER.md for full setup instructions
cp com.kimberlygarmoe.job_search.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.kimberlygarmoe.job_search.plist
launchctl list | grep job_search          # Verify loaded
launchctl start com.kimberlygarmoe.job_search  # Manual trigger
tail -f logs/pipeline.log                 # Watch logs

# Beads commands (if installed)
bd ls                    # List issues
bd show ISSUE-ID        # Show issue details
bd sync                 # Sync issues to git
```

---

**Last Updated**: 2026-02-18  
**Database Location**: `job_search.db` (446 KB, last modified 2026-02-17)  
**Python Version**: 3.10  
**Platform**: macOS (darwin)

<!-- bv-agent-instructions-v1 -->

---

## Beads Workflow Integration

This project uses [beads_viewer](https://github.com/Dicklesworthstone/beads_viewer) for issue tracking. Issues are stored in `.beads/` and tracked in git.

### Essential Commands

```bash
# View issues (launches TUI - avoid in automated sessions)
bv

# CLI commands for agents (use these instead)
bd ready              # Show issues ready to work (no blockers)
bd list --status=open # All open issues
bd show <id>          # Full issue details with dependencies
bd create --title="..." --type=task --priority=2
bd update <id> --status=in_progress
bd close <id> --reason="Completed"
bd close <id1> <id2>  # Close multiple issues at once
bd sync               # Commit and push changes
```

### Workflow Pattern

1. **Start**: Run `bd ready` to find actionable work
2. **Claim**: Use `bd update <id> --status=in_progress`
3. **Work**: Implement the task
4. **Complete**: Use `bd close <id>`
5. **Sync**: Always run `bd sync` at session end

### Key Concepts

- **Dependencies**: Issues can block other issues. `bd ready` shows only unblocked work.
- **Priority**: P0=critical, P1=high, P2=medium, P3=low, P4=backlog (use numbers, not words)
- **Types**: task, bug, feature, epic, question, docs
- **Blocking**: `bd dep add <issue> <depends-on>` to add dependencies

### Session Protocol

**Before ending any session, run this checklist:**

```bash
git status              # Check what changed
git add <files>         # Stage code changes
bd sync                 # Commit beads changes
git commit -m "..."     # Commit code
bd sync                 # Commit any new beads changes
git push                # Push to remote
```

### Best Practices

- Check `bd ready` at session start to find available work
- Update status as you work (in_progress → closed)
- Create new issues with `bd create` when you discover tasks
- Use descriptive titles and set appropriate priority/type
- Always `bd sync` before ending session

<!-- end-bv-agent-instructions -->
