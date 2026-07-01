"""GitHub repository metadata enrichment.

Given a repo URL (from DefiLlama or heuristic discovery), query the GitHub
REST API for:
    - exists (is the repo still alive?)
    - default branch
    - languages + byte counts (proxy for LOC estimate)
    - whether an `audits/` folder exists at the repo root (signal for Stage 3)

Uses the fine-grained PAT stored in `pass` under `tvl-scanner/github`.
Rate limit with authenticated requests: 5000/hour, well above our scanner's
needs (a few hundred per run).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

import httpx

from tvl_scanner.config import get_secret, settings
from tvl_scanner.http import HttpError, get_json

log = logging.getLogger(__name__)


# Match github.com owner/repo from any URL form, including trailing /tree/main etc.
_GH_URL = re.compile(
    r"github\.com[:/]([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?(?:/.*)?$"
)


# Byte-per-LOC heuristic per language. Rough averages; only used for relative
# sizing of audit scope so exact accuracy is unimportant.
_BYTES_PER_LOC = {
    "Solidity": 30,
    "Rust": 28,
    "Move": 30,
    "Cairo": 30,
    "Vyper": 32,
    "TypeScript": 30,
    "JavaScript": 30,
}


@dataclass
class RepoMetadata:
    """Structured result from GitHub enrichment."""

    owner: str
    repo: str
    url: str
    exists: bool
    default_branch: str | None = None
    loc_estimate: int | None = None
    audits_folder_exists: bool = False
    audit_report_count: int = 0  # report artifacts in audits/ + docs/audits/ (saturation signal)
    languages: dict[str, int] | None = None


def parse_github_url(url: str | None) -> tuple[str, str] | None:
    """Extract (owner, repo) from a GitHub URL. Returns None if not parseable."""
    if not url:
        return None
    match = _GH_URL.search(url)
    if not match:
        return None
    return match.group(1), match.group(2)


def _auth_headers() -> dict[str, str]:
    token = get_secret("github", required=False)
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _estimate_loc(languages: dict[str, int]) -> int:
    """Convert language byte counts to an approximate total LOC.

    Only counts languages that smart-contract auditors care about. Ignores
    JS/TS deployment scripts, Python tooling, Solidity test files (we can't
    tell them apart from contracts via the languages endpoint alone).
    """
    total = 0
    for lang, byte_count in languages.items():
        per_loc = _BYTES_PER_LOC.get(lang)
        if per_loc:
            total += int(byte_count / per_loc)
    return total


_ORG_SUFFIX_VARIANTS = (
    "",            # bare slug ("bima-cdp" → github.com/bima-cdp)
    "-protocol",   # bima-protocol
    "-dao",        # bima-dao
    "-finance",    # bima-finance
    "-money",      # bima-money
    "-labs",       # bima-labs
)

_ORG_NEGATIVE_CACHE: set[str] = set()  # org names confirmed not-found / empty
_ORG_POSITIVE_CACHE: dict[str, str] = {}  # slug → resolved repo URL

# Circuit breaker: if rate-limit / transport errors exceed this count during a
# single scan, stop calling find_org_with_repos for the rest of the run. Avoids
# burning the rest of the per-protocol budget on calls that all return 429.
_RATE_LIMIT_ERRORS = 0
_RATE_LIMIT_BUDGET = 5


def _is_rate_limit_error(exc: HttpError) -> bool:
    """Detect rate-limit (429) and forbidden (403) responses from GitHub.

    The 403 case matters because GitHub returns 403 with a rate-limit
    message body, not 429, when an authenticated client exceeds its
    secondary rate limit. Both must be treated as transient — NOT cached
    as 'org does not exist'.
    """
    msg = str(exc).lower()
    return "429" in msg or "rate limited" in msg or "rate limit exceeded" in msg


def _generate_org_candidates(slug: str, display_name: str | None) -> list[str]:
    """Produce a deduped list of GitHub org-name guesses for a protocol slug.

    Strategy: tries the slug as-is, then the slug's first token, each with
    common suffix variants. Also adds the slug-with-dashes-removed for
    protocols like 'rocketpool' (org name) vs 'rocket-pool' (slug).
    """
    if not slug:
        return []
    seen: set[str] = set()
    out: list[str] = []

    def add(name: str) -> None:
        n = name.strip().lower()
        if n and n not in seen and n.isascii() and not n.startswith("-"):
            seen.add(n)
            out.append(n)

    s = slug.strip().lower()
    first_token = s.split("-")[0]

    for base in (s, first_token, s.replace("-", "")):
        for suffix in _ORG_SUFFIX_VARIANTS:
            add(base + suffix)

    # Display-name slug variants (e.g. "BIMA CDP" → "bimacdp")
    if display_name:
        dn = re.sub(r"[^a-z0-9]+", "", display_name.lower())
        if dn:
            for suffix in _ORG_SUFFIX_VARIANTS:
                add(dn + suffix)

    return out[:4]  # bound API cost — top variants only ({slug}, {first}, {slug}-protocol, {first}-protocol)


async def find_org_with_repos(
    slug: str | None,
    display_name: str | None = None,
    *,
    client: httpx.AsyncClient | None = None,
) -> str | None:
    """Try GitHub org-name variants for a protocol slug.

    Returns a `https://github.com/{org}/{repo}` URL for the first org that
    BOTH exists AND has at least one public repo with a smart-contract
    language (Solidity/Rust/Move/Cairo/Vyper). Returns None otherwise.

    Rejects empty orgs (G3): an org with public_repos=0 is closed-source
    and equivalent to no GitHub presence for audit purposes. BIMA's
    bima-protocol org is the canonical example — exists but has 0 repos.

    Uses process-level caches to avoid duplicate API calls within a scan.
    """
    if not slug:
        return None
    cache_key = slug.strip().lower()
    if cache_key in _ORG_POSITIVE_CACHE:
        return _ORG_POSITIVE_CACHE[cache_key]

    # Circuit breaker: if we've hit too many rate-limit errors this scan,
    # don't waste the rest of the GitHub API budget on G2 calls. Auth may
    # be broken (e.g. GPG cache expired) — surface the gap once and move on.
    global _RATE_LIMIT_ERRORS
    if _RATE_LIMIT_ERRORS >= _RATE_LIMIT_BUDGET:
        return None

    s = settings()
    headers = _auth_headers()
    if "Authorization" not in headers:
        log.warning(
            "github: find_org_with_repos called without auth header — "
            "G2 will exhaust unauth (60/hr) limit quickly. Prime `pass show "
            "tvl-scanner/github` to restore GPG cache."
        )

    for org_name in _generate_org_candidates(slug, display_name):
        if org_name in _ORG_NEGATIVE_CACHE:
            continue

        # G3 step 1: does the org exist + have public repos?
        try:
            org_info: Any = await get_json(
                f"{s.GITHUB_API_BASE}/users/{org_name}",
                headers=headers,
                client=client,
            )
        except HttpError as exc:
            if _is_rate_limit_error(exc):
                _RATE_LIMIT_ERRORS += 1
                # Transient — do NOT cache as confirmed-not-found
                if _RATE_LIMIT_ERRORS >= _RATE_LIMIT_BUDGET:
                    log.warning(
                        "github: G2 circuit-breaker tripped after %d rate-limit "
                        "errors. Disabling find_org_with_repos for the rest of "
                        "this scan.",
                        _RATE_LIMIT_ERRORS,
                    )
                return None
            _ORG_NEGATIVE_CACHE.add(org_name)
            continue

        if not isinstance(org_info, dict):
            _ORG_NEGATIVE_CACHE.add(org_name)
            continue

        public_repos = org_info.get("public_repos", 0)
        if not isinstance(public_repos, int) or public_repos == 0:
            _ORG_NEGATIVE_CACHE.add(org_name)
            log.debug("github: org %s exists but has 0 public repos (G3 reject)", org_name)
            continue

        # G2 step 2: list repos, pick the first with a smart-contract language
        try:
            repos_payload: Any = await get_json(
                f"{s.GITHUB_API_BASE}/users/{org_name}/repos?sort=updated&per_page=20",
                headers=headers,
                client=client,
            )
        except HttpError as exc:
            if _is_rate_limit_error(exc):
                _RATE_LIMIT_ERRORS += 1
                return None
            _ORG_NEGATIVE_CACHE.add(org_name)
            continue

        if not isinstance(repos_payload, list):
            continue

        contract_langs = set(_BYTES_PER_LOC.keys()) - {"TypeScript", "JavaScript"}
        for repo in repos_payload:
            if not isinstance(repo, dict):
                continue
            if repo.get("fork") or repo.get("archived"):
                continue
            lang = repo.get("language")
            if isinstance(lang, str) and lang in contract_langs:
                url = repo.get("html_url")
                if isinstance(url, str):
                    _ORG_POSITIVE_CACHE[cache_key] = url
                    log.info(
                        "github: discovered %s via org-name guess (slug=%s)",
                        url,
                        slug,
                    )
                    return url

        # Org has repos but none look like smart-contract code
        _ORG_NEGATIVE_CACHE.add(org_name)

    return None


# Filenames that denote an audit report (firm name or "audit"/"report").
_AUDIT_REPORT_RE = re.compile(
    r"audit|report|bailsec|cyfrin|certora|zenith|spearbit|trail.?of.?bits|sherlock|"
    r"code4?rena|hexens|dedaub|quantstamp|ottersec|halborn|consensys|guardian|macro|"
    r"zellic|pashov|chainsecurity|sigma.?prime|mixbytes",
    re.IGNORECASE,
)


def _count_audit_reports(entries: Any) -> int:
    """Count audit-report artifacts in a GitHub `/contents` listing: report files
    (.pdf/.md whose name names a firm or says audit/report) plus subdirectories
    (each is usually a version/round, e.g. v3, v3.1). No recursion — bounded.

    Counting (vs binary presence) lets a multiply-audited repo (Bailsec x3 +
    Certora + Zenith) read as saturated instead of scoring like a single audit.
    """
    if not isinstance(entries, list):
        return 0
    n = 0
    for e in entries:
        if not isinstance(e, dict):
            continue
        name = e.get("name")
        if not isinstance(name, str):
            continue
        if e.get("type") == "dir" or (name.lower().endswith((".pdf", ".md")) and _AUDIT_REPORT_RE.search(name)):
            n += 1
    return n


async def enrich_repo(
    url: str | None, *, client: httpx.AsyncClient | None = None
) -> RepoMetadata | None:
    """Query GitHub for repo metadata. Returns None if the URL is unparseable.

    On HTTP errors for the main `/repos/{owner}/{repo}` call, returns a
    RepoMetadata with `exists=False`. Side-call failures (languages, audits
    folder) are swallowed — they shouldn't prevent the main record from being
    returned.
    """
    parsed = parse_github_url(url)
    if not parsed:
        return None
    owner, repo = parsed
    s = settings()
    base = f"{s.GITHUB_API_BASE}/repos/{owner}/{repo}"
    headers = _auth_headers()

    # Main repo lookup
    try:
        main: Any = await get_json(base, headers=headers, client=client)
    except HttpError as exc:
        log.info("github: repo %s/%s not accessible (%s)", owner, repo, exc)
        return RepoMetadata(owner=owner, repo=repo, url=url or "", exists=False)

    if not isinstance(main, dict):
        return RepoMetadata(owner=owner, repo=repo, url=url or "", exists=False)

    default_branch = main.get("default_branch")

    # Languages side-call
    languages: dict[str, int] | None = None
    loc_estimate: int | None = None
    try:
        langs_payload: Any = await get_json(
            f"{base}/languages", headers=headers, client=client
        )
        if isinstance(langs_payload, dict):
            languages = {k: int(v) for k, v in langs_payload.items()}
            loc_estimate = _estimate_loc(languages)
    except Exception as exc:
        log.debug("github: languages fetch failed for %s/%s: %s", owner, repo, exc)

    # Audit reports — count artifacts across the two common locations. A 404 is
    # a normal outcome (no audits folder there), NOT an error.
    audit_report_count = 0
    for folder in ("audits", "docs/audits"):
        try:
            audits_payload: Any = await get_json(
                f"{base}/contents/{folder}", headers=headers, client=client
            )
        except HttpError:
            continue
        except Exception as exc:
            log.debug(
                "github: audits folder %s check failed for %s/%s: %s", folder, owner, repo, exc
            )
            continue
        audit_report_count += _count_audit_reports(audits_payload)
    audits_folder_exists = audit_report_count > 0

    return RepoMetadata(
        owner=owner,
        repo=repo,
        url=main.get("html_url") or url or f"https://github.com/{owner}/{repo}",
        exists=True,
        default_branch=default_branch,
        loc_estimate=loc_estimate,
        audits_folder_exists=audits_folder_exists,
        audit_report_count=audit_report_count,
        languages=languages,
    )
