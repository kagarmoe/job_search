"""Dataclasses for database entities."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Job:
    id: int | None = None
    title: str = ""
    url: str = ""
    description: str | None = None
    posted_date: str | None = None
    source: str | None = None
    feed: str | None = None
    score: float | None = None
    score_rationale: str | None = None
    status: str = "new"
    location_label: str | None = None
    job_type: str | None = None
    pay_range: str | None = None
    resume_md: str | None = None
    resume_pdf_path: str | None = None
    cover_letter_md: str | None = None
    cover_letter_pdf_path: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    @classmethod
    def from_row(cls, row) -> Job:
        """Create a Job from a sqlite3.Row."""
        return cls(**{k: row[k] for k in row.keys()})


@dataclass
class ProfileMeta:
    key: str = ""
    value: str = ""

    @classmethod
    def from_row(cls, row) -> ProfileMeta:
        return cls(**{k: row[k] for k in row.keys()})


@dataclass
class JobHistory:
    id: int | None = None
    company: str = ""
    title: str = ""
    start_date: str | None = None
    end_date: str | None = None
    location: str | None = None
    description: str | None = None
    sort_order: int | None = None

    @classmethod
    def from_row(cls, row) -> JobHistory:
        return cls(**{k: row[k] for k in row.keys()})


@dataclass
class Education:
    id: int | None = None
    institution: str = ""
    degree: str | None = None
    field: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None
    sort_order: int | None = None

    @classmethod
    def from_row(cls, row) -> Education:
        return cls(**{k: row[k] for k in row.keys()})


@dataclass
class Certification:
    id: int | None = None
    name: str = ""
    issuer: str | None = None
    date_earned: str | None = None
    sort_order: int | None = None

    @classmethod
    def from_row(cls, row) -> Certification:
        return cls(**{k: row[k] for k in row.keys()})


@dataclass
class Honor:
    id: int | None = None
    name: str = ""
    issuer: str | None = None
    description: str | None = None
    sort_order: int | None = None

    @classmethod
    def from_row(cls, row) -> Honor:
        return cls(**{k: row[k] for k in row.keys()})


@dataclass
class Skill:
    id: int | None = None
    name: str = ""
    category: str = ""
    proficiency: str | None = None
    sort_order: int | None = None

    @classmethod
    def from_row(cls, row) -> Skill:
        return cls(**{k: row[k] for k in row.keys()})
