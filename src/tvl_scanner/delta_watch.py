"""Delta-watch: surface fresh, unaudited code on fund-exit paths.

The highest-yield audit surface is not a protocol audited cold — it is the
*delta* since an actively-developed protocol's last audit. This module tracks a
watchlist of protocols (`data/delta_watch_targets.yaml`), and for each one
GitHub-compares a baseline commit against the current HEAD, flags new commits
touching fund-exit paths (withdraw/redeem/borrow/liquidate/collateral/mint/
flashloan/...), scores them, and writes a delta report in the same per-candidate
YAML format the vault handoff consumes.

Baseline precedence (per target):
    1. `audited_at_commit` from the watchlist  → cumulative since-audit surface
    2. last-checked commit from the state file  → incremental since-last-run
    3. current HEAD (first run)                 → record only, no delta

State persists under ARTIFACTS_DIR so reruns are incremental for targets with
no known audit commit.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import date
from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml

from tvl_scanner.config import get_secret, settings
from tvl_scanner.enrich.github import parse_github_url
from tvl_scanner.enrich.github_delta import ChangedFile, audit_branches_ahead, fetch_delta
from tvl_scanner.http import make_client
from tvl_scanner.models import (
    Chain,
    DeltaWatchResult,
    FundPathChange,
    Language,
)

log = logging.getLogger(__name__)


@dataclass
class WatchTarget:
    slug: str
    display_name: str
    github: str
    chains: list[Chain] = field(default_factory=list)
    languages: list[Language] = field(default_factory=list)
    branch: str | None = None  # watch this ref instead of the default branch
    audited_at_commit: str | None = None
    audited_at_date: date | None = None
    bounty_program: str = "none"
    bounty_max_payout_usd: int | None = None
    # Per-target extra fund-path keywords, merged with the global
    # FUND_PATH_KEYWORDS for THIS target only. For protocols whose fund logic is
    # named with domain terms the generic list misses (e.g. tranche/yield
    # protocols: 'strateg', 'accounting', 'cdo', 'cooldown', 'redemption'). Keeps
    # noise off other targets while giving each protocol accurate delta coverage.
    extra_keywords: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Watchlist + state
# ---------------------------------------------------------------------------


def load_watchlist() -> list[WatchTarget]:
    """Parse `data/delta_watch_targets.yaml` into WatchTarget entries.

    Degrades to an empty list on parse failure so a malformed seed file can't
    kill the watcher.
    """
    try:
        resource = files("tvl_scanner.data").joinpath("delta_watch_targets.yaml")
        raw = resource.read_text(encoding="utf-8")
    except Exception as exc:
        log.error("delta-watch: target list not found: %s", exc)
        return []

    data = yaml.safe_load(raw) or []
    if not isinstance(data, list):
        log.error("delta-watch: target list is not a list")
        return []

    out: list[WatchTarget] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        slug = item.get("slug")
        gh = item.get("github")
        name = item.get("display_name")
        if not (isinstance(slug, str) and isinstance(gh, str) and isinstance(name, str)):
            continue
        out.append(
            WatchTarget(
                slug=slug.strip().lower(),
                display_name=name,
                github=gh.strip(),
                chains=_coerce_enum_list(item.get("chains"), Chain),
                languages=_coerce_enum_list(item.get("languages"), Language),
                branch=_opt_str(item.get("branch")),
                audited_at_commit=_opt_str(item.get("audited_at_commit")),
                audited_at_date=_opt_date(item.get("audited_at_date")),
                bounty_program=item.get("bounty_program") or "none",
                bounty_max_payout_usd=_opt_int(item.get("bounty_max_payout_usd")),
                extra_keywords=_coerce_str_list(item.get("extra_keywords")),
            )
        )
    log.info("delta-watch: loaded %d watch target(s)", len(out))
    return out


def _coerce_enum_list(raw: Any, enum_cls: Any) -> list[Any]:
    if not isinstance(raw, list):
        return []
    out = []
    for v in raw:
        try:
            out.append(enum_cls(str(v).strip().lower()))
        except ValueError:
            log.debug("delta-watch: ignoring unknown %s value %r", enum_cls.__name__, v)
    return out


def _coerce_str_list(raw: Any) -> list[str]:
    """Parse a YAML list of strings → lowercased, stripped, de-duped, non-empty."""
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


def _opt_str(v: Any) -> str | None:
    return str(v).strip() if isinstance(v, (str, int)) and str(v).strip() else None


def _opt_int(v: Any) -> int | None:
    return int(v) if isinstance(v, int) else None


def _opt_date(v: Any) -> date | None:
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        try:
            return date.fromisoformat(v.strip())
        except ValueError:
            return None
    return None


def _state_path() -> Path:
    s = settings()
    return s.artifacts_path / s.DELTA_WATCH_STATE_FILE


def load_state(path: Path | None = None) -> dict[str, dict[str, str]]:
    """Load the per-target {last_checked_commit, last_checked_date} state."""
    p = path or _state_path()
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("delta-watch: could not read state %s: %s", p, exc)
        return {}
    return data if isinstance(data, dict) else {}


def save_state(state: dict[str, dict[str, str]], path: Path | None = None) -> None:
    p = path or _state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2, sort_keys=True))


# ---------------------------------------------------------------------------
# Fund-path classification + scoring
# ---------------------------------------------------------------------------


def classify_fund_path(filename: str, keywords: list[str]) -> str | None:
    """Return the first FUND_PATH_KEYWORD the path matches, or None.

    Non-production artifacts are excluded even when their name contains a fund
    keyword — they are not live fund-exit surfaces:
      - test / mock files and dirs
      - docs, audit reports, images (.md/.txt/.rst/.pdf/.svg/...)
      - config & data (.json/.yaml/.toml/.lock/...) — e.g. deploy-address JSONs
      - formal-verification specs (.spec/.conf) and the `certora/` dir
      - deploy/build artifact dirs (deployments/, broadcast/)
    Without this, a delta of Certora specs + deployment JSONs (which match
    teller/accountant/vault by FILENAME, not by behaviour) inflates the score
    with zero exploitable code — observed on the 2026-06-29 Veda run, where all
    41 "fund-path" files were specs/JSONs/PDFs.

    The exclusion is path-segment aware so it never false-excludes a real source
    file whose name merely contains a substring like "test" (e.g.
    "latest_price.rs", where "latest_" contains "test_"). Bias remains toward
    INCLUDING real source — only non-code extensions and known artifact dirs are
    dropped, never .sol/.rs/.move/.vy source.
    """
    lower = filename.lower()
    # Non-code extensions: docs/reports, config/data, formal-verification specs,
    # images. A fund keyword in one of these is a filename coincidence, not code.
    if lower.endswith(
        (
            ".md", ".txt", ".rst", ".pdf",
            ".json", ".yaml", ".yml", ".toml", ".lock", ".cfg", ".ini", ".env", ".csv",
            ".spec", ".conf",
            ".svg", ".png", ".jpg", ".jpeg", ".gif",
        )
    ):
        return None
    segments = lower.split("/")
    # Non-production dirs: tests/mocks + formal-verification, deploy, audit, docs.
    excluded_dirs = {
        "test", "tests", "mock", "mocks", "__tests__", "__mocks__", "testing",
        "certora", "audit", "audits", "deployments", "deployment", "broadcast",
        "docs", "doc",
    }
    if any(seg in excluded_dirs for seg in segments[:-1]):
        return None
    base = segments[-1]
    name = base.rsplit(".", 1)[0]  # strip extension
    if (
        name.startswith("test_")
        or name.startswith("mock_")
        or name.endswith(("_test", "_tests", "_mock", "_mocks"))
        or name in {"test", "tests", "mock", "mocks"}
        or ".test." in base
        or ".spec." in base  # JS/TS specs: foo.spec.ts
        or base.endswith(".t.sol")  # Foundry test contracts
    ):
        return None
    for kw in keywords:
        if kw in lower:
            return kw
    return None


def _fund_path_changes(files_changed: list[ChangedFile], keywords: list[str]) -> list[FundPathChange]:
    out: list[FundPathChange] = []
    for f in files_changed:
        kw = classify_fund_path(f.filename, keywords)
        if kw is None:
            continue
        if f.is_comment_only:
            # Pure comment/doc churn (NatSpec, a `// Last audited:` header sweep)
            # — matches a fund keyword by FILENAME but changes no code. Dropping
            # it stops doc-only diffs from inflating the fund-path count/score.
            continue
        # additions/deletions report CODE lines when known (comment lines excluded).
        out.append(
            FundPathChange(
                path=f.filename,
                status=f.status,
                additions=f.code_additions if f.code_additions is not None else f.additions,
                deletions=f.code_deletions if f.code_deletions is not None else f.deletions,
                matched_keyword=kw,
            )
        )
    return out


# Multiplier applied when the scoped branch is frozen behind unmerged audit
# branches: the fresh-looking delta is a known-issue minefield (its strongest
# bugs are likely already whitehat/audit-firm reported = duplicates), so damp
# it hard — but not to zero, since the deployed contracts may still lag the
# fixed branches (Primacy-of-Impact caveat).
_FROZEN_BRANCH_DAMPING = 0.4


def score_delta(
    fund_path_files: int,
    fund_path_additions: int,
    bounty_program: str,
    *,
    truncated: bool = False,
    notable_commits: int = 0,
    total_commits: int = 0,
    audit_branches_ahead: int = 0,
) -> float:
    """Rank score: CODE additions dominate; fund-path file count is a minor
    breadth tiebreaker; a live bounty adds a flat bonus (a Critical there has a
    payout). Weighting code volume over raw file count stops a broad +1-line
    sweep from outranking a few substantive changes. `fund_path_additions`
    counts CODE lines only — comment-only files are dropped in _fund_path_changes.

    When the file list is truncated the fund-path count is unreliable, so we
    rank on the commit-log signal instead (keyword-flagged commits + commit
    volume) — otherwise a large, clearly-active delta would score ~0 and sink to
    the bottom purely because GitHub wouldn't return its files.

    `audit_branches_ahead > 0` means the scoped branch is frozen behind unmerged
    audit branches (a known-issue minefield); the score is damped by
    `_FROZEN_BRANCH_DAMPING` so such targets sink in the ranking.
    """
    score = 0.5 * fund_path_files
    score += min(30.0, fund_path_additions / 3.0)
    if bounty_program and bounty_program != "none":
        score += 2.0
    if truncated:
        score += 2.0 * min(notable_commits, 5)  # up to +10 from flagged commits
        score += min(5.0, total_commits / 20.0)  # bounded commit-volume bonus
    if audit_branches_ahead > 0:
        score *= _FROZEN_BRANCH_DAMPING
    return round(score, 2)


def _why(
    result_commits: int,
    fund_files: int,
    additions: int,
    source: str,
    *,
    truncated: bool = False,
    notable: int = 0,
    frozen_branches: int = 0,
) -> str:
    frozen = (
        f" — ⚠ scoped branch FROZEN behind {frozen_branches} unmerged audit branch(es); "
        "likely known-issue minefield (bugs already whitehat/audit-firm reported), deprioritized"
        if frozen_branches > 0
        else ""
    )
    if fund_files > 0:
        msg = (
            f"{fund_files} fund-exit file(s) changed (+{additions} lines) across "
            f"{result_commits} unaudited commit(s) since {source}"
        )
        if truncated:
            msg += " — file list incomplete (GitHub 300-file cap); audit the commit log too"
        return msg + frozen
    if truncated:
        # A 0 here is NOT "nothing on fund paths" — the scan couldn't enumerate
        # the full diff. Point the reader at the commit log instead.
        tail = f" ({notable} keyword-flagged)" if notable else ""
        return (
            f"{result_commits} new commit(s) since {source}; file list TRUNCATED "
            f"(GitHub 300-file cap) — fund-path scan incomplete, audit via commit log{tail}"
        )
    return f"{result_commits} new commit(s) since {source}, none on fund-exit paths"


# ---------------------------------------------------------------------------
# Per-target check
# ---------------------------------------------------------------------------


async def check_target(
    target: WatchTarget,
    state: dict[str, dict[str, str]],
    *,
    client: Any | None = None,
) -> DeltaWatchResult | None:
    """Compare a target's baseline against HEAD and build a DeltaWatchResult.

    Returns None if the repo is inaccessible. A result with total_commits=0
    means nothing changed since the baseline. Mutates `state` with the new HEAD.
    """
    # Global fund-path keywords + this target's extra keywords (deduped). The
    # per-target extras give protocols whose fund logic is named with domain
    # terms (tranche/yield: strateg/accounting/cdo/...) accurate delta coverage
    # without adding that noise to other targets' classification.
    keywords = list(dict.fromkeys(settings().FUND_PATH_KEYWORDS + target.extra_keywords))
    prior = state.get(target.slug, {})

    # Baseline precedence: audited commit → last checked → first run (None).
    if target.audited_at_commit:
        base: str | None = target.audited_at_commit
        baseline_source = "audited_commit"
    elif prior.get("last_checked_commit"):
        base = prior["last_checked_commit"]
        baseline_source = "last_checked"
    else:
        base = None
        baseline_source = "first_run"

    fetched = await fetch_delta(target.github, base, branch=target.branch, client=client)
    if fetched is None:
        log.warning("delta-watch: %s repo inaccessible (%s)", target.slug, target.github)
        return None
    branch, head_sha, comparison = fetched

    # Record the new HEAD for the next run regardless of outcome.
    state[target.slug] = {
        "last_checked_commit": head_sha,
        "last_checked_date": date.today().isoformat(),
    }

    if comparison is None:
        # First run (no baseline) or base == head (no change).
        return DeltaWatchResult(
            target_name=target.slug,
            display_name=target.display_name,
            languages=target.languages,
            chains=target.chains,
            github_repo=target.github,
            bounty_program=target.bounty_program,
            bounty_max_payout_usd=target.bounty_max_payout_usd,
            default_branch=branch,
            baseline_commit=base or head_sha,
            baseline_source=baseline_source,  # type: ignore[arg-type]
            audited_at_date=target.audited_at_date,
            head_commit=head_sha,
            total_commits=0,
            why_interesting=(
                "baseline recorded — no prior commit to diff (first run)"
                if base is None
                else "no new commits since baseline"
            ),
            checked_date=date.today(),
        )

    fund_changes = _fund_path_changes(comparison.files, keywords)
    fund_additions = sum(c.additions for c in fund_changes)
    notable = _notable_commits(comparison, keywords)

    # Frozen-branch check: is the scoped branch lagging unmerged audit branches?
    # (Advisory ranking signal — never blocks the delta; [] on any error.)
    frozen_branches: list[str] = []
    parsed_repo = parse_github_url(target.github)
    if parsed_repo is not None:
        owner, repo = parsed_repo
        frozen_branches = await audit_branches_ahead(owner, repo, branch, client=client)

    score = score_delta(
        len(fund_changes),
        fund_additions,
        target.bounty_program,
        truncated=comparison.truncated,
        notable_commits=len(notable),
        total_commits=comparison.total_commits,
        audit_branches_ahead=len(frozen_branches),
    )
    source_label = (
        f"audit ({target.audited_at_date.isoformat()})"
        if baseline_source == "audited_commit" and target.audited_at_date
        else baseline_source.replace("_", " ")
    )

    return DeltaWatchResult(
        target_name=target.slug,
        display_name=target.display_name,
        languages=target.languages,
        chains=target.chains,
        github_repo=target.github,
        bounty_program=target.bounty_program,
        bounty_max_payout_usd=target.bounty_max_payout_usd,
        default_branch=branch,
        baseline_commit=base or head_sha,
        baseline_source=baseline_source,  # type: ignore[arg-type]
        audited_at_date=target.audited_at_date,
        head_commit=head_sha,
        total_commits=comparison.total_commits,
        total_files_changed=len(comparison.files),
        fund_path_changes=fund_changes,
        fund_path_files_changed=len(fund_changes),
        fund_path_additions=fund_additions,
        notable_commits=notable,
        files_truncated=comparison.truncated,
        unmerged_audit_branches=frozen_branches,
        delta_score=score,
        why_interesting=_why(
            comparison.total_commits,
            len(fund_changes),
            fund_additions,
            source_label,
            truncated=comparison.truncated,
            notable=len(notable),
            frozen_branches=len(frozen_branches),
        ),
        checked_date=date.today(),
    )


def _notable_commits(comparison: Any, keywords: list[str]) -> list[str]:
    """Commit subjects whose message mentions a fund-path keyword (signal of intent)."""
    out: list[str] = []
    for c in comparison.commits:
        subj = c.subject
        low = subj.lower()
        if any(kw in low for kw in keywords):
            out.append(subj)
    return out[:15]


# ---------------------------------------------------------------------------
# Orchestration + report
# ---------------------------------------------------------------------------


async def run_delta_watch(
    *,
    targets: set[str] | None = None,
    scan_date: date | None = None,
    reports_dir: Path | None = None,
    state_path: Path | None = None,
) -> Path:
    """Run the delta-watch over the watchlist and write a report.

    Args:
        targets: if given, only check these slugs.
        scan_date / reports_dir / state_path: overridable for tests.

    Returns the summary report path.
    """
    sdate = scan_date or date.today()
    watchlist = load_watchlist()
    if targets:
        watchlist = [t for t in watchlist if t.slug in targets]
    if not watchlist:
        log.warning("delta-watch: no targets to check")

    state = load_state(state_path)

    log.info("=== delta-watch: checking %d target(s) ===", len(watchlist))
    headers = _github_headers()
    sem = asyncio.Semaphore(settings().DELTA_WATCH_CONCURRENCY)
    client = make_client(headers=headers)
    try:

        async def _bounded(t: WatchTarget) -> DeltaWatchResult | None:
            async with sem:
                return await check_target(t, state, client=client)

        # return_exceptions=True so one target's failure (an unexpected compare
        # payload, a validation error) doesn't abort the whole watchlist and
        # lose the state updates for every other target.
        gathered = await asyncio.gather(
            *(_bounded(t) for t in watchlist), return_exceptions=True
        )
    finally:
        await client.aclose()

    results: list[DeltaWatchResult] = []
    for target, outcome in zip(watchlist, gathered, strict=True):
        if isinstance(outcome, BaseException):
            log.error("delta-watch: %s check failed, skipping: %s", target.slug, outcome)
            continue
        if outcome is not None:
            results.append(outcome)
    save_state(state, state_path)

    # Rank: targets with a delta first (fund-path files OR, when the file list
    # was truncated, a commit-log signal — see DeltaWatchResult.has_delta), by
    # score; then the rest.
    results.sort(key=lambda r: (r.has_delta, r.delta_score), reverse=True)

    with_delta = [r for r in results if r.has_delta]
    log.info(
        "=== delta-watch: %d/%d target(s) have new fund-path commits ===",
        len(with_delta),
        len(results),
    )

    summary_path, _ = write_delta_report(results, sdate, reports_dir=reports_dir)
    return summary_path


def _github_headers() -> dict[str, str]:
    token = get_secret("github", required=False)
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def write_delta_report(
    results: list[DeltaWatchResult],
    scan_date: date,
    *,
    reports_dir: Path | None = None,
) -> tuple[Path, list[Path]]:
    """Write `reports/{date}-delta-watch.md` + per-target YAML records."""
    import shutil

    out_dir = reports_dir or settings().reports_path
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = f"{scan_date.isoformat()}-delta-watch"
    summary_path = out_dir / f"{slug}.md"
    targets_dir = out_dir / slug / "targets"
    if targets_dir.parent.exists():
        shutil.rmtree(targets_dir.parent)
    targets_dir.mkdir(parents=True, exist_ok=True)

    record_paths: list[Path] = []
    for rank, r in enumerate(results, start=1):
        record_paths.append(_write_target_file(r, rank, targets_dir))

    summary_path.write_text(_summary_markdown(results, scan_date, slug))
    return summary_path, record_paths


def _summary_markdown(results: list[DeltaWatchResult], scan_date: date, slug: str) -> str:
    with_delta = [r for r in results if r.has_delta]
    lines: list[str] = [
        f"# Delta-Watch Report — {scan_date.isoformat()}",
        "",
        f"Tracked {len(results)} protocol(s); **{len(with_delta)}** have new commits "
        "to fund-exit paths since their baseline.",
        "",
        "| Rank | Protocol | Chains | Fund-path files | +lines | Commits | Since | Bounty | Score | Record |",
        "| ---- | -------- | ------ | --------------- | ------ | ------- | ----- | ------ | ----- | ------ |",
    ]
    for rank, r in enumerate(results, start=1):
        chains = ",".join(c.value if isinstance(c, Chain) else str(c) for c in r.chains) or "—"
        bounty = (
            f"${r.bounty_max_payout_usd:,}"
            if r.bounty_max_payout_usd
            else (r.bounty_program if r.bounty_program != "none" else "—")
        )
        since = r.audited_at_date.isoformat() if r.audited_at_date else r.baseline_source
        link = f"[{r.target_name}]({slug}/targets/{rank:02d}-{r.target_name}.md)"
        lines.append(
            f"| {rank} | {r.display_name} | {chains} | {r.fund_path_files_changed} | "
            f"+{r.fund_path_additions} | {r.total_commits} | {since} | {bounty} | "
            f"{r.delta_score} | {link} |"
        )
    lines += [
        "",
        "## Next step",
        "",
        "For a top-ranked target, audit ONLY the delta — the fund-path files listed in "
        "its record, diffed against the baseline commit. That is fresh, unaudited code on "
        "permissionless paths. Open the per-target record for the file list and the "
        "`git diff baseline..HEAD` scope.",
        "",
    ]
    return "\n".join(lines)


def _write_target_file(r: DeltaWatchResult, rank: int, out_dir: Path) -> Path:
    frontmatter: dict[str, Any] = {
        "target_name": r.target_name,
        "display_name": r.display_name,
        "protocol_type": r.protocol_type,
        "languages": [lang.value if isinstance(lang, Language) else str(lang) for lang in r.languages],
        "chains": [c.value if isinstance(c, Chain) else str(c) for c in r.chains],
        "github_repo": r.github_repo,
        "default_branch": r.default_branch,
        "baseline_commit": r.baseline_commit,
        "baseline_source": r.baseline_source,
        "audited_at_date": r.audited_at_date.isoformat() if r.audited_at_date else None,
        "head_commit": r.head_commit,
        "total_commits": r.total_commits,
        "total_files_changed": r.total_files_changed,
        "fund_path_files_changed": r.fund_path_files_changed,
        "fund_path_additions": r.fund_path_additions,
        "files_truncated": r.files_truncated,
        "delta_score": r.delta_score,
        "bounty_program": r.bounty_program,
        "bounty_max_payout_usd": r.bounty_max_payout_usd,
        "why_interesting": r.why_interesting,
        "scan_date": r.checked_date.isoformat(),
    }
    yaml_text = yaml.safe_dump(
        frontmatter, sort_keys=False, default_flow_style=False, allow_unicode=True
    )
    body = _target_body(r)
    path = out_dir / f"{rank:02d}-{r.target_name}.md"
    path.write_text(f"---\n{yaml_text}---\n\n{body}")
    return path


def _target_body(r: DeltaWatchResult) -> str:
    lines: list[str] = [
        f"# {r.display_name} — delta-watch",
        "",
        f"> {r.why_interesting}",
        "",
        "## Delta",
        "",
        f"- **Repo**: {r.github_repo} (`{r.default_branch}`)",
        f"- **Baseline**: `{r.baseline_commit}` ({r.baseline_source}"
        + (f", audited {r.audited_at_date.isoformat()}" if r.audited_at_date else "")
        + ")",
        f"- **HEAD**: `{r.head_commit}`",
        f"- **New commits**: {r.total_commits} ({r.total_files_changed} files changed)",
        f"- **Fund-exit files changed**: {r.fund_path_files_changed} (+{r.fund_path_additions} lines)",
        f"- **Delta score**: {r.delta_score}",
    ]
    if r.files_truncated:
        lines.append("- ⚠️ GitHub capped the file list at 300 — some changes not shown.")
    if r.bounty_program != "none":
        payout = f" (max ${r.bounty_max_payout_usd:,})" if r.bounty_max_payout_usd else ""
        lines.append(f"- **Bounty**: {r.bounty_program}{payout}")

    if r.fund_path_changes:
        lines += [
            "",
            "## Fund-exit path changes (audit these)",
            "",
            "| File | Status | code +/- | Matched |",
            "| ---- | ------ | -------- | ------- |",
        ]
        for c in sorted(r.fund_path_changes, key=lambda x: x.additions, reverse=True):
            lines.append(
                f"| `{c.path}` | {c.status} | +{c.additions}/-{c.deletions} | {c.matched_keyword} |"
            )

    if r.notable_commits:
        lines += ["", "## Notable commits (mention a fund-path keyword)", ""]
        lines += [f"- {subj}" for subj in r.notable_commits]

    lines += [
        "",
        "## Audit scope",
        "",
        "Diff the fund-exit files above against the baseline and audit ONLY that delta "
        "(not the pre-baseline code, which the prior audit already covered):",
        "",
        "```bash",
        f"git clone {r.github_repo} && cd {r.target_name}",
        f"git diff {r.baseline_commit}..{r.head_commit} -- <fund-exit files>",
        "```",
        "",
    ]
    return "\n".join(lines)
