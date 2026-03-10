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

### Add a job by hand

If you find a job posting on a site like builtin.com or wellfound.com that isn't in your RSS feeds, you can add it directly using the Python interpreter.

**Step 1: Open the Python interpreter.** Make sure your virtual environment is active (you should see `(.venv)` in your prompt), then type `python` and press Enter:

```bash
(.venv) $ python
```

You'll see something like this:

```
Python 3.10.2 (main, ...) [...]
Type "help", "copyright", "credits" or "license" for more information.
>>>
```

The `>>>` is the Python prompt. It means Python is waiting for you to type a command.

**Step 2: Set up the database connection.** Type each line below, pressing Enter after each one. Python won't print anything — that's normal.

```python
>>> from db.connection import init_db
>>> from db.jobs import upsert_job
>>> init_db()
```

After `init_db()` you'll see a line like `<sqlite3.Connection object at 0x...>`. That's fine — it means the database is ready.

**Step 3: Add the job.** Copy the URL from your browser, then type:

```python
>>> upsert_job(
...     title="Acme Corp hiring Backend Engineer in Seattle, WA",
...     url="https://builtin.com/job/12345",
...     source="builtin.com",
... )
```

When you press Enter after the first line, the prompt changes from `>>>` to `...` — that means Python is waiting for you to finish the statement. Keep typing each line. After the closing `)`, press Enter and Python will save the job to your database.

**Step 4: Exit the interpreter.** Type `exit()` or press Ctrl+D:

```python
>>> exit()
```

The job will now appear in the web app at http://localhost:5000 with status "new."

**Tips:**
- The `url` must be unique. If you add the same URL twice, it updates the existing entry instead of creating a duplicate.
- The `title` and `source` are free text — type whatever helps you recognize the posting.
- You can also pass `description="..."` if you want to paste in the job description.

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

## Customizing for Your Own Job Search

This project is set up for technical writing roles in the Seattle area. To use it for your own search, you need to change four things: your location, your target roles, your RSS feeds, and your profile.

### 1. Change your location

**`pipeline/constants.py`** — Replace the city list with your metro area:

```python
SEATTLE_ZIP = "10001"  # Your zip code (used in analyzer prompt)

SEATTLE_METRO = [
    "New York", "Brooklyn", "Jersey City", "Hoboken",
    # ... your metro cities
]
```

**`pipeline/analyzer.py`** — Find the `ANALYSIS_PROMPT` string and update the location criteria. Search for "Seattle" and replace with your city. The prompt tells the LLM what counts as "local" vs. "remote" vs. "delete."

**`pipeline/location.py`** — The regex patterns (`REMOTE_POSITIVE`, `REMOTE_NEGATIVE`) are generic and should work for any location. The `_SEATTLE_RE` regex auto-builds from the `SEATTLE_METRO` list you changed above, so no edits needed here.

### 2. Change your target roles

**`pipeline/search.py`** — Update `ROLE_TITLES` with your job titles:

```python
ROLE_TITLES = [
    "software engineer", "backend developer", "full stack engineer"
]
```

Also update `ALLOWED_DOMAINS` if you want to search different job boards:

```python
ALLOWED_DOMAINS = ["builtin.com", "wellfound.com", "lever.co"]
```

### 3. Set up your own RSS feeds

**`pipeline/rss.py`** — Replace the `FEED_URL` list with your feeds. Most job boards let you create RSS feeds from saved searches. For example:

- **rss.app** — create feeds from any job board search URL
- **LinkedIn** — some saved searches offer RSS
- **Indeed/Glassdoor** — use rss.app to convert search URLs

```python
FEED_URL = [
    "https://rss.app/feeds/your-feed-1.xml",
    "https://rss.app/feeds/your-feed-2.xml",
]
```

### 4. Add your profile

Replace `resumes/LinkedIn_Profile.md` with your own resume in markdown format, then run:

```bash
python profile_import.py
```

The profile page at http://localhost:5000/profile will show your imported data.

### 5. Start fresh

Delete the existing database so you start with a clean slate:

```bash
rm job_search.db
python run_pipeline.py --rss-only --skip-analyzer
```

The database recreates itself on the next run.

## Testing

```bash
python test_project.py
```

Runs 8 test suites: file existence, app imports, RSS filtering, location classification, constant consistency, title normalization, RSS deduplication, and pipeline integration.

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

### Claude Code skills and plugins

This project uses several [Claude Code skills](https://docs.anthropic.com/en/docs/claude-code/skills) — reusable prompt packages that teach the agent specialized workflows. Skills are invoked automatically when relevant, or manually with slash commands.

#### Installed skills

| Skill | What it does |
|---|---|
| **superpowers** | Core development workflows: brainstorming designs, writing implementation plans, TDD, git worktrees, code review, and subagent-driven development |
| **pr-review-toolkit** | Runs multi-agent PR reviews — code quality, test coverage, error handling, comment accuracy, type design, and code simplification |
| **elements-of-style** | Applies Strunk's writing rules to documentation, commit messages, and prose |
| **episodic-memory** | Searches previous conversations so the agent remembers decisions across sessions |
| **hookify** | Creates git hooks from conversation patterns to prevent recurring mistakes |

#### How skills work

Skills activate automatically based on context. When you say "review this PR," the agent invokes `pr-review-toolkit:review-pr`, which dispatches specialized subagents in parallel. When you say "let's build a feature," `superpowers:brainstorming` runs first to explore the design before any code is written.

You can also invoke skills directly:

```
/pr-review-toolkit:review-pr          # Full PR review
/pr-review-toolkit:review-pr tests    # Test coverage only
/superpowers:brainstorming            # Design a new feature
/commit                               # Commit with conventional message
```

#### Beads plugin

The [Beads](https://github.com/beadsdotdev/beads) issue tracker is installed as a Claude Code plugin (not a skill). It provides `bd` commands for issue tracking and runs hooks that auto-load project context at the start of each session. See the "Issue tracking with Beads" section above.

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
