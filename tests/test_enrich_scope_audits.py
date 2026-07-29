"""Tests for audit-report extraction from bounty-program prose.

The prose snippets below are verbatim excerpts from the live Immunefi payloads
for Derive, Metronome and SPOT — the three programs that a real scan flagged as
"no prior audits found" while every one of them linked its audit report in the
program text.
"""

from __future__ import annotations

from tvl_scanner.enrich.scope_audits import (
    MAX_SOURCES,
    extract_scope_audit_sources,
)
from tvl_scanner.models import AuditSourceKind

# Immunefi boilerplate present in every program — must never count as evidence.
BOILERPLATE = (
    "Rewards are distributed according to the impact of the vulnerability based on "
    "the [Immunefi Vulnerability Severity Classification System V2.2]"
    "(https://immunefi.com/immunefi-vulnerability-severity-classification-system-v2-2). "
    "- [Chain Rollbacks](https://immunefisupport.zendesk.com/hc/en-us/articles/16913153448721-Chain-Rollbacks)\n"
    "- [Any other actions prohibited by the Immunefi Rules](https://immunefi.com/rules/)"
)

DERIVE_REWARDS = (
    BOILERPLATE + "\n\nAny vulnerability already disclosed in the [audits that have "
    "been performed](https://github.com/sigp/public-audits/blob/master/lyra-finance/"
    "review-round2.pdf) are not able to receive a reward."
)

METRONOME_REWARDS = (
    BOILERPLATE + "\n\nKnown issues highlighted in the following audit reports are "
    "considered out of scope: \n- [https://github.com/autonomoussoftware/"
    "metronome-synth-audit/wiki/Audit](https://github.com/autonomoussoftware/"
    "metronome-synth-audit/wiki/Audit)"
)

SPOT_ASSETS = (
    "Known issues highlighted in the following audit reports are considered out of "
    "scope: \n\n- [https://github.com/ampleforth/ampleforth-audits/tree/master/spot/"
    "v1.0.0](https://github.com/ampleforth/ampleforth-audits/tree/master/spot/v1.0.0)"
)


def test_extracts_firm_org_url_from_rewards_body() -> None:
    """`sigp` is Sigma Prime's GitHub org — a firm token, no 'audit' in the path."""
    sources = extract_scope_audit_sources({"rewardsBody": DERIVE_REWARDS})

    assert len(sources) == 1
    assert sources[0].source == AuditSourceKind.BOUNTY_SCOPE_AUDIT
    assert sources[0].url == (
        "https://github.com/sigp/public-audits/blob/master/lyra-finance/review-round2.pdf"
    )
    assert "sigp" in (sources[0].title or "")


def test_extracts_team_hosted_audit_path() -> None:
    """No known firm in the URL — the `audit` path segment carries the signal."""
    sources = extract_scope_audit_sources({"rewardsBody": METRONOME_REWARDS})

    assert len(sources) == 1
    assert "metronome-synth-audit" in str(sources[0].url)


def test_extracts_from_assets_body() -> None:
    sources = extract_scope_audit_sources({"assetsBodyV2": SPOT_ASSETS})

    assert len(sources) == 1
    assert "ampleforth-audits" in str(sources[0].url)


def test_immunefi_boilerplate_alone_yields_nothing() -> None:
    """The severity-classification and rules links appear in every program."""
    assert extract_scope_audit_sources({"rewardsBody": BOILERPLATE}) == []


def test_no_prose_yields_nothing() -> None:
    assert extract_scope_audit_sources({}) == []
    assert extract_scope_audit_sources({"rewardsBody": None, "description": ""}) == []


def test_same_url_in_two_fields_counted_once() -> None:
    """Markdown links repeat the URL as both label and target."""
    sources = extract_scope_audit_sources(
        {"rewardsBody": METRONOME_REWARDS, "assetsBodyV2": METRONOME_REWARDS}
    )
    assert len(sources) == 1


def test_capped_at_max_sources() -> None:
    body = " ".join(
        f"https://example.com/audits/report-{i}.pdf" for i in range(MAX_SOURCES + 4)
    )
    assert len(extract_scope_audit_sources({"rewardsBody": body})) == MAX_SOURCES


def test_trailing_markdown_punctuation_stripped() -> None:
    """A URL closing a markdown link keeps the paren unless we strip it."""
    sources = extract_scope_audit_sources(
        {"rewardsBody": "see [report](https://chainsecurity.com/reports/Polygon.pdf)."}
    )
    assert str(sources[0].url) == "https://chainsecurity.com/reports/Polygon.pdf"


def test_social_links_are_not_audit_evidence() -> None:
    body = (
        "Follow https://twitter.com/exampledao and join https://discord.gg/example "
        "and read https://medium.com/@example/our-security-audit-story"
    )
    urls = [str(s.url) for s in extract_scope_audit_sources({"rewardsBody": body})]
    assert not any("twitter" in u or "discord" in u for u in urls)
