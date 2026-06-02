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
from dataclasses import dataclass, field
from typing import Any

import httpx

from tvl_scanner.config import settings
from tvl_scanner.enrich.github import _auth_headers, parse_github_url
from tvl_scanner.http import HttpError, get_json

log = logging.getLogger(__name__)

# GitHub caps the compare endpoint's file list at 300 entries.
_COMPARE_FILE_CAP = 300


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
        out.append(
            ChangedFile(
                filename=filename,
                status=status,
                additions=additions if isinstance(additions, int) else 0,
                deletions=deletions if isinstance(deletions, int) else 0,
            )
        )
    return out


async def compare_commits(
    owner: str,
    repo: str,
    base: str,
    head: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> RepoComparison | None:
    """Compare two refs via `GET /compare/{base}...{head}`.

    Returns a RepoComparison with the commits and changed files between base
    and head, or None if the comparison can't be made (unknown ref, gone repo).
    `base == head` yields a valid result with total_commits=0 and no files.
    """
    s = settings()
    url = f"{s.GITHUB_API_BASE}/repos/{owner}/{repo}/compare/{base}...{head}"
    try:
        payload: Any = await get_json(url, headers=_auth_headers(), client=client)
    except HttpError as exc:
        log.info(
            "github_delta: compare %s...%s failed for %s/%s (%s)",
            base,
            head,
            owner,
            repo,
            exc,
        )
        return None
    if not isinstance(payload, dict):
        return None

    total = payload.get("total_commits")
    files = _parse_files(payload.get("files"))
    return RepoComparison(
        base=base,
        head=head,
        total_commits=total if isinstance(total, int) else 0,
        commits=_parse_commits(payload.get("commits")),
        files=files,
        truncated=len(files) >= _COMPARE_FILE_CAP,
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
