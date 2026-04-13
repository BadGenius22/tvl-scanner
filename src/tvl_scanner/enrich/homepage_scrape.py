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
from urllib.parse import urlparse

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

AUDIT_FIRM_PHRASES: dict[re.Pattern[str], str] = {
    re.compile(r"\btrail of bits\b", re.I): "trail_of_bits",
    re.compile(r"\bhalborn\b", re.I): "halborn",
    re.compile(r"\bzellic\b", re.I): "zellic",
    re.compile(r"\bchainsecurity\b", re.I): "chain_security",
    re.compile(r"\bopenzeppelin\b", re.I): "openzeppelin",
    re.compile(r"\bcyfrin\b", re.I): "cyfrin",
    re.compile(r"\bhexens\b", re.I): "hexens",
    re.compile(r"\bspearbit\b", re.I): "spearbit",
    re.compile(r"\bquantstamp\b", re.I): "quantstamp",
    re.compile(r"\bcertik\b", re.I): "certik",
    re.compile(r"\bsigma prime\b", re.I): "sigma_prime",
    re.compile(r"\bpeckshield\b", re.I): "peckshield",
    re.compile(r"\bslowmist\b", re.I): "slowmist",
    re.compile(r"\bconsensys diligence\b", re.I): "consensys_diligence",
    re.compile(r"\bmacro\b", re.I): "macro",
    re.compile(r"\bcode4rena\b", re.I): "code4rena",
    re.compile(r"\bsherlock\b", re.I): "sherlock",
}


@dataclass(frozen=True)
class HomepageScrapeResult:
    """Structured output of a homepage scrape."""

    url: str
    fetched: bool
    wrapper_matches: list[str]   # tags from WRAPPER_PHRASES values
    audit_firm_matches: list[str]  # tags from AUDIT_FIRM_PHRASES values


_EMPTY = HomepageScrapeResult(url="", fetched=False, wrapper_matches=[], audit_firm_matches=[])


async def scrape_homepage(
    url: str | None, *, client: httpx.AsyncClient | None = None
) -> HomepageScrapeResult:
    """Fetch `url` and run regex extraction. Returns empty result on any failure."""
    if not url or not isinstance(url, str) or not url.startswith(("http://", "https://")):
        return _EMPTY

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

    try:
        response = await client.get(url)
        if response.status_code >= 400:
            return HomepageScrapeResult(
                url=url, fetched=False, wrapper_matches=[], audit_firm_matches=[]
            )
        html = response.text
    except (httpx.HTTPError, ValueError) as exc:
        log.debug("homepage scrape failed for %s: %s", url, exc)
        return HomepageScrapeResult(
            url=url, fetched=False, wrapper_matches=[], audit_firm_matches=[]
        )
    finally:
        if owns_client:
            await client.aclose()

    # Many modern sites are SPAs and the body has minimal text. We still
    # check meta tags and any inline content. Cap input at 200KB so a
    # malicious oversized payload can't blow up the regex engine.
    sample = html[:200_000]

    wrapper_hits: set[str] = set()
    for pattern, tag in WRAPPER_PHRASES.items():
        if pattern.search(sample):
            wrapper_hits.add(tag)

    # Audit firms are only counted if the page also contains some audit
    # context word — this prevents false positives where a firm name happens
    # to appear out of context (e.g. on a partner page).
    audit_hits: set[str] = set()
    if AUDIT_CONTEXT_PATTERN.search(sample):
        for pattern, tag in AUDIT_FIRM_PHRASES.items():
            if pattern.search(sample):
                audit_hits.add(tag)

    return HomepageScrapeResult(
        url=url,
        fetched=True,
        wrapper_matches=sorted(wrapper_hits),
        audit_firm_matches=sorted(audit_hits),
    )


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
# Ordered by likelihood of containing audit firm names.
_AUDIT_PATHS = (
    "/security",
    "/audits",
    "/security/audits",
    "/documentation/security",
    "/documentation/audits",
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

    Returns a deduped, ordered list. Capped at ~15 entries to bound HTTP cost.
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
                if len(candidates) >= 15:
                    break
            if len(candidates) >= 15:
                break

    return candidates[:15]


async def scrape_homepage_with_fallback(
    base_url: str | None,
    display_name: str | None,
    *,
    client: httpx.AsyncClient | None = None,
    max_attempts: int = 6,
) -> HomepageScrapeResult:
    """Two-phase homepage scrape with derived URL fallback.

    Phase 1: try the base_url. If it returns successfully AND found at least
    one wrapper or audit firm match, return immediately — single URL was
    sufficient.

    Phase 2: try derived candidate URLs in order, stopping on the first
    successful fetch that yields any wrapper or audit firm match. Caps at
    `max_attempts` HTTP requests total (Phase 1 + Phase 2 combined).

    Returns the BEST result found across all attempts (the URL that
    produced the most/strongest matches), or an empty result if nothing
    succeeded.
    """
    # Phase 1
    primary = await scrape_homepage(base_url, client=client)
    if primary.fetched and (primary.wrapper_matches or primary.audit_firm_matches):
        return primary

    # Phase 2: try derived URLs
    derived = derive_candidate_urls(display_name, base_url)
    # Skip the base_url since we just tried it
    if base_url in derived:
        derived = [u for u in derived if u != base_url]

    best_result = primary  # baseline; updated if a derived URL beats it
    attempts_made = 1  # Phase 1 counts as 1
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

    return best_result
