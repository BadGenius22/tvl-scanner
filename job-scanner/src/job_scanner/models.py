"""Data models for the job scanner.

Two-stage progression, mirroring the tvl_scanner class hierarchy: `JobPosting`
(discovery output, one per listing) → `ScoredJob` (extends with the suitability
sub-scores + derived fields the report renders). Each stage's output is a strict
superset of the previous, so records serialize once and lift anywhere.
"""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


class JobSource(str, Enum):
    REMOTIVE = "remotive"
    REMOTEOK = "remoteok"
    ARBEITNOW = "arbeitnow"
    GREENHOUSE = "greenhouse"
    LEVER = "lever"


class JobPosting(BaseModel):
    """One open role as discovered from a source, normalized.

    `job_id` is the stable dedupe/state key: `<source>:<native id or slug>`.
    Salary fields are best-effort annualized USD (see `salary.parse_salary_text`);
    None means the posting didn't state compensation, which scores neutral.
    """

    job_id: str
    source: JobSource
    title: str
    company: str
    url: str
    location: str = ""  # raw location text: "Remote", "Worldwide", "Berlin", ...
    remote: bool | None = None  # None = the source doesn't say
    salary_min_usd: int | None = None
    salary_max_usd: int | None = None
    salary_raw: str | None = None  # original salary text, kept for the report
    tags: list[str] = Field(default_factory=list)
    description: str = ""  # plain text (HTML stripped), truncated at source
    posted_at: date | None = None
    employment_type: str | None = None

    @property
    def best_salary_usd(self) -> int | None:
        """The figure compensation scoring uses: the top of the stated range."""
        if self.salary_max_usd is not None:
            return self.salary_max_usd
        return self.salary_min_usd


class ScoredJob(JobPosting):
    """JobPosting + suitability scoring. What the report renders."""

    suitability_score: float
    skill_match_score: float
    compensation_score: float
    location_score: float
    seniority_score: float
    benefits_score: float
    freshness_score: float
    matched_role_keywords: list[str] = Field(default_factory=list)
    matched_skills: list[str] = Field(default_factory=list)
    matched_benefits: list[str] = Field(default_factory=list)
    why_suitable: str = ""
    is_new: bool = True  # first time this job_id is seen (vs. the state file)
    scan_date: date
