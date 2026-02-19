# job_search

Making my job search fun with agents.

An automated job search system that aggregates listings from RSS feeds and web searches, stores them in SQLite, and helps track applications.

## Quick Start

### Prerequisites

- Python 3.10+
- Virtual environment (`.venv/`)
- Optional: OpenAI API key for web search

### Setup

```bash
# Clone and navigate to repository
cd job_search

# Activate virtual environment
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# Install dependencies (if needed)
pip install pandas feedparser openai openai-agents
```

## Running the Job Search

### Manual execution (ad-hoc)

**Fetch jobs from all sources:**
```bash
python run_pipeline.py
```
Fetches from RSS feeds + web search + runs LLM analyzer (requires `OPENAI_API_KEY` environment variable).

The analyzer automatically:
- Filters jobs by location (Seattle metro within 20 miles OR fully remote)
- Extracts pay range information from descriptions
- Cleans up title formatting issues

**RSS feeds only (no analyzer):**
```bash
python run_pipeline.py --rss-only --skip-analyzer
```
No API key needed, fetches from configured RSS feeds without LLM analysis.

**Skip analyzer (keep all jobs):**
```bash
python run_pipeline.py --skip-analyzer
```
Fetches jobs but skips intelligent filtering and pay extraction.

**Web search only:**
```bash
export OPENAI_API_KEY="your-key-here"
python run_pipeline.py --search-only
```
Searches builtin.com and wellfound.com for technical writing roles.

### Automated execution (scheduled)

**Set up daily scheduler (macOS):**
```bash
# Install launchd job
cp com.kimberlygarmoe.job_search.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.kimberlygarmoe.job_search.plist

# Verify it's running
launchctl list | grep job_search

# View logs
tail -f logs/pipeline.log
```

The scheduler runs daily at 8:00 AM with RSS-only mode. See [SCHEDULER.md](SCHEDULER.md) for full configuration options.

## Working with Jobs

### View jobs in database

```bash
# Count total jobs
sqlite3 job_search.db "SELECT COUNT(*) FROM jobs;"

# View recent jobs
sqlite3 job_search.db "SELECT title, source, posted_date FROM jobs ORDER BY posted_date DESC LIMIT 10;"

# View jobs by status
sqlite3 job_search.db "SELECT status, COUNT(*) FROM jobs GROUP BY status;"
```

### Analyze jobs with LLM

```bash
python job_analyzer.py
```
Analyzes all 'new' jobs using GPT-4o:
- Filters by location (Seattle metro OR fully remote)
- Extracts and displays pay range information
- Reads entire posting to catch contradictions
- Provides decision reasoning (KEEP, DELETE, or UNCERTAIN)

**Options:**
```bash
python job_analyzer.py --job-id 123  # Analyze specific job
python job_analyzer.py --dry-run     # Test without modifying database
```

**Note**: The analyzer runs automatically in `run_pipeline.py` unless you use `--skip-analyzer`.

### Filter jobs by location (legacy)

```bash
python filter_jobs_by_location.py
```
Rule-based location filter. **Recommendation**: Use `job_analyzer.py` instead for more accurate LLM-powered filtering.

### Import profile data

```bash
python profile_import.py
```
Parses `resumes/LinkedIn_Profile.md` and imports profile data into database (job history, education, skills). Run once to populate your profile.

### Programmatic access

```python
from db.connection import get_db
from db.jobs import list_jobs, update_status, update_score

# List new jobs
new_jobs = list_jobs(status="new", order_by="posted_date DESC", limit=10)

# Update job status
update_status(job_id=123, status="applied")

# Score a job
update_score(job_id=123, score=8.5, rationale="Great match for my skills")

# Filter by score
good_jobs = list_jobs(min_score=7.0, order_by="score DESC")
```

## Project Structure

- `run_pipeline.py` - Main entry point for job fetching (includes analyzer)
- `job_analyzer.py` - LLM-powered job filtering and pay extraction
- `rss_job_feed.py` - RSS feed parser
- `startup_search.py` - Web search integration
- `filter_jobs_by_location.py` - Legacy location filter utility
- `profile_import.py` - Import LinkedIn profile to database
- `db/` - Database layer (schema, models, CRUD operations)
- `jobs/` - Legacy CSV files
- `resumes/` - Resume/profile documents
- `logs/` - Pipeline execution logs
- `archive/` - Deprecated scripts (reference only)

## Configuration

### RSS Feeds

Edit `FEED_URL` in `rss_job_feed.py` to add/remove feeds.

### Web Search

Edit `startup_search.py` to customize:
- `ALLOWED_DOMAINS` - Job board domains to search
- `ROLE_TITLES` - Target role keywords

### Location Preferences

**Recommended**: Use `job_analyzer.py` for LLM-powered location filtering.

**Legacy option**: Edit `filter_jobs_by_location.py` to customize:
- `SEATTLE_METRO` - Cities to keep
- `REMOTE_POSITIVE` / `REMOTE_NEGATIVE` - Remote detection patterns

### Job Analyzer

The analyzer uses GPT-4o to intelligently filter jobs:
- **Location criteria**: Within 20 miles of Seattle (98117) OR fully remote
- **Pay extraction**: Finds and formats salary information from descriptions
- **Smart reading**: Reads entire posting to catch contradictions
- **Configurable**: Modify prompt in `job_analyzer.py` to adjust criteria

## Documentation

- **[AGENTS.md](AGENTS.md)** - Comprehensive guide for agents/developers
- **[SCHEDULER.md](SCHEDULER.md)** - Scheduler setup and management
- **[archive/README.md](archive/README.md)** - Archived scripts reference

## Database Schema

Jobs are stored in SQLite (`job_search.db`) with the following key fields:

- `title`, `url` (unique), `description`
- `posted_date`, `source`, `feed`
- `score` (0-10), `score_rationale`
- `status` (new|reviewed|applied|rejected|offer)
- `resume_md`, `cover_letter_md` (job-specific materials)
- `created_at`, `updated_at`

See [db/schema.py](db/schema.py) for full schema.

## Testing

```bash
# Run database smoke tests
python -m db.smoke_test

# Run project integrity tests
python test_project.py
```

## Issue Tracking

This project uses [Beads](https://github.com/beadsdotdev/beads) for issue tracking:

```bash
bd list              # List all issues
bd show ISSUE-ID     # Show issue details
bd new "Issue title" # Create new issue
```

View the [Beadspace dashboard](https://kagarmoe.github.io/job_search/) for a visual overview.

## License

Personal project - use at your own discretion.
