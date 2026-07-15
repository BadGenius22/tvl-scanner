"""Contest-platform audit history via GitHub search.

Instead of scraping code4rena.com, sherlock.xyz, and cantina.xyz HTML (fragile,
rate-limited, anti-bot), we query the GitHub search API for repositories in
the three canonical audit-org accounts:

    code-423n4   → Code4rena  (every C4 contest is a repo, e.g. 2024-01-salty)
    sherlock-audit → Sherlock  (every Sherlock audit is a repo)
    spearbit     → Cantina/Spearbit (public portfolio of audit reports)

GitHub repository search endpoint:
    GET /search/repositories?q=<query>+org:<org>

Authenticated rate limit is 30 requests/minute for search endpoints, which is
well within our budget (3 searches × ~50 candidates = 150/run).

A hit in any of these orgs = strong audit history signal. Weight: 3 points per
hit (per the plan), since contests are the highest-quality audit signal.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass

import httpx

from tvl_scanner.config import get_secret, settings
from tvl_scanner.http import HttpError, get_json
from tvl_scanner.models import AuditSource, AuditSourceKind

log = logging.getLogger(__name__)


AUDIT_ORGS: dict[AuditSourceKind, str] = {
    AuditSourceKind.CODE4RENA: "code-423n4",
    AuditSourceKind.SHERLOCK: "sherlock-audit",
    AuditSourceKind.CANTINA: "spearbit",
}


_CLEAN_NAME = re.compile(r"[^A-Za-z0-9]+")


def _normalize_query(name: str) -> str:
    """Strip version suffixes, spaces, and punctuation to get a searchable token.

    Uses the FIRST meaningful token — the brand name usually comes first, and
    trailing words like "Finance", "Protocol", "Labs" are too common to be
    discriminating search terms.

    Examples:
        "Camelot V3"     → "camelot"
        "Factor Finance" → "factor"
        "uniswap-v3"     → "uniswap"
    """
    tokens = _CLEAN_NAME.split(name.strip().lower())
    # Drop empties and version-only tokens ("v3", "v2", etc.)
    tokens = [t for t in tokens if t and not re.fullmatch(r"v\d+", t)]
    # Drop single-letter tokens ("a", "b")
    tokens = [t for t in tokens if len(t) >= 2]
    if not tokens:
        return ""
    return tokens[0]


def _auth_headers() -> dict[str, str]:
    token = get_secret("github", required=False)
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


@dataclass
class ContestHit:
    kind: AuditSourceKind
    repo_full_name: str
    html_url: str


async def search_org(
    query_token: str,
    kind: AuditSourceKind,
    *,
    client: httpx.AsyncClient | None = None,
) -> list[ContestHit]:
    """Search one audit org's repos for the given query token.

    Returns at most 10 hits — more than that and the match is suspiciously vague.
    """
    if not query_token or len(query_token) < 3:
        return []
    s = settings()
    org = AUDIT_ORGS[kind]
    params = {
        "q": f"{query_token} in:name org:{org}",
        "per_page": 10,
    }
    url = f"{s.GITHUB_API_BASE}/search/repositories"

    try:
        payload = await get_json(
            url, params=params, headers=_auth_headers(), client=client
        )
    except HttpError as exc:
        log.info("contest search failed for %s/%s: %s", org, query_token, exc)
        return []

    items = payload.get("items", []) if isinstance(payload, dict) else []
    hits: list[ContestHit] = []
    for item in items:
        full = item.get("full_name")
        html = item.get("html_url")
        if full and html:
            hits.append(
                ContestHit(kind=kind, repo_full_name=str(full), html_url=str(html))
            )
    return hits


async def check_all_contests(
    display_name: str,
    *,
    defillama_slug: str | None = None,
    client: httpx.AsyncClient | None = None,
    token_cache: dict[tuple[str, AuditSourceKind], list[ContestHit]] | None = None,
) -> list[AuditSource]:
    """Search all three contest orgs for audit history matching this protocol.

    Tries multiple query tokens (display name, defillama slug) and merges hits
    by repo full_name to avoid double-counting.

    BATCH G FIX #3: takes an optional `token_cache` shared across all candidates
    in a scan. GitHub's search API has a 30-req-per-minute rate limit per
    authenticated user (SEPARATE from the 5000/hr core API limit). With ~150
    candidates × 3 orgs = 450 calls we saturate the per-minute bucket mid-scan
    and get 403 for the remainder. Caching by (token, org) means that
    protocols sharing a brand name (e.g., "aave", "aave-v2", "aave-v3" all
    normalize to "aave") only cost one HTTP round-trip total.
    """
    tokens: set[str] = set()
    primary = _normalize_query(display_name)
    if primary:
        tokens.add(primary)
    if defillama_slug:
        secondary = _normalize_query(defillama_slug)
        if secondary:
            tokens.add(secondary)
    if not tokens:
        return []

    # For each (token, org) pair, look up in cache or spawn a search task.
    all_hits: list[list[ContestHit]] = []
    task_keys: list[tuple[str, AuditSourceKind]] = []
    tasks: list[asyncio.Task[list[ContestHit]]] = []

    for token in tokens:
        for kind in AUDIT_ORGS:
            key = (token, kind)
            if token_cache is not None and key in token_cache:
                all_hits.append(token_cache[key])
            else:
                task_keys.append(key)
                tasks.append(asyncio.create_task(search_org(token, kind, client=client)))

    if tasks:
        task_results = await asyncio.gather(*tasks, return_exceptions=True)
        for key, result in zip(task_keys, task_results, strict=True):
            if isinstance(result, BaseException):
                hits: list[ContestHit] = []
            else:
                hits = result
            if token_cache is not None:
                token_cache[key] = hits
            all_hits.append(hits)

    seen_repos: set[str] = set()
    results: list[AuditSource] = []
    for hits in all_hits:
        for hit in hits:
            if hit.repo_full_name in seen_repos:
                continue
            seen_repos.add(hit.repo_full_name)
            results.append(
                AuditSource(
                    source=hit.kind,
                    url=hit.html_url,
                    title=hit.repo_full_name,
                    weight=3,
                )
            )
    return results
