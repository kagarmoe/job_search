# ATS Search & Manual URL Ingest

**Date:** 2026-04-15
**Issue:** kimberlygarmoe-10

## Problem

Jobs arrive via LinkedIn RSS feeds, but the actual application pages live on ATS platforms (Greenhouse, Ashby). Users must manually find the direct posting to apply. OpenAI's web search with `allowed_domains` reliably returns structured JSON from both `greenhouse.io` and `ashbyhq.com`.

## Design

### 1. ATS Search Source (`pipeline/ats_search.py`)

New pipeline module that searches ATS platforms for technical writer postings.

**Platforms:**
- `greenhouse.io` — `"technical writer"` postings
- `ashbyhq.com` — `"technical writer"` postings

**Behavior:**
- Uses OpenAI web search with `allowed_domains` filter per platform
- Tracks per-feed `last_fetch` timestamps (one per domain) to scope queries to "posted since {date}"
- Filters results to only keep URLs containing the target domain (guards against LLM returning off-domain results)
- Upserts each result with `source` from domain name, `feed` as `"Greenhouse Search"` / `"Ashby Search"`
- Called from `run_pipeline()` alongside RSS and existing web search
- Skipped with `--rss-only`; can be run alone with `--ats-only`

**Search flow:**
1. Load `last_fetch` for each ATS feed
2. For each platform, call OpenAI web search with `allowed_domains` and date constraint
3. Parse JSON response (reuse `parse_json_response()` from `pipeline/search.py`)
4. Filter: discard any result whose URL doesn't contain the expected domain
5. Upsert each job to database
6. Update `last_fetch` per feed (only for successfully upserted jobs, per P1 fix pattern)

### 2. Manual URL Ingest (`pipeline/ingest.py`)

New module that fetches a job posting page and extracts basic data.

**Behavior:**
- Takes a URL, fetches page via `httpx`
- Extracts title from `<title>` tag, description from page body
- Derives source from URL domain (e.g. `greenhouse.io` → `"Greenhouse"`, `ashbyhq.com` → `"Ashby"`)
- Upserts as a job; the existing analyzer handles location/type/pay extraction

**Entry points:**
- **CLI:** `python run_pipeline.py --ingest-url <url>`
- **Web UI:** `POST /ingest` route with a URL form field

### 3. CLI Flag Changes

New flags for `run_pipeline.py`:
- `--ats-only` — only run ATS platform search (skip RSS and existing web search)
- `--ingest-url <url>` — ingest a single URL and exit (no other pipeline steps)

### 4. Schema Changes

None. Existing columns (`url`, `source_id`, `feed_id`, `title`, `description`) handle everything.

## Key Decisions

- **OpenAI web search over scraping** — `allowed_domains` filter works reliably for both Greenhouse and Ashby, returns structured JSON, and avoids fragile HTML parsing for search results.
- **Domain filtering on results** — LLMs occasionally return off-domain URLs; we discard any result whose URL doesn't match the target domain.
- **Per-platform last_fetch** — Each ATS domain gets its own feed timestamp, same incremental pattern as RSS feeds.
- **Manual ingest is simple page fetch** — No platform-specific parsing; the LLM analyzer extracts structured data from the raw content.
- **Reuse parse_json_response()** — Same JSON extraction logic as existing web search, avoiding duplication.
