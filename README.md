# Job Search

An automated job search system that pulls listings from RSS feeds and web searches, stores them in a local database, and serves a web interface for reviewing and tracking applications.

## What This Project Does

1. **Fetches jobs** from RSS feeds (and optionally web search via OpenAI)
2. **Analyzes jobs** with an LLM to filter by location, extract pay, and clean titles
3. **Stores everything** in a local SQLite database
4. **Serves a web app** where you can browse, filter, review, and track jobs

## Prerequisites

- **Python 3.10 or newer** — check with `python3 --version`
- **Git** — check with `git --version`
- **macOS or Linux** (Windows works but paths differ)
- **Optional:** an OpenAI API key, for web search and LLM analysis features

## Setup

### 1. Clone the repository

Open a terminal and run:

```bash
git clone https://github.com/kagarmoe/job_search.git
cd job_search
```

### 2. Create a virtual environment

A virtual environment keeps this project's packages separate from your system Python.

```bash
python3 -m venv .venv
```

### 3. Activate the virtual environment

```bash
source .venv/bin/activate
```

Your terminal prompt should now show `(.venv)`. You need to run this command each time you open a new terminal to work on this project.

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Initialize the database

The database creates itself the first time you run the app or pipeline. No manual setup needed.

### 6. (Optional) Set your OpenAI API key

Only needed for web search and LLM job analysis:

```bash
export OPENAI_API_KEY="your-key-here"
```

## Running the App

### Web interface

```bash
python app.py
```

Then open http://localhost:5000 in your browser. The web interface lets you:

- Browse and filter job listings by status, source, or score
- View full job details and descriptions
- Mark jobs as interested, passed, or applied
- Walk through a review queue of unreviewed jobs
- View your imported profile

### Fetch new jobs

```bash
# Full pipeline: RSS + web search + LLM analyzer
python run_pipeline.py

# RSS feeds only, no API key needed
python run_pipeline.py --rss-only --skip-analyzer

# RSS feeds with LLM analysis (needs OPENAI_API_KEY)
python run_pipeline.py --rss-only

# Web search only
python run_pipeline.py --search-only
```

The LLM analyzer filters each new job by location (Seattle metro or fully remote), extracts pay range, identifies job type, and cleans up title formatting.

### Import your profile

```bash
python profile_import.py
```

Parses `resumes/LinkedIn_Profile.md` and loads your work history, education, and skills into the database. Run once after setup.

### Schedule daily fetches (macOS)

```bash
cp com.kimberlygarmoe.job_search.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.kimberlygarmoe.job_search.plist
```

Runs `run_pipeline.py --rss-only` daily at 8:00 AM. See [SCHEDULER.md](SCHEDULER.md) for configuration and troubleshooting.

## Project Structure

```
app.py                  Flask web application
run_pipeline.py         CLI entry point for fetching and analyzing jobs
profile_import.py       Import LinkedIn profile into database

pipeline/               Job processing modules
  constants.py          Shared constants (Seattle metro cities, etc.)
  rss.py                RSS feed fetcher
  search.py             Web search via OpenAI
  analyzer.py           LLM-powered job analysis (location, pay, type)
  dedup.py              Duplicate detection and removal
  location.py           Regex-based location classification

db/                     Database layer
  schema.py             Table definitions
  models.py             Dataclasses (Job, Feed, Source, etc.)
  connection.py         Connection management (thread-safe, WAL mode)
  jobs.py               Job CRUD operations
  feeds.py              Feed and source CRUD operations
  profile.py            Profile data operations
  smoke_test.py         Database integration tests
  migrate_*.py          Schema migration scripts

templates/              HTML templates (Jinja2)
static/css/             Stylesheets
resumes/                Resume and profile documents
logs/                   Pipeline execution logs (gitignored)
archive/                Deprecated scripts (reference only)
docs/plans/             Design documents
```

## Configuration

### RSS feeds

Edit `FEED_URL` in `pipeline/rss.py` to add or remove feeds.

### Web search

Edit `pipeline/search.py` to customize:
- `ALLOWED_DOMAINS` — job boards to search (default: builtin.com, wellfound.com)
- `ROLE_TITLES` — target role keywords

### Location and analysis

Edit the `ANALYSIS_PROMPT` in `pipeline/analyzer.py` to change location criteria, job type categories, or extraction rules. The shared city list lives in `pipeline/constants.py`.

## Testing

```bash
python test_project.py
```

Runs 6 test suites: file existence, app imports, RSS filtering, location classification, constant consistency, and pipeline integration.

```bash
python -m db.smoke_test
```

Runs database integration tests (schema creation, CRUD operations).

## Database

Jobs are stored in `job_search.db` (SQLite, gitignored). Key fields:

| Field | Description |
|---|---|
| `title`, `url` | Job title and posting URL (unique) |
| `description` | Full posting text |
| `status` | `new`, `interested`, `passed`, `applied`, `rejected`, `offer` |
| `score` | 0–10 relevance score |
| `location_label` | `Seattle`, `Remote`, or `Review for location` |
| `job_type` | `Full-time`, `Contract`, `Part-time`, or `Not specified` |
| `pay_range` | Extracted salary (e.g., `$120K-$150K/year`) |

See `db/schema.py` for the full schema.

### Quick queries

```bash
# Count jobs by status
sqlite3 job_search.db "SELECT status, COUNT(*) FROM jobs GROUP BY status;"

# Recent jobs
sqlite3 job_search.db "SELECT title, posted_date FROM jobs ORDER BY posted_date DESC LIMIT 10;"
```

---

## Contributing to This Project

This section covers everything you need to contribute: Git workflow, coding patterns, issue tracking with Beads, and working with AI coding agents.

### Git basics

Git tracks changes to files over time. Here are the commands you need:

```bash
# Check what files you changed
git status

# See the actual changes
git diff

# Stage files for commit (tells Git "include these changes")
git add file1.py file2.py

# Save your staged changes with a message
git commit -m "fix: correct location filter for Kent, WA"

# Push your branch to GitHub
git push
```

**Key rule: never push directly to `main`.** Always create a branch and open a pull request (PR).

### Branch workflow

Every change — no matter how small — goes through a branch and PR:

```bash
# Start from main with the latest code
git checkout main
git pull

# Create a branch for your work
git checkout -b feat/add-salary-filter

# ... make your changes, commit them ...

# Push your branch to GitHub
git push -u job_search feat/add-salary-filter
```

Then open a pull request on GitHub. The branch name should describe what you're doing:
- `feat/add-salary-filter` — new feature
- `fix/duplicate-job-entries` — bug fix
- `chore/update-dependencies` — maintenance
- `refactor/simplify-rss-parser` — code improvement

### Commit messages

Start each message with a type prefix:

```
feat: add salary range filter to job list page
fix: prevent duplicate RSS entries on re-fetch
refactor: extract shared constants to pipeline/constants.py
chore: update feedparser to 6.1.0
docs: add setup instructions for Windows
```

Keep messages short (under 72 characters) and describe *why*, not *what*. The diff shows what changed; the message explains the reason.

### Issue tracking with Beads

This project uses [Beads](https://github.com/beadsdotdev/beads) instead of GitHub Issues. Beads stores issues in a local Dolt database that syncs with the repo, so issue tracking works offline and alongside your code.

#### Finding work

```bash
# Show issues ready to work on (no blockers)
bd ready

# List all open issues
bd list --status=open

# View details of a specific issue
bd show <issue-id>
```

#### Working on an issue

```bash
# Claim the issue
bd update <issue-id> --status=in_progress

# ... do the work, commit code ...

# Close when done
bd close <issue-id> --reason="Added salary filter with tests"
```

#### Creating issues

```bash
bd create --title="Add salary range filter" \
  --description="Users should be able to filter the job list by minimum salary" \
  --type=feature \
  --priority=2
```

Priority runs 0–4: 0 is critical, 2 is medium, 4 is backlog.

Types: `feature`, `bug`, `task`, `chore`.

#### Dependencies

If one issue blocks another:

```bash
# "Write tests" depends on "Implement feature"
bd dep add <test-issue-id> <feature-issue-id>

# See what's blocked
bd blocked
```

#### Beadspace dashboard

View all issues visually at: https://kagarmoe.github.io/job_search/

### Working with AI coding agents

This project is built with [Claude Code](https://claude.com/claude-code), an AI coding agent. The `AGENTS.md` file at the repo root contains detailed instructions that Claude reads automatically when working in this codebase.

#### What agents do well

- Implement features from a description or design doc
- Write tests, fix bugs, refactor code
- Track work with Beads (`bd create`, `bd close`)
- Create branches, commit, push, and open PRs
- Run the test suite and fix failures

#### How to use an agent on this project

1. Open Claude Code in the project directory
2. Describe what you want: "Add a filter for minimum salary on the job list page"
3. The agent reads `AGENTS.md` for project conventions, creates a Beads issue, writes code, runs tests, and opens a PR
4. Review the PR on GitHub before merging

#### What to watch for

- **Always review agent PRs.** Agents write working code, but you decide whether the approach is right.
- **Check test coverage.** If the agent skips tests, ask it to add them.
- **The agent follows `AGENTS.md`.** If you want to change a convention (naming, structure, workflow), update that file.

### Code patterns

A few conventions to follow when contributing:

**Database access** — use the `db/` layer, never raw `sqlite3.connect()`:

```python
from db.connection import get_db
from db.jobs import list_jobs, update_status

jobs = list_jobs(status="new", limit=10)
update_status(job_id=42, status="applied")
```

**Shared constants** — location data lives in `pipeline/constants.py`:

```python
from pipeline.constants import SEATTLE_METRO
```

**Testing** — add tests in `test_project.py`. Run with `python test_project.py`.

**Dependencies** — after adding a package, update requirements:

```bash
pip install new-package
pip freeze > requirements.txt
```

### Getting help

- Open an issue with `bd create --title="..." --type=bug`
- Check existing issues with `bd list`
- Read `AGENTS.md` for detailed project conventions
- Read `docs/plans/` for design documents explaining past decisions
