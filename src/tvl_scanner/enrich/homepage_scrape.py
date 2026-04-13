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
