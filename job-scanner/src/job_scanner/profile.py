"""Candidate profile — the definition of "suitable".

The profile is a YAML file the user edits; everything the scoring formula
weighs (skills, seniority, location, compensation floor, benefits) comes from
here, never from code. Resolution order for the file:

    1. explicit path (CLI `--profile`)
    2. `JOB_SCANNER_PROFILE_PATH` from .env / environment
    3. `profile.yaml` at the repo root (gitignored personal copy)
    4. packaged default `job_scanner/data/profile.yaml`

Unknown YAML keys are ignored and missing keys fall back to the field defaults,
so a minimal personal profile can override just one section.
"""

from __future__ import annotations

import logging
from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from job_scanner.config import settings

log = logging.getLogger(__name__)


class Profile(BaseModel):
    """Flattened, validated view of profile.yaml."""

    name: str = "default"

    # Role identity: a title matching one of these is a strong signal the
    # listing is the right KIND of job. Also used as search queries on sources
    # that support search (Remotive).
    role_keywords: list[str] = Field(default_factory=list)

    # Skills: core = the day-job stack (weighs heavily), bonus = nice-to-have.
    core_skills: list[str] = Field(default_factory=list)
    bonus_skills: list[str] = Field(default_factory=list)

    # Acceptable seniority markers in the title ("senior", "staff", "lead").
    seniority_levels: list[str] = Field(default_factory=list)

    # Hard dealbreakers: a title containing one of these is dropped pre-scoring.
    exclude_keywords: list[str] = Field(default_factory=list)

    # Location: remote_only drops onsite listings outside location_keywords;
    # location_keywords are the places/regions that work for you.
    remote_only: bool = True
    location_keywords: list[str] = Field(default_factory=list)

    # Compensation (annualized USD): below min scores near 0, at/above target
    # scores 10, unknown scores neutral.
    min_salary_usd: int = 60_000
    target_salary_usd: int = 150_000

    # Benefits that matter to you, matched against the listing description.
    benefits_keywords: list[str] = Field(default_factory=list)

    # Postings older than this score 0 freshness (stale listings rank down).
    max_age_days: int = 45

    # Company watchlist: Greenhouse board tokens / Lever company slugs to pull
    # directly, so dream-company openings never depend on aggregator coverage.
    greenhouse_boards: list[str] = Field(default_factory=list)
    lever_companies: list[str] = Field(default_factory=list)


def _lower_list(raw: Any) -> list[str]:
    """YAML list → lowercased, stripped, de-duped, non-empty strings."""
    if not isinstance(raw, list):
        return []
    seen: set[str] = set()
    out: list[str] = []
    for v in raw:
        if not isinstance(v, (str, int)):
            continue
        kw = str(v).strip().lower()
        if kw and kw not in seen:
            seen.add(kw)
            out.append(kw)
    return out


def _from_raw(data: dict[str, Any]) -> Profile:
    """Flatten the nested YAML layout into Profile fields."""
    skills = data.get("skills") if isinstance(data.get("skills"), dict) else {}
    location = data.get("location") if isinstance(data.get("location"), dict) else {}
    comp = data.get("compensation") if isinstance(data.get("compensation"), dict) else {}
    boards = data.get("company_boards") if isinstance(data.get("company_boards"), dict) else {}
    assert isinstance(skills, dict) and isinstance(location, dict)
    assert isinstance(comp, dict) and isinstance(boards, dict)

    defaults = Profile()
    return Profile(
        name=str(data.get("name") or defaults.name),
        role_keywords=_lower_list(data.get("role_keywords")),
        core_skills=_lower_list(skills.get("core")),
        bonus_skills=_lower_list(skills.get("bonus")),
        seniority_levels=_lower_list(data.get("seniority_levels")),
        exclude_keywords=_lower_list(data.get("exclude_keywords")),
        remote_only=bool(location.get("remote_only", defaults.remote_only)),
        location_keywords=_lower_list(location.get("keywords")),
        min_salary_usd=int(comp.get("min_salary_usd") or defaults.min_salary_usd),
        target_salary_usd=int(comp.get("target_salary_usd") or defaults.target_salary_usd),
        benefits_keywords=_lower_list(data.get("benefits_keywords")),
        max_age_days=int(data.get("max_age_days") or defaults.max_age_days),
        greenhouse_boards=_lower_list(boards.get("greenhouse")),
        lever_companies=_lower_list(boards.get("lever")),
    )


def load_profile(path: str | Path | None = None) -> Profile:
    """Load the profile per the resolution order in the module docstring."""
    s = settings()
    candidates: list[Path] = []
    if path:
        candidates.append(Path(path).expanduser())
    if s.PROFILE_PATH:
        candidates.append(Path(s.PROFILE_PATH).expanduser())
    candidates.append(s.repo_root / "profile.yaml")

    for p in candidates:
        if p.is_file():
            log.info("profile: loading %s", p)
            return _parse(p.read_text(encoding="utf-8"), source=str(p))
        if path and p == candidates[0]:
            # An explicitly requested profile that doesn't exist is an error,
            # not a silent fallback — the user would be scored against the
            # wrong definition of "suitable" without noticing.
            raise FileNotFoundError(f"profile not found: {p}")

    resource = files("job_scanner.data").joinpath("profile.yaml")
    log.info("profile: using packaged default")
    return _parse(resource.read_text(encoding="utf-8"), source="packaged default")


def _parse(raw: str, *, source: str) -> Profile:
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        log.warning("profile: %s is not a YAML mapping — using built-in defaults", source)
        return Profile()
    return _from_raw(data)
