"""Suitability score computation.

Every posting that survives the dealbreaker filter gets a suitability score on
a 0-10 scale — the weighted sum of six sub-scores, each normalized to [0, 10]
(same shape as the tvl-scanner priority formula):

    suitability = 0.30·skill_match   + 0.20·compensation + 0.15·location
                + 0.15·seniority     + 0.10·benefits     + 0.10·freshness

skill_match carries the most weight by design — a perfectly-paid job you're
not a fit for is still not suitable. Unknown facts (no salary stated, no
posting date) score neutral, never zero: missing data shouldn't bury a listing.
"""

from __future__ import annotations

import re
from datetime import date
from functools import lru_cache

from job_scanner.models import JobPosting, ScoredJob
from job_scanner.profile import Profile

# Weight distribution — sums to 1.0
W_SKILL = 0.30
W_COMP = 0.20
W_LOCATION = 0.15
W_SENIORITY = 0.15
W_BENEFITS = 0.10
W_FRESH = 0.10

# Suitability cutoff for inclusion in the final report
SUITABILITY_CUTOFF = 5.0

# Relevance gate: without a role-keyword hit, at least this many distinct skill
# hits are required — otherwise a well-paid remote job with zero profile
# overlap ("Head of Marketing", perfect comp/location) sails past the cutoff on
# the neutral scores alone.
MIN_SKILL_HITS_WITHOUT_ROLE = 2

# Seniority markers that mean "below the profile's floor" unless the profile
# explicitly lists them as acceptable.
_ANTI_SENIORITY = ("intern", "internship", "junior", "entry level", "graduate", "working student")

# Location tokens that geo-fence a "remote" job to a region. If a fenced
# listing's fence doesn't overlap the profile's location keywords, remote
# doesn't help ("Remote (US only)" is not remote for an APAC candidate).
_GEO_FENCE_TOKENS = (
    "usa", "u.s.", "us only", "us-only", "united states", "america", "canada",
    "europe", "eu only", "emea", "uk", "united kingdom", "latam", "australia",
)

_REMOTE_TOKENS = ("remote", "worldwide", "anywhere", "global")


def _blob(job: JobPosting) -> str:
    """The lowercase haystack keyword matching runs against."""
    return " ".join([job.title.lower(), " ".join(job.tags), job.description.lower()])


@lru_cache(maxsize=1024)
def _kw_re(kw: str) -> re.Pattern[str]:
    # Lookarounds rather than \b so keywords with non-word edges ("u.s.",
    # "4-day", "c++") still anchor correctly. A trailing plural is tolerated
    # so "smart contract" matches "Smart Contracts" — but nothing beyond it,
    # so "intern" still misses "internal"/"international".
    return re.compile(rf"(?<!\w){re.escape(kw)}(?:s|es)?(?!\w)")


def _kw_hit(haystack: str, kw: str) -> bool:
    """Word-boundary keyword match — 'rust' must not hit 'trust', nor
    'intern' hit 'international'. (Live-run regression, 2026-07-22.)"""
    return _kw_re(kw).search(haystack) is not None


def skill_match_score(job: JobPosting, profile: Profile) -> tuple[float, list[str], list[str]]:
    """Returns (score, matched_role_keywords, matched_skills).

    A role-keyword hit in the TITLE is the dominant signal (right kind of job);
    core/bonus skill hits in title+tags+description fill the rest. Without a
    title hit the score caps at 8 — skill soup in a wrong-role description
    shouldn't beat an actual role match.
    """
    title = job.title.lower()
    blob = _blob(job)
    role_hits = [kw for kw in profile.role_keywords if _kw_hit(title, kw)]
    core_hits = [kw for kw in profile.core_skills if _kw_hit(blob, kw)]
    bonus_hits = [kw for kw in profile.bonus_skills if _kw_hit(blob, kw)]

    score = (5.0 if role_hits else 0.0)
    score += min(6.0, 1.5 * len(core_hits))
    score += min(2.0, 0.5 * len(bonus_hits))
    return min(10.0, score), role_hits, core_hits + bonus_hits


def compensation_score(job: JobPosting, profile: Profile) -> float:
    """Map stated salary onto [0, 10]: below min → 0-3, min→3, target+→10.

    Unstated salary scores a neutral 5 — most crypto/security roles negotiate.
    """
    salary = job.best_salary_usd
    if salary is None:
        return 5.0
    if salary >= profile.target_salary_usd:
        return 10.0
    if salary >= profile.min_salary_usd:
        span = profile.target_salary_usd - profile.min_salary_usd
        if span <= 0:
            return 10.0
        return 3.0 + 7.0 * (salary - profile.min_salary_usd) / span
    return max(0.0, 3.0 * salary / profile.min_salary_usd)


def _is_remote(job: JobPosting) -> bool:
    loc = job.location.lower()
    return job.remote is True or any(t in loc for t in _REMOTE_TOKENS)


def _geo_fenced_out(job: JobPosting, profile: Profile) -> bool:
    """True when the location names a region that ISN'T in the profile.

    Only GEOGRAPHIC profile keywords can lift a fence — the generic remote
    tokens must not, or "Remote (US only)" would pass for an APAC profile just
    because "remote" is in its keyword list.
    """
    loc = job.location.lower()
    fences = [t for t in _GEO_FENCE_TOKENS if _kw_hit(loc, t)]
    if not fences:
        return False
    geo_keywords = [k for k in profile.location_keywords if k not in _REMOTE_TOKENS]
    return not any(_kw_hit(loc, k) for k in geo_keywords)


def location_score(job: JobPosting, profile: Profile) -> float:
    loc = job.location.lower()
    kw_hit = any(_kw_hit(loc, k) for k in profile.location_keywords)
    if _is_remote(job):
        if _geo_fenced_out(job, profile):
            return 3.0  # "Remote (US only)" for a non-US profile — long shot
        return 10.0
    if kw_hit:
        return 7.0  # onsite/hybrid, but somewhere that works
    if not loc:
        return 4.0  # unknown — don't bury it
    return 0.0 if profile.remote_only else 3.0


def seniority_score(job: JobPosting, profile: Profile) -> float:
    title = job.title.lower()
    wanted = [lvl for lvl in profile.seniority_levels if _kw_hit(title, lvl)]
    if wanted:
        return 10.0
    anti = [
        t for t in _ANTI_SENIORITY if _kw_hit(title, t) and t not in profile.seniority_levels
    ]
    if anti:
        return 0.0
    return 6.0  # many good postings omit seniority — neutral, slightly positive


def benefits_score(job: JobPosting, profile: Profile) -> tuple[float, list[str]]:
    """2.5 per matched benefit, capped at 10. Empty description → neutral 5."""
    if not job.description and not job.tags:
        return 5.0, []
    blob = _blob(job)
    hits = [kw for kw in profile.benefits_keywords if _kw_hit(blob, kw)]
    return min(10.0, 2.5 * len(hits)), hits


def freshness_score(job: JobPosting, profile: Profile, *, scan_date: date) -> float:
    """Linear decay from 10 (posted today) to 0 (at max_age_days). Unknown → 5."""
    if job.posted_at is None:
        return 5.0
    age = (scan_date - job.posted_at).days
    if age < 0:
        return 10.0
    if age >= profile.max_age_days:
        return 0.0
    return 10.0 * (1.0 - age / profile.max_age_days)


def dealbreaker(job: JobPosting, profile: Profile) -> str | None:
    """Hard filter, applied before scoring. Returns the reason, or None to keep.

    Only certainties are dropped: an excluded keyword in the TITLE, an
    anti-seniority title, or (for remote_only profiles) a listing that is
    explicitly onsite somewhere outside the profile's locations. Ambiguity
    always falls through to scoring.
    """
    title = job.title.lower()
    for kw in profile.exclude_keywords:
        if _kw_hit(title, kw):
            return f"excluded keyword: {kw}"
    if seniority_score(job, profile) == 0.0:
        return "below seniority floor"
    if (
        profile.remote_only
        and job.remote is False
        and not any(k in job.location.lower() for k in profile.location_keywords)
    ):
        # Reason strings stay location-free so rank_all's drop counts aggregate.
        return "onsite-only outside preferred locations"
    return None


def _why_suitable(
    job: JobPosting,
    role_hits: list[str],
    skills: list[str],
    benefits: list[str],
    *,
    scan_date: date,
) -> str:
    """Auto-generate the one-line summary shown in the report table."""
    parts: list[str] = []
    if role_hits:
        parts.append(f"role match: {role_hits[0]}")
    if skills:
        parts.append(f"skills: {', '.join(skills[:4])}")
    if job.best_salary_usd is not None:
        parts.append(f"~${job.best_salary_usd:,}/yr")
    if _is_remote(job):
        parts.append("remote")
    elif job.location:
        parts.append(job.location)
    if benefits:
        parts.append(f"benefits: {', '.join(benefits[:3])}")
    if job.posted_at is not None:
        parts.append(f"{max(0, (scan_date - job.posted_at).days)}d old")
    return " • ".join(parts) if parts else "matched profile above cutoff"


def rank_job(job: JobPosting, profile: Profile, *, scan_date: date) -> ScoredJob:
    """Compute all sub-scores and the weighted suitability for one posting."""
    skill_s, role_hits, skills = skill_match_score(job, profile)
    comp_s = compensation_score(job, profile)
    loc_s = location_score(job, profile)
    senior_s = seniority_score(job, profile)
    benefit_s, benefits = benefits_score(job, profile)
    fresh_s = freshness_score(job, profile, scan_date=scan_date)

    suitability = (
        skill_s * W_SKILL
        + comp_s * W_COMP
        + loc_s * W_LOCATION
        + senior_s * W_SENIORITY
        + benefit_s * W_BENEFITS
        + fresh_s * W_FRESH
    )

    return ScoredJob(
        **job.model_dump(),
        suitability_score=round(suitability, 2),
        skill_match_score=round(skill_s, 2),
        compensation_score=round(comp_s, 2),
        location_score=round(loc_s, 2),
        seniority_score=round(senior_s, 2),
        benefits_score=round(benefit_s, 2),
        freshness_score=round(fresh_s, 2),
        matched_role_keywords=role_hits,
        matched_skills=skills,
        matched_benefits=benefits,
        why_suitable=_why_suitable(job, role_hits, skills, benefits, scan_date=scan_date),
        scan_date=scan_date,
    )


def rank_all(
    jobs: list[JobPosting],
    profile: Profile,
    *,
    scan_date: date,
    cutoff: float = SUITABILITY_CUTOFF,
    cap: int = 40,
) -> tuple[list[ScoredJob], dict[str, int]]:
    """Filter dealbreakers, score, cut off, sort descending, cap.

    Returns (ranked jobs, dealbreaker-reason counts) so the report can say what
    was dropped and why — silent drops make a daily digest untrustworthy.
    """
    dropped: dict[str, int] = {}
    kept: list[ScoredJob] = []
    for job in jobs:
        reason = dealbreaker(job, profile)
        if reason is not None:
            key = reason.split(":")[0]
            dropped[key] = dropped.get(key, 0) + 1
            continue
        scored = rank_job(job, profile, scan_date=scan_date)
        # Relevance gate: neutral comp/location/seniority alone must not carry
        # a job the profile has essentially nothing in common with.
        if (
            not scored.matched_role_keywords
            and len(scored.matched_skills) < MIN_SKILL_HITS_WITHOUT_ROLE
        ):
            dropped["weak profile match"] = dropped.get("weak profile match", 0) + 1
            continue
        kept.append(scored)

    ranked = [j for j in kept if j.suitability_score >= cutoff]
    ranked.sort(key=lambda j: j.suitability_score, reverse=True)
    return ranked[:cap], dropped
