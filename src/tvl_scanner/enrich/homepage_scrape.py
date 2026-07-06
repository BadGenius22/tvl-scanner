"""Protocol homepage HTML regex extraction (Batch K).

For top-N candidates after ranking, fetch the protocol's homepage URL
(DefiLlama provides it as `url` in the detail endpoint or flat catalog)
and run regex extraction over the rendered HTML for two classes of
signal:

1. **Wrapper / fork phrases** — explicit architectural claims like
   "uses the SPL native stake pool program", "fork of Aave", "based on
   Uniswap V3". When matched, the candidate is a wrapper of an audited
   protocol and should be demoted.

2. **Audit firm mentions** — phrases like "audited by Trail of Bits",
   "Halborn", "Zellic", etc. These catch protocols whose audit history
   is hosted on their own website rather than indexed by DefiLlama or
   github contest orgs. This is exactly the gap that hides Hyperlane-
   class protocols from the rest of our scanner.

Cost: one HTTPS fetch per top-N candidate. Default N=30 (top of report).
~30 fetches per scan, ~5-10 seconds added to scan time.

Failure mode: if the homepage doesn't load, returns empty results.
Never raises.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx

log = logging.getLogger(__name__)


WRAPPER_PHRASES: dict[re.Pattern[str], str] = {
    re.compile(r"native stake pool program", re.I): "spl_stake_pool",
    re.compile(r"spl[- ]?stake[- ]?pool", re.I): "spl_stake_pool",
    re.compile(r"fork of (?:the )?aave", re.I): "aave_fork",
    re.compile(r"based on aave", re.I): "aave_fork",
    re.compile(r"fork of (?:the )?compound", re.I): "compound_fork",
    re.compile(r"based on compound", re.I): "compound_fork",
    re.compile(r"built on uniswap[- ]v?[34]", re.I): "uniswap_v3_fork",
    re.compile(r"fork of uniswap[- ]v?[234]", re.I): "uniswap_fork",
    re.compile(r"based on (?:the )?morpho", re.I): "morpho_layer",
    re.compile(r"fork of (?:the )?gmx", re.I): "gmx_fork",
    re.compile(r"based on (?:the )?balancer", re.I): "balancer_fork",
}


# Audit firm name detection. Two-stage: page must first contain SOME audit
# context word (`audit`, `audited`, `security review`, `assessment`), then
# we look for known firm names anywhere on the page. The two-stage approach
# correctly handles forms like "audited by Trail of Bits, Halborn, and
# Zellic" where the firm names aren't all preceded by "audited by".
#
# Risk of false positive on bare firm names is minimal — these names are
# uncommon outside audit context (Halborn, Zellic, Spearbit, etc.).

AUDIT_CONTEXT_PATTERN = re.compile(
    r"\b(audit|audited|security review|security assessment|reviewed by)\b", re.I
)

# GitHub URL extraction — pulled from page HTML when DefiLlama and the
# curated registry both fail to provide a repo. Owners listed in
# _GITHUB_OWNER_DENYLIST are ignored because their links almost never
# represent the candidate's own source code (they're nav UI, common
# dependency repos, or unrelated). Repo names in _GITHUB_REPO_DENYLIST
# are likewise ignored even if the owner looks plausible.
_GITHUB_URL_PATTERN = re.compile(
    r"https?://github\.com/([A-Za-z0-9][A-Za-z0-9_.-]*)/([A-Za-z0-9][A-Za-z0-9_.-]*?)"
    r"(?:\.git)?(?=[/\"'?#)\s<]|$)",
    re.I,
)
_GITHUB_OWNER_DENYLIST: frozenset[str] = frozenset({
    "sponsors", "orgs", "login", "marketplace", "codespaces", "features",
    "pricing", "topics", "trending", "collections", "events", "about",
    "site", "github", "explore", "settings", "notifications", "issues",
    "pulls", "discussions", "search",
    # Common dependency owners that appear in protocol homepages but
    # almost certainly aren't the candidate's own code:
    "openzeppelin", "ethereum", "aave", "uniswap", "compound-finance",
    "transmissions11", "smartcontractkit", "trufflesuite", "foundry-rs",
    "nomicfoundation",
})
_GITHUB_REPO_DENYLIST: frozenset[str] = frozenset({
    "openzeppelin-contracts", "openzeppelin-contracts-upgradeable",
    "solidity", "go-ethereum", "hardhat", "foundry", "forge-std",
    # Non-code repos that protocol homepages frequently link to. We never
    # want these stored as a candidate's `github_repo` because they don't
    # contain auditable smart-contract source. Even when one of these is
    # the ONLY GitHub link on a page (e.g. SYMM-IO/docs), it's better to
    # leave github_repo null than mislead downstream consumers.
    "docs", "documentation", "website", "site", "homepage", "landing",
    "blog", "marketing", "frontend", "ui", "brand", "press-kit",
})


AUDIT_FIRM_PHRASES: dict[re.Pattern[str], str] = {
    re.compile(r"\btrail of bits\b", re.I): "trail_of_bits",
    re.compile(r"\bhalborn\b", re.I): "halborn",
    re.compile(r"\bzellic\b", re.I): "zellic",
    re.compile(r"\bzokyo\b", re.I): "zokyo",
    re.compile(r"\boxor\b", re.I): "oxor",
    re.compile(r"\bottersec\b", re.I): "ottersec",
    re.compile(r"\bchainsecurity\b", re.I): "chain_security",
    re.compile(r"\bopenzeppelin\b", re.I): "openzeppelin",
    re.compile(r"\bcyfrin\b", re.I): "cyfrin",
    re.compile(r"\bhexens\b", re.I): "hexens",
    re.compile(r"\bspearbit\b", re.I): "spearbit",
    re.compile(r"\bcantina\b", re.I): "cantina",
    re.compile(r"\bquantstamp\b", re.I): "quantstamp",
    re.compile(r"\bcertik\b", re.I): "certik",
    re.compile(r"\bsigma prime\b", re.I): "sigma_prime",
    re.compile(r"\bpeckshield\b", re.I): "peckshield",
    re.compile(r"\bslowmist\b", re.I): "slowmist",
    re.compile(r"\bconsensys diligence\b", re.I): "consensys_diligence",
    re.compile(r"\bmacro\b", re.I): "macro",
    re.compile(r"\bcode4rena\b", re.I): "code4rena",
    re.compile(r"\bsherlock\b", re.I): "sherlock",
    # Added 2026-05-26 after rho-x-lp-vault false positive — these firms
    # cover most contemporary DeFi audits absent from the original list.
    re.compile(r"\bhacken\b", re.I): "hacken",
    re.compile(r"\bveridise\b", re.I): "veridise",
    re.compile(r"\bpashov\b", re.I): "pashov",
    re.compile(r"\bdedaub\b", re.I): "dedaub",
    re.compile(r"\backee blockchain\b", re.I): "ackee",
    re.compile(r"\bruntime verification\b", re.I): "runtime_verification",
    re.compile(r"\babdk\b", re.I): "abdk",
    re.compile(r"\bmixbytes\b", re.I): "mixbytes",
    re.compile(r"\bbeosin\b", re.I): "beosin",
    re.compile(r"\bquill audits\b", re.I): "quill_audits",
    re.compile(r"\bsolidified\b", re.I): "solidified",
    re.compile(r"\bstatemind\b", re.I): "statemind",
    re.compile(r"\bpessimistic\b", re.I): "pessimistic",
    re.compile(r"\bnethermind\b", re.I): "nethermind",
    re.compile(r"\bsec3\b", re.I): "sec3",
    re.compile(r"\bkudelski\b", re.I): "kudelski",
    re.compile(r"\btrust security\b", re.I): "trust_security",
    re.compile(r"\bthree sigma\b", re.I): "three_sigma",
    re.compile(r"\bimmunebytes\b", re.I): "immunebytes",
    re.compile(r"\bsalus\b", re.I): "salus",
}


# Audit-firm URL fingerprints. Some homepages embed the audit firm via
# <img> logos and direct links to the audit artifact, with the firm name
# appearing only inside the URL (not as plaintext on the page). The
# Wayback/SPA case is the most common: the page renders the audit logos
# but the literal firm name lives inside the href, not in body text.
# Example (rho.trading homepage on 2026-05-26):
#     <a href="https://www.halborn.com/audits/rho-labs/vault-contracts-v2-9d7cbb">
#     <a href="https://github.com/zokyo-sec/audit-reports/...">
#     <a href="https://audits.oxor.io/reports/...">
# When the regular AUDIT_FIRM_PHRASES regex misses (because the SPA's
# server-rendered HTML carries the link but no firm-name text), these
# patterns catch the linked URL itself. Match is on substring; the URL
# domain or path embeds the firm's brand and is unambiguous evidence
# of an audit citation.
AUDIT_FIRM_URL_PATTERNS: dict[re.Pattern[str], str] = {
    re.compile(r"https?://(?:www\.)?halborn\.com/audits/", re.I): "halborn",
    re.compile(r"https?://github\.com/zokyo-sec/", re.I): "zokyo",
    re.compile(r"https?://(?:www\.)?zokyo\.io/", re.I): "zokyo",
    re.compile(r"https?://audits\.oxor\.io/", re.I): "oxor",
    re.compile(r"https?://(?:www\.)?osec\.io/", re.I): "ottersec",
    re.compile(r"https?://github\.com/(?:ackee-blockchain|ackeeblockchain)/", re.I): "ackee",
    re.compile(r"https?://github\.com/trailofbits/publications", re.I): "trail_of_bits",
    re.compile(r"https?://(?:www\.)?certik\.com/projects/", re.I): "certik",
    re.compile(r"https?://(?:www\.)?openzeppelin\.com/security-audits/", re.I): "openzeppelin",
    re.compile(r"https?://code4rena\.com/(?:reports|audits|contests)/", re.I): "code4rena",
    re.compile(r"https?://(?:www\.)?sherlock\.xyz/audits/", re.I): "sherlock",
    re.compile(r"https?://(?:www\.)?cantina\.xyz/(?:competitions|portfolio)/", re.I): "cantina",
    re.compile(r"https?://(?:www\.)?spearbit\.com/", re.I): "spearbit",
    re.compile(r"https?://(?:www\.)?quantstamp\.com/audits/", re.I): "quantstamp",
    re.compile(r"https?://github\.com/pashov-audit-group/", re.I): "pashov",
    re.compile(r"https?://(?:www\.)?hacken\.io/audits/", re.I): "hacken",
    re.compile(r"https?://(?:www\.)?veridise\.com/audits-archive/", re.I): "veridise",
    re.compile(r"https?://github\.com/runtimeverification/", re.I): "runtime_verification",
}


@dataclass(frozen=True)
class HomepageScrapeResult:
    """Structured output of a homepage scrape."""

    url: str
    fetched: bool
    wrapper_matches: list[str]   # tags from WRAPPER_PHRASES values
    audit_firm_matches: list[str]  # tags from AUDIT_FIRM_PHRASES values
    github_urls: list[str]  # github.com/owner/repo URLs found in page HTML


_EMPTY = HomepageScrapeResult(
    url="", fetched=False, wrapper_matches=[], audit_firm_matches=[], github_urls=[]
)


def _extract_github_urls(html: str) -> list[str]:
    """Pull github.com/<owner>/<repo> URLs from page HTML, filtered + deduped.

    Order is preserved by first appearance. Capped at 10 candidates so a
    blog/docs page with dozens of code links doesn't blow up the caller's
    GitHub API budget.
    """
    seen: set[tuple[str, str]] = set()
    out: list[str] = []
    for match in _GITHUB_URL_PATTERN.finditer(html):
        owner = match.group(1).strip(".")
        repo = match.group(2).strip(".")
        if not owner or not repo:
            continue
        owner_lower = owner.lower()
        repo_lower = repo.lower()
        if owner_lower in _GITHUB_OWNER_DENYLIST:
            continue
        if repo_lower in _GITHUB_REPO_DENYLIST:
            continue
        key = (owner_lower, repo_lower)
        if key in seen:
            continue
        seen.add(key)
        out.append(f"https://github.com/{owner}/{repo}")
        if len(out) >= 10:
            break
    return out


async def _fetch_and_extract(
    url: str | None, *, client: httpx.AsyncClient | None = None
) -> tuple[HomepageScrapeResult, str]:
    """Internal: fetch + regex extraction, returns (result, html_sample).

    The html_sample is exposed so callers (specifically the Phase 3 link-crawl
    in scrape_homepage_with_fallback) can re-mine the page for audit-relevant
    anchor tags without a second fetch. Returns ("", "") on any failure.
    """
    if not url or not isinstance(url, str) or not url.startswith(("http://", "https://")):
        return _EMPTY, ""

    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; tvl-scanner/0.5)",
                "Accept": "text/html,application/xhtml+xml",
            },
        )
    assert client is not None

    # ALWAYS follow redirects and send browser-ish headers on the request,
    # regardless of whether we own the client. The scanner pipeline passes
    # a shared client from `make_client()` which does NOT set
    # follow_redirects=True (httpx defaults to False), and many protocol
    # homepages 301-redirect (e.g. www.rho.trading → rho.trading). Without
    # this, the scraper sees a redirect body containing no audit text and
    # silently classifies an audited protocol as under-audited. Per-request
    # kwargs override the client defaults; safe to apply unconditionally.
    request_headers = {
        "User-Agent": "Mozilla/5.0 (compatible; tvl-scanner/0.5)",
        "Accept": "text/html,application/xhtml+xml",
    }

    try:
        response = await client.get(url, follow_redirects=True, headers=request_headers)
        if response.status_code >= 400:
            return (
                HomepageScrapeResult(
                    url=url,
                    fetched=False,
                    wrapper_matches=[],
                    audit_firm_matches=[],
                    github_urls=[],
                ),
                "",
            )
        html = response.text
    except (httpx.HTTPError, ValueError) as exc:
        log.debug("homepage scrape failed for %s: %s", url, exc)
        return (
            HomepageScrapeResult(
                url=url,
                fetched=False,
                wrapper_matches=[],
                audit_firm_matches=[],
                github_urls=[],
            ),
            "",
        )
    finally:
        if owns_client:
            await client.aclose()

    # Many modern sites are SPAs and the body has minimal text. We still
    # check meta tags and any inline content. Cap input at 400KB — the
    # original 200KB cap missed rho.trading's audits section (firms appeared
    # at byte ~118K in a 204KB page; close, but 400KB gives meaningful
    # headroom for modern SPA bundles). All patterns are `\b<literal>\b`
    # form so they run in linear time regardless of input size — the cap is
    # purely a memory bound, not a ReDoS guard.
    sample = html[:400_000]

    wrapper_hits: set[str] = set()
    for pattern, tag in WRAPPER_PHRASES.items():
        if pattern.search(sample):
            wrapper_hits.add(tag)

    # Audit firms via two paths:
    #   1. Plaintext firm name regex — gated by AUDIT_CONTEXT_PATTERN to
    #      avoid false positives where a firm name appears on a partner page.
    #   2. URL fingerprint regex — direct links to the audit artifact
    #      (e.g. halborn.com/audits/<proto>, audits.oxor.io/reports/<id>).
    #      Match is unambiguous on its own, no context gate needed —
    #      a homepage linking to its own audit page is direct evidence.
    audit_hits: set[str] = set()
    if AUDIT_CONTEXT_PATTERN.search(sample):
        for pattern, tag in AUDIT_FIRM_PHRASES.items():
            if pattern.search(sample):
                audit_hits.add(tag)
    for url_pattern, tag in AUDIT_FIRM_URL_PATTERNS.items():
        if url_pattern.search(sample):
            audit_hits.add(tag)

    github_urls = _extract_github_urls(sample)

    return (
        HomepageScrapeResult(
            url=url,
            fetched=True,
            wrapper_matches=sorted(wrapper_hits),
            audit_firm_matches=sorted(audit_hits),
            github_urls=github_urls,
        ),
        sample,
    )


async def scrape_homepage(
    url: str | None, *, client: httpx.AsyncClient | None = None
) -> HomepageScrapeResult:
    """Fetch `url` and run regex extraction. Returns empty result on any failure."""
    result, _html = await _fetch_and_extract(url, client=client)
    return result


def rank_github_urls_for_protocol(
    urls: list[str], *, slug: str | None = None, display_name: str | None = None
) -> list[str]:
    """Rank scraped GitHub URLs by relevance to a known protocol identity.

    Higher score when owner or repo name shares a token with the slug or
    a slugified version of display_name. Used as a tie-breaker before
    calling enrich_repo() — saves GitHub API calls by trying the most
    likely match first.
    """
    tokens: set[str] = set()
    if slug:
        for t in re.split(r"[^a-z0-9]+", slug.lower()):
            if len(t) >= 3 and t not in _DISPLAY_NAME_SUFFIXES:
                tokens.add(t)
    if display_name:
        for t in re.split(r"[^a-z0-9]+", display_name.lower()):
            if len(t) >= 3 and t not in _DISPLAY_NAME_SUFFIXES:
                tokens.add(t)

    def score(url: str) -> int:
        match = re.search(r"github\.com/([^/]+)/([^/?#]+)", url, re.I)
        if not match:
            return 0
        owner = match.group(1).lower()
        repo = match.group(2).lower().rstrip(".git")
        s = 0
        for tok in tokens:
            if tok in (owner, repo):
                s += 4
            elif tok in owner or tok in repo:
                s += 2
        # Prefer repos that look like contracts/protocol code over docs/site
        if any(kw in repo for kw in ("contract", "core", "protocol", "v2", "v3", "v4", "smart")):
            s += 1
        if any(kw in repo for kw in ("docs", "website", "site", "frontend", "ui", "blog")):
            s -= 1
        return s

    # Stable sort: preserve original order on ties (first-mentioned wins)
    return sorted(urls, key=score, reverse=True)


# ─────────────────────────────────────────────────────────────────────────────
# BATCH K2: multi-URL fallback for protocols whose DefiLlama url is wrong
# ─────────────────────────────────────────────────────────────────────────────


# Common protocol-name suffixes to strip when slug-ifying a display name.
# "SoDEX Bridge" → "sodex", "Pendle Finance" → "pendle", "Aave Protocol" → "aave"
_DISPLAY_NAME_SUFFIXES = {
    "bridge",
    "protocol",
    "finance",
    "dao",
    "network",
    "labs",
    "foundation",
    "exchange",
    "swap",
    "v1",
    "v2",
    "v3",
    "v4",
}


# Common TLDs to try when deriving a domain from a slug.
_CANDIDATE_TLDS = ("com", "xyz", "io", "fi", "finance", "network", "app", "org")


# Common security/audit URL paths to try on each candidate domain.
# Ordered by approximate likelihood of containing audit firm names — short and
# common paths first, deeper nesting last. List intentionally over-covers so a
# new protocol's docs nesting (e.g. SoDEX's /documentation/custody-and-security/
# audits) doesn't slip through.
_AUDIT_PATHS = (
    # Top-level shortcuts
    "/audit",
    "/audits",
    "/security",
    "/audit-reports",
    # Direct nesting
    "/security/audits",
    "/security/audit-reports",
    "/security/reports",
    # /docs/* (mintlify / docusaurus convention)
    "/docs/security",
    "/docs/audits",
    "/docs/security/audits",
    # /documentation/* (gitbook convention)
    "/documentation/security",
    "/documentation/audits",
    "/documentation/security/audits",
    "/documentation/custody-and-security",
    "/documentation/custody-and-security/audits",
    # /about/* and /resources/*
    "/about/security",
    "/resources/audits",
)


def _slugify_display_name(display_name: str) -> str | None:
    """Convert a display name to a slug suitable for domain derivation.

    Examples:
        "SoDEX Bridge" → "sodex"
        "Pendle Finance" → "pendle"
        "Aave V3" → "aave"
        "Spark Savings" → "spark"
        "" → None
    """
    if not display_name:
        return None
    # Lowercase and split on whitespace + punctuation
    tokens = re.split(r"[^a-z0-9]+", display_name.lower())
    # Drop empty tokens and known suffix words
    tokens = [t for t in tokens if t and t not in _DISPLAY_NAME_SUFFIXES]
    if not tokens:
        return None
    # Prefer the first remaining token (the brand name usually leads)
    # over single-character or all-digit tokens
    for t in tokens:
        if len(t) >= 2 and not t.isdigit():
            return t
    return None


def derive_candidate_urls(
    display_name: str | None, base_url: str | None
) -> list[str]:
    """Generate a list of candidate URLs to try for audit-firm scraping.

    Strategy (priority-ordered):
      1. The base_url itself (DefiLlama's `url` field), if any.
      2. Slug × .com × audit paths. Highest signal: when the input URL is
         wrong, the brand's `.com` is usually right (this catches the SoDEX
         case where DefiLlama returned a SosoValue invite link).
      3. The base_url's domain root + audit paths (subdomain stripped).
         Lower priority because when the input URL is wrong, the parent
         company domain is also likely wrong.
      4. Slug × other TLDs × audit paths (least-likely fallback).

    Returns a deduped, ordered list. Capped at 50 entries to keep the ordered
    list bounded. The actual per-scan request budget is enforced by
    scrape_homepage_with_fallback's `max_attempts` parameter — this cap does NOT
    itself cause 50 HTTP calls.
    """
    candidates: list[str] = []
    seen: set[str] = set()

    def add(url: str) -> None:
        if url and url not in seen:
            seen.add(url)
            candidates.append(url)

    # 1. The base URL itself (if valid)
    if base_url and isinstance(base_url, str) and base_url.startswith("http"):
        add(base_url)

    # 2. Slug × .com × audit paths (highest-signal derived candidates)
    slug = _slugify_display_name(display_name or "")
    if slug:
        primary_domain = f"https://{slug}.com"
        add(primary_domain)
        for path in _AUDIT_PATHS:
            add(primary_domain + path)

    # 2b. docs.<slug> + app.<slug> subdomain probes (G1).
    # Many protocols host audit pages on docs.<slug>.<tld> rather than the
    # root domain. Example: docs.bima.money/security exists but bima.money
    # has no /security path. Step 3 below only STRIPS docs./app., never
    # ADDS them — so a protocol whose homepage is bima.money never gets
    # docs.bima.money/security probed without this step.
    # Tightly scoped: 2 subdomains × top-4 audit paths × {.com + inferred TLD
    # from base_url, if different} keeps this under ~16 added URLs.
    if slug:
        _HIGH_SIGNAL_AUDIT_PATHS = (
            "/security",
            "/security/audits",
            "/audits",
            "/audit-reports",
        )
        _SUBDOMAIN_TLDS = ["com"]
        if base_url and isinstance(base_url, str) and base_url.startswith("http"):
            try:
                base_tld = urlparse(base_url).netloc.rsplit(".", 1)[-1].lower()
                if base_tld and base_tld != "com" and base_tld.isalpha():
                    _SUBDOMAIN_TLDS.append(base_tld)
            except (ValueError, AttributeError):
                pass
        for subdomain in ("docs", "app"):
            for tld in _SUBDOMAIN_TLDS:
                sub_base = f"https://{subdomain}.{slug}.{tld}"
                add(sub_base)
                for path in _HIGH_SIGNAL_AUDIT_PATHS:
                    add(sub_base + path)

    # 3. Base URL's domain root + audit paths (subdomain stripped)
    if base_url and isinstance(base_url, str) and base_url.startswith("http"):
        try:
            parsed = urlparse(base_url)
            if parsed.scheme and parsed.netloc:
                netloc = parsed.netloc.lower()
                root_netloc = netloc
                parts = netloc.split(".")
                if len(parts) >= 3 and parts[0] in (
                    "docs",
                    "app",
                    "ssi",
                    "invite",
                    "share",
                    "www",
                    "go",
                    "link",
                ):
                    root_netloc = ".".join(parts[1:])

                root_base = f"{parsed.scheme}://{root_netloc}"
                add(root_base)
                for path in _AUDIT_PATHS:
                    add(root_base + path)
        except (ValueError, AttributeError):
            pass

    # 4. Slug × other TLDs × audit paths (least-likely fallback)
    if slug:
        for tld in _CANDIDATE_TLDS:
            if tld == "com":
                continue  # already added in step 2
            domain_base = f"https://{slug}.{tld}"
            add(domain_base)
            for path in _AUDIT_PATHS:
                add(domain_base + path)
                if len(candidates) >= 50:
                    break
            if len(candidates) >= 50:
                break

    return candidates[:50]


# ─────────────────────────────────────────────────────────────────────────────
# BATCH L: Phase 3 link-crawl fallback
# ─────────────────────────────────────────────────────────────────────────────
#
# When derived audit-path guesses fail (Phase 2), the homepage itself almost
# always links to the audit page from its nav or footer — but at a custom URL
# we'd never guess (e.g. SoDEX uses /documentation/custody-and-security/audits).
# We parse the Phase 1 HTML for <a href> tags whose href or anchor text mentions
# audit/security/review keywords, then visit the highest-scoring same-domain
# links and re-run the audit-firm regex on those pages.

_ANCHOR_PATTERN = re.compile(
    r'<a\s+[^>]*?href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
    re.I | re.DOTALL,
)

_AUDIT_KEYWORD_PATTERN = re.compile(r"\b(audit|audits|security|reviews?)\b", re.I)
_AUDIT_STRONG_PATTERN = re.compile(r"\baudits?\b", re.I)

# Subdomains whose registered-domain match should still count as "same site".
# A protocol's audit page is often on docs.protocol.com or app.protocol.com,
# never on a totally unrelated host — restricting to same registered domain
# avoids following random external links (twitter, blog hosts, partners).
_SAME_SITE_SUBDOMAIN_HINTS = frozenset(
    {"docs", "app", "www", "security", "learn", "gitbook", "developers", "help"}
)


def _registered_domain(netloc: str) -> str:
    """Last two dot-separated labels — a cheap proxy for the registered domain.

    For `docs.sodex.com` returns `sodex.com`. For `sodex.com` returns `sodex.com`.
    Imperfect for multi-label TLDs (`.co.uk`) but those are vanishingly rare
    among DeFi protocol homepages, so the simpler heuristic wins.
    """
    parts = netloc.lower().split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return netloc.lower()


def _clean_anchor_text(raw: str) -> str:
    """Strip inner tags + collapse whitespace from anchor text."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw)).strip()


def _extract_audit_relevant_links(html: str, base_url: str) -> list[str]:
    """Find <a href> tags mentioning audit/security/review; return ranked URLs.

    Same-registered-domain only — never follows out to twitter, partner sites,
    or arbitrary external blogs. Deduped and capped to keep callers honest.
    """
    if not html or not base_url:
        return []
    try:
        base_parsed = urlparse(base_url)
        base_registered = _registered_domain(base_parsed.netloc)
        if not base_registered or "." not in base_registered:
            return []
    except (ValueError, AttributeError):
        return []

    scored: list[tuple[int, str]] = []
    seen: set[str] = set()

    for match in _ANCHOR_PATTERN.finditer(html[:200_000]):
        href = match.group(1).strip()
        anchor = _clean_anchor_text(match.group(2))

        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:", "data:")):
            continue

        href_score = 0
        anchor_score = 0
        if _AUDIT_KEYWORD_PATTERN.search(href):
            href_score = 3
            if _AUDIT_STRONG_PATTERN.search(href):
                href_score += 1
        if _AUDIT_KEYWORD_PATTERN.search(anchor):
            anchor_score = 2
            if _AUDIT_STRONG_PATTERN.search(anchor):
                anchor_score += 1
        if href_score == 0 and anchor_score == 0:
            continue

        try:
            absolute = urljoin(base_url, href)
            absolute_parsed = urlparse(absolute)
        except (ValueError, AttributeError):
            continue

        if absolute_parsed.scheme not in ("http", "https"):
            continue
        if not absolute_parsed.netloc:
            continue
        if _registered_domain(absolute_parsed.netloc) != base_registered:
            continue

        canonical = absolute.split("#")[0]
        if canonical in seen:
            continue
        seen.add(canonical)
        scored.append((href_score + anchor_score, canonical))

        if len(scored) >= 15:
            break

    scored.sort(key=lambda x: x[0], reverse=True)
    return [url for _, url in scored]


async def _follow_audit_links(
    base_url: str,
    base_html: str,
    *,
    client: httpx.AsyncClient | None,
    max_visits: int = 3,
) -> HomepageScrapeResult:
    """Visit the top audit-relevant links from base_html; return first useful hit."""
    candidate_links = _extract_audit_relevant_links(base_html, base_url)
    if not candidate_links:
        return _EMPTY

    best = _EMPTY
    for link in candidate_links[:max_visits]:
        result = await scrape_homepage(link, client=client)
        if result.fetched and (result.audit_firm_matches or result.wrapper_matches):
            log.info(
                "homepage_scrape L link-crawl: %s → audit=%s wrapper=%s",
                link,
                result.audit_firm_matches,
                result.wrapper_matches,
            )
            return result
        if result.fetched and not best.fetched:
            best = result
    return best


async def scrape_homepage_with_fallback(
    base_url: str | None,
    display_name: str | None,
    *,
    client: httpx.AsyncClient | None = None,
    max_attempts: int = 12,
) -> HomepageScrapeResult:
    """Three-phase homepage scrape with derived URL and link-crawl fallback.

    Phase 1: try the base_url. If it returns successfully AND found at least
    one wrapper or audit firm match, return immediately — single URL was
    sufficient.

    Phase 2: try derived candidate URLs in order, stopping on the first
    successful fetch that yields any wrapper or audit firm match.

    Phase 3 (Batch L): if Phase 1 fetched HTML but found nothing, mine that
    HTML for <a href> links whose href or anchor text mentions audit/security/
    review keywords and visit those (top 3, same-registered-domain only).
    Catches protocols whose audit page lives at a custom path we'd never guess
    (e.g. SoDEX → /documentation/custody-and-security/audits).

    Phases 1 and 2 share the `max_attempts` budget. Phase 3 has its own
    implicit budget of 3 visits because it's targeted (only follows links the
    homepage itself surfaces, same-registered-domain only) and a tight
    caller-side max_attempts shouldn't strangle the cheapest, highest-signal
    fallback. Returns the BEST result found, or an empty result if nothing
    succeeded.
    """
    # Phase 1
    primary, primary_html = await _fetch_and_extract(base_url, client=client)
    if primary.fetched and (primary.wrapper_matches or primary.audit_firm_matches):
        return primary

    # Phase 2: try derived URLs
    derived = derive_candidate_urls(display_name, base_url)
    if base_url in derived:
        derived = [u for u in derived if u != base_url]

    best_result = primary
    attempts_made = 1
    for candidate in derived:
        if attempts_made >= max_attempts:
            break
        attempts_made += 1
        result = await scrape_homepage(candidate, client=client)
        if result.fetched and (result.wrapper_matches or result.audit_firm_matches):
            log.info(
                "homepage_scrape K2 fallback: derived URL %s succeeded for %r "
                "(wrapper=%s audit=%s)",
                candidate,
                display_name,
                result.wrapper_matches,
                result.audit_firm_matches,
            )
            return result
        if result.fetched and not best_result.fetched:
            best_result = result

    # Phase 3 (Batch L): mine Phase 1's HTML for audit-related links.
    # Independent of the max_attempts budget — Phase 3 only fires when the
    # homepage actually produced HTML and the cheaper phases came up empty,
    # and it's bounded internally to 3 visits (one HTTP each).
    if primary.fetched and primary_html:
        crawl_result = await _follow_audit_links(
            primary.url or base_url or "",
            primary_html,
            client=client,
            max_visits=3,
        )
        if crawl_result.fetched and (
            crawl_result.audit_firm_matches or crawl_result.wrapper_matches
        ):
            return crawl_result
        if crawl_result.fetched and not best_result.fetched:
            best_result = crawl_result

    return best_result
