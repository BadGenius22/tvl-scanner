"""Audit-report links embedded in a bounty program's prose fields.

Immunefi's structured `audits` array is populated for only ~30% of live
programs, but ~64% cite their audit reports somewhere in the program prose.
That is not an accident of formatting: findings already disclosed in a prior
audit are OUT OF SCOPE for the bounty, so every program has a direct financial
incentive to link them. The citation usually lands in `rewardsBody` ("Any
vulnerability already disclosed in the audits that have been performed…") or
in `assetsBodyV2` ("Known issues highlighted in the following audit reports
are considered out of scope…").

Reading these recovers audit history for the traditional firms that the
GitHub contest search structurally cannot see — Sigma Prime, ChainSecurity,
OpenZeppelin, PeckShield, Halborn, Trail of Bits — because those firms
publish PDFs rather than running public contests. Measured against the live
catalogue, 110 of 248 programs (44%) carry audit evidence ONLY here.

Costs nothing: the program payload is already fetched for scope parsing.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from tvl_scanner.models import AuditSource, AuditSourceKind

log = logging.getLogger(__name__)

# Prose fields that carry audit citations, richest first.
PROSE_FIELDS: tuple[str, ...] = (
    "rewardsBody",
    "assetsBodyV2",
    "outOfScopeAndRules",
    "customOutOfScopeInformation",
    "knownIssues",
    "programOverview",
    "impactsBody",
    "description",
)

_URL = re.compile(r'https?://[^\s\)\]\>"\'`,]+')

# Immunefi's own boilerplate appears in every program (severity classification,
# support articles, rules). None of it is evidence about THIS protocol.
_EXCLUDED_HOSTS = re.compile(
    r"^https?://(?:[a-z0-9-]+\.)*"
    r"(?:immunefi\.com|immunefisupport\.zendesk\.com|zendesk\.com"
    r"|twitter\.com|x\.com|discord\.(?:gg|com)|t\.me|telegram\.org"
    r"|linkedin\.com|youtube\.com)",
    re.I,
)

# Audit firms and their publishing orgs, matched anywhere in the URL. `sigp` is
# Sigma Prime's GitHub org; `osec` is OtterSec's. Kept deliberately specific —
# these tokens are rare outside an audit context.
_FIRM_TOKENS = re.compile(
    r"(sigp|sigmaprime|trailofbits|trail-of-bits|openzeppelin|spearbit|cantina"
    r"|ottersec|osec|zellic|halborn|peckshield|quantstamp|certik|hexens|cyfrin"
    r"|veridise|dedaub|nethermind|consensys|chainsecurity|slowmist|hacken"
    r"|mixbytes|pashov|guardianaudits|kudelski|neodyme|runtimeverification"
    r"|ackee|zokyo|salus|beosin|statemind|pessimistic|solidified|immunebytes"
    r"|code-?423n4|sherlock-audit|bailsec|certora|zenith|oxorio|zokyo|zksecurity"
    r"|blocksec|secure3|shellboxes|sec3|bramah|iosiro|omniscia|paladin)",
    re.I,
)

# A URL whose path names an audit is self-describing regardless of who wrote
# it — catches team-hosted reports like `vesperfi/doc/tree/main/audit/v3+`,
# `Folks-Finance/audits`, and `devs.spark.fi/security/security-and-audits`.
_AUDIT_PATH = re.compile(r"/[^/]*audit", re.I)

MAX_SOURCES = 3
SOURCE_WEIGHT = 2


def _is_audit_url(url: str) -> bool:
    if _EXCLUDED_HOSTS.match(url):
        return False
    return bool(_AUDIT_PATH.search(url) or _FIRM_TOKENS.search(url))


def _attributed_firm(url: str) -> str | None:
    m = _FIRM_TOKENS.search(url)
    return m.group(1).lower() if m else None


def _clean(url: str) -> str:
    """Strip trailing punctuation that markdown link syntax leaves attached."""
    return url.rstrip(".,;:'\"`)]>*_")


def extract_scope_audit_sources(program: dict[str, Any]) -> list[AuditSource]:
    """Pull audit-report citations out of a bounty program's prose fields.

    Returns at most MAX_SOURCES deduplicated entries. Empty when the program
    cites nothing — which is a real signal, not a failure.
    """
    seen: set[str] = set()
    sources: list[AuditSource] = []

    # Asset URLs are scanned alongside the prose because some programs list an
    # audits page (or an audit-bearing repo path) as an in-scope asset rather
    # than citing it in text. Costs nothing — the assets are already in hand.
    asset_urls = " ".join(
        a.get("url", "")
        for a in (program.get("assets") or [])
        if isinstance(a, dict) and isinstance(a.get("url"), str)
    )

    for field in (*PROSE_FIELDS, "__assets__"):
        raw = asset_urls if field == "__assets__" else program.get(field)
        if not isinstance(raw, str) or not raw:
            continue
        for match in _URL.findall(raw):
            url = _clean(match)
            if url in seen or not _is_audit_url(url):
                continue
            seen.add(url)
            firm = _attributed_firm(url)
            title = (
                f"Audit report cited in bounty scope ({firm})"
                if firm
                else "Audit report cited in bounty scope"
            )
            sources.append(
                AuditSource(
                    source=AuditSourceKind.BOUNTY_SCOPE_AUDIT,
                    url=url,
                    title=title,
                    weight=SOURCE_WEIGHT,
                )
            )
            if len(sources) >= MAX_SOURCES:
                return sources
    return sources
