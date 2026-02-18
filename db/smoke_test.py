"""Smoke test for the database module.

Run: python -m db.smoke_test
"""

import sys
import tempfile
from pathlib import Path

from db.connection import init_db, close_db
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
            "certifications", "education", "honors", "job_history",
            "jobs", "profile_meta", "skills",
        }
        assert expected.issubset(set(tables)), f"Missing tables: {expected - set(tables)}"
        print(f"[PASS] All {len(expected)} tables created: {sorted(expected)}")

        # Insert a job
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
        print(f"[PASS] Inserted job id={job.id}")

        # Fetch by ID
        fetched = get_job(job.id, db=conn)
        assert fetched is not None
        assert fetched.url == "https://example.com/jobs/123"
        print(f"[PASS] get_job({job.id}) returned correct job")

        # Fetch by URL
        fetched_url = get_job_by_url("https://example.com/jobs/123", db=conn)
        assert fetched_url is not None
        assert fetched_url.id == job.id
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
        print(f"[PASS] list_jobs() returned {len(jobs)} job(s)")

        # Update status
        updated = update_status(job.id, "reviewed", db=conn)
        assert updated is not None
        assert updated.status == "reviewed"
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
        print(f"[PASS] list_jobs() filters work correctly")

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

        print("\n=== All smoke tests passed! ===")

    finally:
        close_db()
        Path(db_path).unlink(missing_ok=True)
        Path(db_path + "-wal").unlink(missing_ok=True)
        Path(db_path + "-shm").unlink(missing_ok=True)


if __name__ == "__main__":
    main()
