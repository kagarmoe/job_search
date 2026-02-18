"""Stub CRUD operations for profile tables.

Full implementations will be added in Epic 3 (Profile Backend).
"""

from __future__ import annotations

import sqlite3

from .connection import get_db
from .models import (
    Certification,
    Education,
    Honor,
    JobHistory,
    ProfileMeta,
    Skill,
)


# --- profile_meta ---

def set_meta(key: str, value: str, *, db: sqlite3.Connection | None = None) -> None:
    """Set a profile metadata key-value pair (upsert)."""
    conn = db or get_db()
    conn.execute(
        """
        INSERT INTO profile_meta (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (key, value),
    )
    conn.commit()


def get_meta(key: str, *, db: sqlite3.Connection | None = None) -> str | None:
    """Get a profile metadata value by key."""
    conn = db or get_db()
    row = conn.execute(
        "SELECT value FROM profile_meta WHERE key = ?", (key,)
    ).fetchone()
    return row["value"] if row else None


def get_all_meta(*, db: sqlite3.Connection | None = None) -> dict[str, str]:
    """Get all profile metadata as a dict."""
    conn = db or get_db()
    rows = conn.execute("SELECT key, value FROM profile_meta").fetchall()
    return {r["key"]: r["value"] for r in rows}


# --- job_history ---

def add_job_history(
    company: str,
    title: str,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    location: str | None = None,
    description: str | None = None,
    sort_order: int | None = None,
    db: sqlite3.Connection | None = None,
) -> JobHistory:
    """Add a work experience entry."""
    conn = db or get_db()
    cursor = conn.execute(
        """
        INSERT INTO job_history (company, title, start_date, end_date, location, description, sort_order)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        RETURNING *
        """,
        (company, title, start_date, end_date, location, description, sort_order),
    )
    row = cursor.fetchone()
    conn.commit()
    return JobHistory.from_row(row)


def list_job_history(*, db: sqlite3.Connection | None = None) -> list[JobHistory]:
    """List all work experience entries ordered by sort_order."""
    conn = db or get_db()
    rows = conn.execute(
        "SELECT * FROM job_history ORDER BY sort_order"
    ).fetchall()
    return [JobHistory.from_row(r) for r in rows]


# --- education ---

def add_education(
    institution: str,
    *,
    degree: str | None = None,
    field: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    description: str | None = None,
    sort_order: int | None = None,
    db: sqlite3.Connection | None = None,
) -> Education:
    """Add an education entry."""
    conn = db or get_db()
    cursor = conn.execute(
        """
        INSERT INTO education (institution, degree, field, start_date, end_date, description, sort_order)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        RETURNING *
        """,
        (institution, degree, field, start_date, end_date, description, sort_order),
    )
    row = cursor.fetchone()
    conn.commit()
    return Education.from_row(row)


def list_education(*, db: sqlite3.Connection | None = None) -> list[Education]:
    """List all education entries ordered by sort_order."""
    conn = db or get_db()
    rows = conn.execute(
        "SELECT * FROM education ORDER BY sort_order"
    ).fetchall()
    return [Education.from_row(r) for r in rows]


# --- certifications ---

def add_certification(
    name: str,
    *,
    issuer: str | None = None,
    date_earned: str | None = None,
    sort_order: int | None = None,
    db: sqlite3.Connection | None = None,
) -> Certification:
    """Add a certification entry."""
    conn = db or get_db()
    cursor = conn.execute(
        """
        INSERT INTO certifications (name, issuer, date_earned, sort_order)
        VALUES (?, ?, ?, ?)
        RETURNING *
        """,
        (name, issuer, date_earned, sort_order),
    )
    row = cursor.fetchone()
    conn.commit()
    return Certification.from_row(row)


def list_certifications(*, db: sqlite3.Connection | None = None) -> list[Certification]:
    """List all certifications ordered by sort_order."""
    conn = db or get_db()
    rows = conn.execute(
        "SELECT * FROM certifications ORDER BY sort_order"
    ).fetchall()
    return [Certification.from_row(r) for r in rows]


# --- honors ---

def add_honor(
    name: str,
    *,
    issuer: str | None = None,
    description: str | None = None,
    sort_order: int | None = None,
    db: sqlite3.Connection | None = None,
) -> Honor:
    """Add an honor/award entry."""
    conn = db or get_db()
    cursor = conn.execute(
        """
        INSERT INTO honors (name, issuer, description, sort_order)
        VALUES (?, ?, ?, ?)
        RETURNING *
        """,
        (name, issuer, description, sort_order),
    )
    row = cursor.fetchone()
    conn.commit()
    return Honor.from_row(row)


def list_honors(*, db: sqlite3.Connection | None = None) -> list[Honor]:
    """List all honors ordered by sort_order."""
    conn = db or get_db()
    rows = conn.execute(
        "SELECT * FROM honors ORDER BY sort_order"
    ).fetchall()
    return [Honor.from_row(r) for r in rows]


# --- skills ---

def add_skill(
    name: str,
    category: str,
    *,
    proficiency: str | None = None,
    sort_order: int | None = None,
    db: sqlite3.Connection | None = None,
) -> Skill:
    """Add a skill (upserts on name)."""
    conn = db or get_db()
    cursor = conn.execute(
        """
        INSERT INTO skills (name, category, proficiency, sort_order)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            category    = excluded.category,
            proficiency = excluded.proficiency,
            sort_order  = excluded.sort_order
        RETURNING *
        """,
        (name, category, proficiency, sort_order),
    )
    row = cursor.fetchone()
    conn.commit()
    return Skill.from_row(row)


def list_skills(
    *, category: str | None = None, db: sqlite3.Connection | None = None
) -> list[Skill]:
    """List skills, optionally filtered by category."""
    conn = db or get_db()
    if category:
        rows = conn.execute(
            "SELECT * FROM skills WHERE category = ? ORDER BY sort_order",
            (category,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM skills ORDER BY category, sort_order"
        ).fetchall()
    return [Skill.from_row(r) for r in rows]
