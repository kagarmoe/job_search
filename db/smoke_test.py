"""Smoke test for the database module.

Run: python -m db.smoke_test
"""

import sys
import tempfile
from pathlib import Path

from datetime import datetime

from db.connection import init_db, close_db
from db.feeds import (
    get_or_create_source,
    get_or_create_feed,
    get_last_fetch,
    get_all_last_fetches,
    set_last_fetch,
)
from db.jobs import (
    upsert_job,
    get_job,
    get_job_by_url,
    list_jobs,
    update_status,
    update_score,
    delete_job,
)
from db.profile import set_meta, get_meta, add_skill, list_skills


def main() -> None:
    # Use a temp file so we don't pollute the project
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    print(f"Using temp DB: {db_path}")

    try:
        conn = init_db(db_path)

        # Verify tables exist
        tables = [
            r["name"]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
        ]
        expected = {
            "certifications", "education", "feeds", "honors",
            "job_history", "jobs", "profile_meta", "skills", "sources",
        }
        assert expected.issubset(set(tables)), f"Missing tables: {expected - set(tables)}"
        print(f"[PASS] All {len(expected)} tables created: {sorted(expected)}")

        # ----------------------------------------------------------
        # Sources and Feeds
        # ----------------------------------------------------------
        src_id = get_or_create_source("LinkedIn", db=conn)
        assert src_id is not None
        src_id2 = get_or_create_source("LinkedIn", db=conn)
        assert src_id == src_id2, "get_or_create_source should return same id"
        print(f"[PASS] get_or_create_source() works (id={src_id})")

        feed_id = get_or_create_feed(
            "LinkedIn Jobs - Tech Writer",
            url="https://example.com/feed.xml",
            source_id=src_id,
            db=conn,
        )
        assert feed_id is not None
        feed_id2 = get_or_create_feed("LinkedIn Jobs - Tech Writer", db=conn)
        assert feed_id == feed_id2, "get_or_create_feed should return same id by name"
        feed_id3 = get_or_create_feed(
            "Other Name", url="https://example.com/feed.xml", db=conn
        )
        assert feed_id == feed_id3, "get_or_create_feed should return same id by url"
        print(f"[PASS] get_or_create_feed() works (id={feed_id})")

        # ----------------------------------------------------------
        # Insert a job (using string API)
        # ----------------------------------------------------------
        job = upsert_job(
            "Senior Technical Writer",
            "https://example.com/jobs/123",
            description="Write great docs.",
            posted_date="2026-02-17",
            source="LinkedIn",
            feed="Manual Addition",
            db=conn,
        )
        assert job.id is not None
        assert job.title == "Senior Technical Writer"
        assert job.status == "new"
        assert job.source == "LinkedIn"
        assert job.feed == "Manual Addition"
        assert job.source_id is not None
        assert job.feed_id is not None
        print(f"[PASS] Inserted job id={job.id} (source_id={job.source_id}, feed_id={job.feed_id})")

        # Fetch by ID — should have JOINed names
        fetched = get_job(job.id, db=conn)
        assert fetched is not None
        assert fetched.url == "https://example.com/jobs/123"
        assert fetched.source == "LinkedIn"
        assert fetched.feed == "Manual Addition"
        print(f"[PASS] get_job({job.id}) returned correct job with source/feed names")

        # Fetch by URL
        fetched_url = get_job_by_url("https://example.com/jobs/123", db=conn)
        assert fetched_url is not None
        assert fetched_url.id == job.id
        assert fetched_url.source == "LinkedIn"
        print(f"[PASS] get_job_by_url() returned correct job")

        # Upsert same URL — should update, not duplicate
        job2 = upsert_job(
            "Senior Technical Writer (Updated)",
            "https://example.com/jobs/123",
            description="Write amazing docs.",
            source="LinkedIn",
            db=conn,
        )
        assert job2.id == job.id, f"Expected same id, got {job2.id} vs {job.id}"
        assert job2.title == "Senior Technical Writer (Updated)"
        assert job2.description == "Write amazing docs."
        # Status should be preserved from original
        assert job2.status == "new"
        print(f"[PASS] Upsert dedup: same id, updated title/description, preserved status")

        # List jobs
        jobs = list_jobs(db=conn)
        assert len(jobs) == 1
        assert jobs[0].source == "LinkedIn"
        print(f"[PASS] list_jobs() returned {len(jobs)} job(s) with source names")

        # Update status
        updated = update_status(job.id, "reviewed", db=conn)
        assert updated is not None
        assert updated.status == "reviewed"
        assert updated.source == "LinkedIn"  # JOINed name preserved
        print(f"[PASS] update_status() -> reviewed")

        # Update score
        scored = update_score(job.id, 8.5, "Great match for skills", db=conn)
        assert scored is not None
        assert scored.score == 8.5
        assert scored.score_rationale == "Great match for skills"
        print(f"[PASS] update_score() -> 8.5")

        # List with filters
        jobs_new = list_jobs(status="new", db=conn)
        assert len(jobs_new) == 0  # we changed it to reviewed
        jobs_reviewed = list_jobs(status="reviewed", db=conn)
        assert len(jobs_reviewed) == 1
        jobs_scored = list_jobs(min_score=5.0, db=conn)
        assert len(jobs_scored) == 1
        # Filter by source name
        jobs_linkedin = list_jobs(source="LinkedIn", db=conn)
        assert len(jobs_linkedin) == 1
        jobs_other = list_jobs(source="Nonexistent", db=conn)
        assert len(jobs_other) == 0
        print(f"[PASS] list_jobs() filters work correctly (including source filter)")

        # Insert a second job and test ordering
        upsert_job("Content Strategist", "https://example.com/jobs/456", db=conn)
        all_jobs = list_jobs(order_by="title ASC", db=conn)
        assert all_jobs[0].title == "Content Strategist"
        assert all_jobs[1].title == "Senior Technical Writer (Updated)"
        print(f"[PASS] list_jobs() ordering works")

        # Delete
        assert delete_job(job.id, db=conn) is True
        assert get_job(job.id, db=conn) is None
        assert delete_job(999, db=conn) is False
        print(f"[PASS] delete_job() works")

        # Profile stubs
        set_meta("name", "Test User", db=conn)
        assert get_meta("name", db=conn) == "Test User"
        set_meta("name", "Updated User", db=conn)  # upsert
        assert get_meta("name", db=conn) == "Updated User"
        print(f"[PASS] profile_meta set/get/upsert")

        skill = add_skill("Python", "tools", proficiency="expert", db=conn)
        assert skill.name == "Python"
        skills = list_skills(category="tools", db=conn)
        assert len(skills) == 1
        print(f"[PASS] skills add/list")

        # Check constraint: invalid status should fail
        try:
            conn.execute(
                "INSERT INTO jobs (title, url, status) VALUES ('Test', 'https://test/bad-status', 'invalid')"
            )
            print("[FAIL] CHECK constraint did not fire for invalid status")
            sys.exit(1)
        except Exception:
            conn.execute("ROLLBACK")  # clean up failed transaction
            print(f"[PASS] CHECK constraint rejects invalid status")

        # Check constraint: score out of range should fail
        try:
            conn.execute(
                "INSERT INTO jobs (title, url, score) VALUES ('Test', 'https://test/bad-score', 11)"
            )
            print("[FAIL] CHECK constraint did not fire for score > 10")
            sys.exit(1)
        except Exception:
            conn.execute("ROLLBACK")
            print(f"[PASS] CHECK constraint rejects score > 10")

        # ----------------------------------------------------------
        # Feed fetch timestamps (operating on feeds table)
        # ----------------------------------------------------------

        # No last_fetch recorded yet for an unknown url
        assert get_last_fetch("https://example.com/unknown-feed.xml", db=conn) is None
        print("[PASS] get_last_fetch() returns None for unknown feed")

        # set_last_fetch on a feed that already has a url (created above)
        ts1 = datetime(2026, 2, 20, 12, 0, 0)
        set_last_fetch("https://example.com/feed.xml", ts1, db=conn)
        assert get_last_fetch("https://example.com/feed.xml", db=conn) == ts1
        print("[PASS] set_last_fetch() / get_last_fetch() round-trip")

        # Upsert overwrites with newer timestamp
        ts2 = datetime(2026, 2, 21, 8, 30, 0)
        set_last_fetch("https://example.com/feed.xml", ts2, db=conn)
        assert get_last_fetch("https://example.com/feed.xml", db=conn) == ts2
        print("[PASS] set_last_fetch() upsert updates timestamp")

        # set_last_fetch for a brand-new url (creates row)
        set_last_fetch("https://example.com/feed2.xml", ts1, db=conn)
        all_fetches = get_all_last_fetches(db=conn)
        assert "https://example.com/feed.xml" in all_fetches
        assert "https://example.com/feed2.xml" in all_fetches
        assert all_fetches["https://example.com/feed.xml"] == ts2
        assert all_fetches["https://example.com/feed2.xml"] == ts1
        print("[PASS] get_all_last_fetches() returns all feeds with timestamps")

        # ----------------------------------------------------------
        # Job with feed_url — ensures feed row gets url populated
        # ----------------------------------------------------------
        job_rss = upsert_job(
            "RSS Job",
            "https://example.com/jobs/rss-1",
            source="builtin.com",
            feed="Builtin Jobs Feed",
            feed_url="https://rss.example.com/builtin.xml",
            db=conn,
        )
        assert job_rss.feed_id is not None
        # The feed row should have the url set
        feed_row = conn.execute(
            "SELECT url FROM feeds WHERE id = ?", (job_rss.feed_id,)
        ).fetchone()
        assert feed_row["url"] == "https://rss.example.com/builtin.xml"
        print("[PASS] upsert_job with feed_url populates feeds.url")

        print("\n=== All smoke tests passed! ===")

    finally:
        close_db()
        Path(db_path).unlink(missing_ok=True)
        Path(db_path + "-wal").unlink(missing_ok=True)
        Path(db_path + "-shm").unlink(missing_ok=True)


if __name__ == "__main__":
    main()
