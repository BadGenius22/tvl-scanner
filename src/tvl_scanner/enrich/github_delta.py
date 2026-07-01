"""GitHub commit-delta access for the delta-watch flow.

The first use of GitHub's `/commits` and `/compare` endpoints in the scanner
(enrich/github.py only uses `/repos`, `/users`, `/contents/audits`). Given a
repo and two refs, compute the set of commits and changed files between them so
delta-watch can flag new code on fund-exit paths since a protocol's last audit.

Reuses enrich/github.py's auth-header + URL-parse helpers and the shared
http.get_json() retry/backoff client. A 404 (gone repo / unknown ref) is a
normal negative — returns None, never raises.

GitHub compare caps the `files` array at 300 and the `commits` array at 250,
but the `total_commits` field is accurate. We surface a `truncated` flag when
the file list is capped so callers don't silently under-report.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

from tvl_scanner.config import settings
from tvl_scanner.enrich.github import _auth_headers, parse_github_url
from tvl_scanner.http import HttpError, get_json

log = logging.getLogger(__name__)

# GitHub caps the compare endpoint's `files` array at 300 and its `commits`
# array at 250. The file cap is HARD: the `page` query param paginates COMMITS,
# not files (verified empirically — page 2+ returns 0 files), and files come
# back alphabetically, so a >300-file diff silently drops every path sorting
# after the 300th (e.g. `src/` after `certora/`, `deployments/`, `script/`).
# To recover the complete set we split the commit range into sub-ranges, each
# small enough to stay under the cap, and union their files.
_COMPARE_FILE_CAP = 300
# Safety bound on how many compare calls one delta may trigger while
# subdividing — stops a pathological diff from fanning out unboundedly.
_MAX_COMPARE_CALLS = 60


@dataclass
class CommitInfo:
    sha: str
    message: str
    date: str | None = None

    @property
    def subject(self) -> str:
        """First line of the commit message."""
        return self.message.splitlines()[0] if self.message else ""


@dataclass
class ChangedFile:
    filename: str
    status: str
    additions: int = 0
    deletions: int = 0
    # Added/removed lines that are real CODE (not blank, not a // or /* */ *
    # comment), parsed from the diff patch. None = unknown (patch unavailable);
    # callers treat unknown as code and never drop it.
    code_additions: int | None = None
    code_deletions: int | None = None

    @property
    def is_comment_only(self) -> bool:
        """True only when the change touched ZERO code lines — pure comment/doc/
        blank churn (e.g. a NatSpec block or a repo-wide `// Last audited:`
        header sweep). Unknown counts (None, patch unavailable) are never
        comment-only, so a real change is never dropped on missing data."""
        if self.code_additions is None:
            return False
        return self.code_additions == 0 and (self.code_deletions or 0) == 0


@dataclass
class RepoComparison:
    """Result of `GET /compare/{base}...{head}`."""

    base: str
    head: str
    total_commits: int
    commits: list[CommitInfo] = field(default_factory=list)
    files: list[ChangedFile] = field(default_factory=list)
    truncated: bool = False


async def get_default_branch(
    owner: str, repo: str, *, client: httpx.AsyncClient | None = None
) -> str | None:
    """Return the repo's default branch, or None if the repo is inaccessible."""
    s = settings()
    try:
        main: Any = await get_json(
            f"{s.GITHUB_API_BASE}/repos/{owner}/{repo}",
            headers=_auth_headers(),
            client=client,
        )
    except HttpError as exc:
        log.info("github_delta: repo %s/%s not accessible (%s)", owner, repo, exc)
        return None
    if not isinstance(main, dict):
        return None
    branch = main.get("default_branch")
    return branch if isinstance(branch, str) else None


async def get_head_sha(
    owner: str, repo: str, ref: str, *, client: httpx.AsyncClient | None = None
) -> str | None:
    """Resolve a ref (branch name or sha) to its current commit sha.

    Uses `GET /commits/{ref}` which accepts a branch, tag, or sha and returns
    the resolved commit. Returns None if the ref doesn't resolve.
    """
    s = settings()
    try:
        payload: Any = await get_json(
            f"{s.GITHUB_API_BASE}/repos/{owner}/{repo}/commits/{ref}",
            headers=_auth_headers(),
            client=client,
        )
    except HttpError as exc:
        log.info("github_delta: ref %s not found in %s/%s (%s)", ref, owner, repo, exc)
        return None
    if not isinstance(payload, dict):
        return None
    sha = payload.get("sha")
    return sha if isinstance(sha, str) else None


# Branch names that suggest an audit line: `audit/*`, or a known audit firm.
_AUDIT_BRANCH_RE = re.compile(
    r"audit|bailsec|cyfrin|certora|zenith|spearbit|trail.?of.?bits|sherlock|"
    r"code4?rena|hexens|dedaub|quantstamp|ottersec|halborn|consensys|guardian|"
    r"macro|zellic|pashov|chainsecurity|sigma.?prime|mixbytes|trailofbits",
    re.IGNORECASE,
)


async def audit_branches_ahead(
    owner: str,
    repo: str,
    base_ref: str,
    *,
    client: httpx.AsyncClient | None = None,
    max_checks: int = 12,
) -> list[str]:
    """Names of audit-named branches (`audit/*`, or a known audit-firm name) that
    carry commits NOT in `base_ref`.

    A strong "known-issue minefield" signal: when the Immunefi-scoped branch is
    frozen while fixes are staged on unmerged audit branches, the scoped
    snapshot's strongest bugs are likely already whitehat/audit-firm reported
    (duplicates → excluded). Learned on Parallel Protocol (2026-07): scoped
    `main` was ~4.5mo stale behind six unmerged Bailsec/Cyfrin/whitehat branches.

    One branch-list call plus up to `max_checks` compare calls. Returns [] on any
    error — this is an advisory ranking signal and must never block the delta.
    """
    s = settings()
    try:
        payload: Any = await get_json(
            f"{s.GITHUB_API_BASE}/repos/{owner}/{repo}/branches?per_page=100",
            headers=_auth_headers(),
            client=client,
        )
    except HttpError as exc:
        log.info("github_delta: branches unavailable for %s/%s (%s)", owner, repo, exc)
        return []
    if not isinstance(payload, list):
        return []
    candidates = [
        name
        for b in payload
        if isinstance(b, dict)
        and isinstance((name := b.get("name")), str)
        and name != base_ref
        and _AUDIT_BRANCH_RE.search(name)
    ]
    ahead: list[str] = []
    for name in candidates[:max_checks]:
        cmp_ = await _fetch_compare(owner, repo, base_ref, name, client=client)
        # cmp_[0] is total_commits the branch is ahead of base_ref (base-exclusive).
        if cmp_ is not None and cmp_[0] > 0:
            ahead.append(name)
    return ahead


def _parse_commits(raw: Any) -> list[CommitInfo]:
    out: list[CommitInfo] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if not isinstance(item, dict):
            continue
        sha = item.get("sha")
        commit = item.get("commit")
        if not isinstance(sha, str) or not isinstance(commit, dict):
            continue
        message = commit.get("message")
        author = commit.get("author")
        commit_date = author.get("date") if isinstance(author, dict) else None
        out.append(
            CommitInfo(
                sha=sha,
                message=message if isinstance(message, str) else "",
                date=commit_date if isinstance(commit_date, str) else None,
            )
        )
    return out


# Line prefixes that mark a C-style comment line. Solidity, Rust, and Move all
# use these, so the same heuristic serves every delta-watch target language.
_COMMENT_PREFIXES = ("//", "/*", "*/", "*")


def _is_comment_or_blank(line: str) -> bool:
    s = line.strip()
    return not s or s.startswith(_COMMENT_PREFIXES)


def _count_code_lines(patch: str | None) -> tuple[int | None, int | None]:
    """From a unified-diff `patch`, count added/removed lines that are real code
    (not blank, not a C-style comment). Returns (None, None) when no patch is
    available — the caller treats unknown as code so a real change is never
    dropped. Heuristic: a block-comment body line lacking a leading `*` would
    count as code, which is the safe direction (never under-count code).
    """
    if not patch:
        return None, None
    code_add = code_del = 0
    for line in patch.splitlines():
        if line[:3] in ("+++", "---") or line.startswith("@@"):
            continue
        if line.startswith("+") and not _is_comment_or_blank(line[1:]):
            code_add += 1
        elif line.startswith("-") and not _is_comment_or_blank(line[1:]):
            code_del += 1
    return code_add, code_del


def _parse_files(raw: Any) -> list[ChangedFile]:
    out: list[ChangedFile] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if not isinstance(item, dict):
            continue
        filename = item.get("filename")
        status = item.get("status")
        if not isinstance(filename, str) or not isinstance(status, str):
            continue
        additions = item.get("additions")
        deletions = item.get("deletions")
        patch = item.get("patch")
        code_add, code_del = _count_code_lines(patch if isinstance(patch, str) else None)
        out.append(
            ChangedFile(
                filename=filename,
                status=status,
                additions=additions if isinstance(additions, int) else 0,
                deletions=deletions if isinstance(deletions, int) else 0,
                code_additions=code_add,
                code_deletions=code_del,
            )
        )
    return out


async def _fetch_compare(
    owner: str, repo: str, base: str, head: str, *, client: httpx.AsyncClient | None
) -> tuple[int, list[CommitInfo], list[ChangedFile]] | None:
    """One `GET /compare/{base}...{head}` call → (total_commits, commits, files).

    Returns None on failure (unknown ref, gone repo, rate limit). Commits come
    back oldest→newest, base-exclusive / head-inclusive.
    """
    s = settings()
    url = f"{s.GITHUB_API_BASE}/repos/{owner}/{repo}/compare/{base}...{head}"
    try:
        payload: Any = await get_json(url, headers=_auth_headers(), client=client)
    except HttpError as exc:
        log.info(
            "github_delta: compare %s...%s failed for %s/%s (%s)", base, head, owner, repo, exc
        )
        return None
    if not isinstance(payload, dict):
        return None
    total = payload.get("total_commits")
    return (
        total if isinstance(total, int) else 0,
        _parse_commits(payload.get("commits")),
        _parse_files(payload.get("files")),
    )


def _union_files(file_groups: list[list[ChangedFile]]) -> list[ChangedFile]:
    """Merge changed-file lists from sub-range compares, deduped by filename.

    A file touched in more than one sub-range is kept once with the largest
    observed change size (additions+deletions) — the union over-reports a file's
    churn at worst, never drops a touched file. Code-line counts carry the max
    KNOWN value across occurrences, so a file showing real code in ANY sub-range
    is never mislabeled comment-only by a sub-range where it was comment-only.
    """
    merged: dict[str, ChangedFile] = {}
    code_add: dict[str, int] = {}
    code_del: dict[str, int] = {}
    for group in file_groups:
        for f in group:
            if f.code_additions is not None:
                cur = code_add.get(f.filename)
                code_add[f.filename] = (
                    f.code_additions if cur is None else max(cur, f.code_additions)
                )
            if f.code_deletions is not None:
                cur = code_del.get(f.filename)
                code_del[f.filename] = (
                    f.code_deletions if cur is None else max(cur, f.code_deletions)
                )
            prev = merged.get(f.filename)
            if prev is None or (f.additions + f.deletions) > (prev.additions + prev.deletions):
                merged[f.filename] = f
    for name, f in merged.items():
        if name in code_add:
            f.code_additions = code_add[name]
        if name in code_del:
            f.code_deletions = code_del[name]
    return list(merged.values())


async def _collect_all_files(
    owner: str,
    repo: str,
    base: str,
    head: str,
    commits: list[CommitInfo],
    files: list[ChangedFile],
    *,
    client: httpx.AsyncClient | None,
    budget: dict[str, int],
) -> tuple[list[ChangedFile], bool]:
    """Complete changed-file set for base...head, splitting whenever GitHub caps
    the 300-file list.

    `commits`/`files` are the already-fetched results for THIS range, so the
    first compare is not repeated. Returns (files, still_truncated);
    still_truncated is True only if a sub-range cannot be split further (a single
    commit changing >300 files) or the call budget is exhausted.
    """
    if len(files) < _COMPARE_FILE_CAP:
        return files, False
    if len(commits) < 2:
        return files, True  # one commit changing >300 files — accept the cap
    if budget["calls"] >= _MAX_COMPARE_CALLS:
        log.warning("github_delta: compare-split budget exhausted for %s/%s", owner, repo)
        return files, True
    # Pick a midpoint commit strictly between base and head (never head itself).
    mid = commits[(len(commits) - 1) // 2].sha
    groups: list[list[ChangedFile]] = []
    truncated = False
    for lo, hi in ((base, mid), (mid, head)):
        budget["calls"] += 1
        fetched = await _fetch_compare(owner, repo, lo, hi, client=client)
        if fetched is None:
            truncated = True  # sub-range failed (e.g. rate limit) — partial result
            continue
        _, sub_commits, sub_files = fetched
        collected, sub_trunc = await _collect_all_files(
            owner, repo, lo, hi, sub_commits, sub_files, client=client, budget=budget
        )
        groups.append(collected)
        truncated = truncated or sub_trunc
    return _union_files(groups), truncated


async def compare_commits(
    owner: str,
    repo: str,
    base: str,
    head: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> RepoComparison | None:
    """Compare two refs via `GET /compare/{base}...{head}`.

    Returns a RepoComparison with the commits and changed files between base and
    head, or None if the comparison can't be made (unknown ref, gone repo).
    `base == head` yields a valid result with total_commits=0 and no files.

    When GitHub caps the file list at 300, the commit range is split into
    sub-ranges and their files unioned, so the result reflects the COMPLETE diff
    — not just the alphabetically-first 300 paths. `truncated` then means the
    split could not fully resolve (a single >300-file commit, or budget hit).
    """
    fetched = await _fetch_compare(owner, repo, base, head, client=client)
    if fetched is None:
        return None
    total, commits, files = fetched

    truncated = len(files) >= _COMPARE_FILE_CAP
    if truncated:
        budget = {"calls": 1}
        files, truncated = await _collect_all_files(
            owner, repo, base, head, commits, files, client=client, budget=budget
        )
    return RepoComparison(
        base=base,
        head=head,
        total_commits=total,
        commits=commits,
        files=files,
        truncated=truncated,
    )


async def fetch_delta(
    repo_url: str,
    base: str | None,
    *,
    branch: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> tuple[str, str, RepoComparison | None] | None:
    """High-level: resolve a repo's watched-branch HEAD and compare it to `base`.

    `branch` overrides the watched ref — needed for protocols that develop on a
    release/version branch (e.g. marginfi's `0.1.9-main`) rather than the default
    branch. When None, the repo's default branch is used.

    Returns `(watched_branch, head_sha, comparison)`:
      - comparison is None when base is None (first run — caller records the
        head as the new baseline with no delta) or base == head (no change).
      - Returns None entirely if the repo URL is unparseable, the repo is gone,
        or the requested branch doesn't resolve.
    """
    parsed = parse_github_url(repo_url)
    if not parsed:
        return None
    owner, repo = parsed

    watched_branch = branch or await get_default_branch(owner, repo, client=client)
    if watched_branch is None:
        return None
    head_sha = await get_head_sha(owner, repo, watched_branch, client=client)
    if head_sha is None:
        return None

    if base is None or base == head_sha:
        return watched_branch, head_sha, None

    comparison = await compare_commits(owner, repo, base, head_sha, client=client)
    return watched_branch, head_sha, comparison
