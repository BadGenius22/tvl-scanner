"""Report writer: daily summary markdown + per-role YAML records.

Same layout convention as the tvl-scanner reports:
    reports/YYYY-MM-DD-job-scan.md                  — ranked summary table
    reports/YYYY-MM-DD-job-scan/roles/<rank>-<slug>.md — one record per role,
        YAML frontmatter + human-readable body, liftable without transformation.
"""

from __future__ import annotations

import re
import shutil
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from job_scanner.config import settings
from job_scanner.models import ScoredJob

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(text: str, limit: int = 60) -> str:
    slug = _SLUG_RE.sub("-", text.lower()).strip("-")
    return slug[:limit] or "role"


def write_report(
    jobs: list[ScoredJob],
    scan_date: date,
    *,
    dropped: dict[str, int] | None = None,
    total_discovered: int = 0,
    reports_dir: Path | None = None,
) -> tuple[Path, list[Path]]:
    """Write the summary + per-role records; returns (summary_path, record_paths)."""
    out_dir = reports_dir or settings().reports_path
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = f"{scan_date.isoformat()}-job-scan"
    summary_path = out_dir / f"{slug}.md"
    roles_dir = out_dir / slug / "roles"
    if roles_dir.parent.exists():
        shutil.rmtree(roles_dir.parent)
    roles_dir.mkdir(parents=True, exist_ok=True)

    record_paths: list[Path] = []
    for rank, job in enumerate(jobs, start=1):
        record_paths.append(_write_role_file(job, rank, roles_dir))

    summary_path.write_text(
        _summary_markdown(jobs, scan_date, slug, dropped or {}, total_discovered)
    )
    return summary_path, record_paths


def _fmt_salary(job: ScoredJob) -> str:
    if job.salary_min_usd and job.salary_max_usd and job.salary_min_usd != job.salary_max_usd:
        return f"${job.salary_min_usd // 1000}k–${job.salary_max_usd // 1000}k"
    if job.best_salary_usd:
        return f"${job.best_salary_usd // 1000}k"
    return "—"


def _summary_markdown(
    jobs: list[ScoredJob],
    scan_date: date,
    slug: str,
    dropped: dict[str, int],
    total_discovered: int,
) -> str:
    new_count = sum(1 for j in jobs if j.is_new)
    lines: list[str] = [
        f"# Job Scan — {scan_date.isoformat()}",
        "",
        f"Discovered {total_discovered} listing(s); **{len(jobs)}** above the suitability "
        f"cutoff, **{new_count}** new since the last scan.",
        "",
        "| Rank | Role | Company | Location | Salary | Score | New | Source | Record |",
        "| ---- | ---- | ------- | -------- | ------ | ----- | --- | ------ | ------ |",
    ]
    for rank, j in enumerate(jobs, start=1):
        record = f"{rank:02d}-{_slugify(j.company + '-' + j.title)}"
        lines.append(
            f"| {rank} | [{j.title}]({j.url}) | {j.company} | {j.location or 'remote'} | "
            f"{_fmt_salary(j)} | {j.suitability_score} | {'🆕' if j.is_new else ''} | "
            f"{j.source.value} | [record]({slug}/roles/{record}.md) |"
        )

    if dropped:
        lines += ["", "## Dropped before scoring (dealbreakers)", ""]
        lines += [f"- {reason}: {count}" for reason, count in sorted(dropped.items())]

    lines += [
        "",
        "## Next step",
        "",
        "Open a top-ranked record for the score breakdown, matched skills, and the "
        "description snippet — then apply via the role link. Tune what \"suitable\" "
        "means in `profile.yaml` (skills, salary floor, locations, benefits).",
        "",
    ]
    return "\n".join(lines)


def _write_role_file(job: ScoredJob, rank: int, out_dir: Path) -> Path:
    frontmatter: dict[str, Any] = {
        "title": job.title,
        "company": job.company,
        "url": job.url,
        "source": job.source.value,
        "location": job.location or None,
        "remote": job.remote,
        "employment_type": job.employment_type,
        "salary_min_usd": job.salary_min_usd,
        "salary_max_usd": job.salary_max_usd,
        "salary_raw": job.salary_raw,
        "posted_at": job.posted_at.isoformat() if job.posted_at else None,
        "suitability_score": job.suitability_score,
        "scores": {
            "skill_match": job.skill_match_score,
            "compensation": job.compensation_score,
            "location": job.location_score,
            "seniority": job.seniority_score,
            "benefits": job.benefits_score,
            "freshness": job.freshness_score,
        },
        "matched_role_keywords": job.matched_role_keywords,
        "matched_skills": job.matched_skills,
        "matched_benefits": job.matched_benefits,
        "is_new": job.is_new,
        "scan_date": job.scan_date.isoformat(),
    }
    yaml_text = yaml.safe_dump(
        frontmatter, sort_keys=False, default_flow_style=False, allow_unicode=True
    )
    path = out_dir / f"{rank:02d}-{_slugify(job.company + '-' + job.title)}.md"
    path.write_text(f"---\n{yaml_text}---\n\n{_role_body(job)}")
    return path


def _role_body(job: ScoredJob) -> str:
    lines: list[str] = [
        f"# {job.title} — {job.company}",
        "",
        f"> {job.why_suitable}",
        "",
        f"**Apply**: {job.url}",
        "",
        "## Score breakdown",
        "",
        "| Dimension | Score | Weight |",
        "| --------- | ----- | ------ |",
        f"| Skill match | {job.skill_match_score} | 0.30 |",
        f"| Compensation | {job.compensation_score} | 0.20 |",
        f"| Location | {job.location_score} | 0.15 |",
        f"| Seniority | {job.seniority_score} | 0.15 |",
        f"| Benefits | {job.benefits_score} | 0.10 |",
        f"| Freshness | {job.freshness_score} | 0.10 |",
        f"| **Suitability** | **{job.suitability_score}** | |",
    ]
    if job.matched_skills or job.matched_role_keywords:
        lines += [
            "",
            "## Why it matched",
            "",
        ]
        if job.matched_role_keywords:
            lines.append(f"- Role keywords: {', '.join(job.matched_role_keywords)}")
        if job.matched_skills:
            lines.append(f"- Skills: {', '.join(job.matched_skills)}")
        if job.matched_benefits:
            lines.append(f"- Benefits: {', '.join(job.matched_benefits)}")
    if job.description:
        snippet = job.description[:800]
        lines += ["", "## Description (snippet)", "", snippet + ("…" if len(job.description) > 800 else "")]
    lines.append("")
    return "\n".join(lines)
