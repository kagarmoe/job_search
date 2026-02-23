"""Dataclasses for database entities."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field


def _from_row(cls, row):
    """Create a dataclass instance from a sqlite3.Row, ignoring extra columns."""
    known = {f.name for f in dataclasses.fields(cls)}
    return cls(**{k: row[k] for k in row.keys() if k in known})


@dataclass
class Source:
    id: int | None = None
    name: str = ""

    @classmethod
    def from_row(cls, row) -> Source:
        return _from_row(cls, row)


@dataclass
class Feed:
    id: int | None = None
    name: str = ""
    url: str | None = None
    source_id: int | None = None
    last_fetch: str | None = None

    @classmethod
    def from_row(cls, row) -> Feed:
        return _from_row(cls, row)


@dataclass
class Job:
    id: int | None = None
    title: str = ""
    url: str = ""
    description: str | None = None
    posted_date: str | None = None
    source_id: int | None = None
    feed_id: int | None = None
    source: str | None = None  # populated from JOIN with sources table
    feed: str | None = None    # populated from JOIN with feeds table
    score: float | None = None
    score_rationale: str | None = None
    status: str = "new"
    location_label: str | None = None
    job_type: str | None = None
    pay_range: str | None = None
    contract_duration: str | None = None
    resume_md: str | None = None
    resume_pdf_path: str | None = None
    cover_letter_md: str | None = None
    cover_letter_pdf_path: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    @classmethod
    def from_row(cls, row) -> Job:
        return _from_row(cls, row)


@dataclass
class ProfileMeta:
    key: str = ""
    value: str = ""

    @classmethod
    def from_row(cls, row) -> ProfileMeta:
        return _from_row(cls, row)


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
        return _from_row(cls, row)


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
        return _from_row(cls, row)


@dataclass
class Certification:
    id: int | None = None
    name: str = ""
    issuer: str | None = None
    date_earned: str | None = None
    sort_order: int | None = None

    @classmethod
    def from_row(cls, row) -> Certification:
        return _from_row(cls, row)


@dataclass
class Honor:
    id: int | None = None
    name: str = ""
    issuer: str | None = None
    description: str | None = None
    sort_order: int | None = None

    @classmethod
    def from_row(cls, row) -> Honor:
        return _from_row(cls, row)


@dataclass
class Skill:
    id: int | None = None
    name: str = ""
    category: str = ""
    proficiency: str | None = None
    sort_order: int | None = None

    @classmethod
    def from_row(cls, row) -> Skill:
        return _from_row(cls, row)
