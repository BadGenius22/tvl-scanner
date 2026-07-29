"""Tests for audit density scoring."""

from __future__ import annotations

from datetime import date

from tvl_scanner.audit_check.score import (
    UNDER_AUDITED_THRESHOLD,
    _defillama_sources,
    _github_folder_source,
    compute_score,
)
from tvl_scanner.models import (
    AuditSource,
    AuditSourceKind,
    Chain,
    DiscoverySource,
    EnrichedCandidate,
    Language,
)


def _enriched(
    *,
    defillama_audit_links: list[str] | None = None,
    github_audits_folder_exists: bool = False,
    github_audit_report_count: int = 0,
    github_repo: str | None = None,
) -> EnrichedCandidate:
    return EnrichedCandidate(
        chain=Chain.ARBITRUM,
        address="0xABC",
        tvl_usd=250000,
        first_seen=date(2026, 3, 15),
        source=DiscoverySource.GECKOTERMINAL,
        target_name="test-protocol",
        display_name="Test Protocol",
        protocol_type="unknown protocol on arbitrum",
        languages=[Language.SOLIDITY],
        github_repo=github_repo,  # type: ignore[arg-type]
        defillama_audit_links=defillama_audit_links or [],  # type: ignore[arg-type]
        github_audits_folder_exists=github_audits_folder_exists,
        github_audit_report_count=github_audit_report_count,
    )


def _with_updates(candidate: EnrichedCandidate, **updates: object) -> EnrichedCandidate:
    """Rebuild with validation — model_copy(update=...) skips it, leaving raw
    strings in HttpUrl fields and tripping pydantic serializer warnings."""
    return EnrichedCandidate(**{**candidate.model_dump(), **updates})


def test_defillama_sources_capped_at_3() -> None:
    """More than 3 DefiLlama audit links should still only score 3 points."""
    candidate = _enriched(
        defillama_audit_links=[
            "https://example.com/audit1.pdf",
            "https://example.com/audit2.pdf",
            "https://example.com/audit3.pdf",
            "https://example.com/audit4.pdf",
            "https://example.com/audit5.pdf",
        ]
    )
    sources = _defillama_sources(candidate)
    assert len(sources) == 3
    assert all(s.weight == 1 for s in sources)


def test_github_folder_source_requires_repo_url() -> None:
    """Audits folder flag without a repo URL should produce nothing."""
    candidate = _enriched(github_audits_folder_exists=True, github_repo=None)
    assert _github_folder_source(candidate) == []


def test_github_folder_source_emits_one_point() -> None:
    candidate = _enriched(
        github_audits_folder_exists=True,
        github_repo="https://github.com/foo/bar",
    )
    sources = _github_folder_source(candidate)
    assert len(sources) == 1
    assert sources[0].weight == 1  # count=0 → floor of 1 (backward compat)
    assert str(sources[0].url).endswith("/tree/HEAD/audits")


def test_github_folder_source_weights_by_report_count() -> None:
    """A multiply-audited repo (e.g. Bailsec x3 + Certora + Zenith) scores the
    full cap of 3, not a flat 1 — so it reads as saturated, not under-audited."""
    candidate = _enriched(
        github_audits_folder_exists=True,
        github_audit_report_count=5,
        github_repo="https://github.com/foo/bar",
    )
    sources = _github_folder_source(candidate)
    assert len(sources) == 1
    assert sources[0].weight == 3  # min(cap=3, 5)


def test_multiply_audited_repo_not_under_audited() -> None:
    """3+ in-repo audit reports alone push a candidate past the under-audited
    threshold (<=2), even with no DefiLlama links or contests."""
    candidate = _enriched(
        github_audits_folder_exists=True,
        github_audit_report_count=4,
        github_repo="https://github.com/foo/bar",
    )
    result = compute_score(candidate, contest_sources=[])
    assert result.audit_density_score >= 3
    assert result.under_audited is False


def test_compute_score_zero_for_empty_candidate() -> None:
    candidate = _enriched()
    result = compute_score(candidate, contest_sources=[])
    assert result.audit_density_score == 0
    assert result.under_audited is True


def test_compute_score_full_signal_marks_not_under_audited() -> None:
    """DefiLlama(3) + GitHub folder(1) + one C4 hit(3) = 7 points → not under-audited."""
    candidate = _enriched(
        defillama_audit_links=["https://example.com/a1.pdf", "https://example.com/a2.pdf"],
        github_audits_folder_exists=True,
        github_repo="https://github.com/foo/bar",
    )
    contest = [
        AuditSource(
            source=AuditSourceKind.CODE4RENA,
            url="https://github.com/code-423n4/2024-01-foo",
            weight=3,
        )
    ]
    result = compute_score(candidate, contest_sources=contest)
    # 2 DL links (capped at 3) + 1 github folder + 3 C4 = 6
    assert result.audit_density_score == 6
    assert result.under_audited is False


def test_compute_score_borderline_case() -> None:
    """Exactly 2 points (threshold) should be under_audited."""
    candidate = _enriched(
        defillama_audit_links=["https://example.com/a1.pdf"],
        github_audits_folder_exists=True,
        github_repo="https://github.com/foo/bar",
    )
    # DL(1) + GitHub folder(1) = 2, threshold = 2 → under_audited (<=)
    result = compute_score(candidate)
    assert result.audit_density_score == 2
    assert result.under_audited is True
    assert UNDER_AUDITED_THRESHOLD == 2


def test_compute_score_preserves_enriched_fields() -> None:
    """AuditedCandidate should carry all EnrichedCandidate fields unchanged."""
    candidate = _enriched()
    result = compute_score(candidate)
    assert result.chain == candidate.chain
    assert result.target_name == candidate.target_name
    assert result.display_name == candidate.display_name
    assert result.tvl_usd == candidate.tvl_usd


def test_compute_score_defillama_count_override_forces_not_under_audited() -> None:
    """Batch I fix #2: a candidate with low total_score but defillama_audit_count >= 2
    should be forced to under_audited=False.
    """
    # Construct a candidate with NO audit signals other than defillama_audit_count=3.
    # Total score would normally be 0 → under_audited=True. But with audit_count=3
    # the override kicks in and flips it.
    import datetime

    from tvl_scanner.models import (
        Chain,
        DiscoverySource,
        EnrichedCandidate,
        Language,
    )

    candidate = EnrichedCandidate(
        chain=Chain.ARBITRUM,
        address="0xABC",
        tvl_usd=500000,
        first_seen=datetime.date(2026, 3, 15),
        source=DiscoverySource.DEFILLAMA_CATALOG,
        target_name="test",
        display_name="Test Protocol",
        protocol_type="Lending on arbitrum",
        languages=[Language.SOLIDITY],
        defillama_audit_count=3,  # KEY: DL reports 3 audits
        defillama_audit_links=[],  # but no linked audits (the override path)
    )
    result = compute_score(candidate, contest_sources=[])
    # audit_count=3 generates 3 phantom DL sources → score=3, but the important
    # assertion is under_audited=False from the override
    assert result.under_audited is False


def test_compute_score_defillama_count_zero_leaves_under_audited_true() -> None:
    """A candidate with defillama_audit_count=0 should NOT trigger the override."""
    import datetime

    from tvl_scanner.models import (
        Chain,
        DiscoverySource,
        EnrichedCandidate,
        Language,
    )

    candidate = EnrichedCandidate(
        chain=Chain.ARBITRUM,
        address="0xABC",
        tvl_usd=500000,
        first_seen=datetime.date(2026, 3, 15),
        source=DiscoverySource.DEFILLAMA_CATALOG,
        target_name="test",
        display_name="Fresh Protocol",
        protocol_type="Lending on arbitrum",
        languages=[Language.SOLIDITY],
        defillama_audit_count=0,
    )
    result = compute_score(candidate, contest_sources=[])
    assert result.under_audited is True
    assert result.audit_density_score == 0


def test_bounty_trust_source_fires_for_immunefi_with_substantial_payout() -> None:
    """Batch I.2: a candidate with an Immunefi bounty $100K+ should get a
    BOUNTY_TRUST audit source automatically.
    """
    from tvl_scanner.audit_check.score import _bounty_trust_source

    candidate = _with_updates(
        _enriched(),
        bounty_program="immunefi",
        bounty_url="https://immunefi.com/bounty/hyperlane/",
        bounty_max_payout_usd=2_500_000,
    )
    sources = _bounty_trust_source(candidate)
    assert len(sources) == 1
    assert sources[0].source == AuditSourceKind.BOUNTY_TRUST
    assert sources[0].weight == 4
    assert "immunefi" in (sources[0].title or "")
    assert "2,500,000" in (sources[0].title or "")


def test_bounty_trust_source_skips_low_payout() -> None:
    """A bounty below $100K is too small to imply professional audit due diligence."""
    from tvl_scanner.audit_check.score import _bounty_trust_source

    candidate = _with_updates(
        _enriched(),
        bounty_program="immunefi",
        bounty_url="https://immunefi.com/bounty/small/",
        bounty_max_payout_usd=50_000,
    )
    assert _bounty_trust_source(candidate) == []


def test_bounty_trust_source_skips_no_bounty() -> None:
    """A candidate with no bounty program should not get a phantom trust source."""
    from tvl_scanner.audit_check.score import _bounty_trust_source

    candidate = _enriched()
    assert _bounty_trust_source(candidate) == []


def test_compute_score_bounty_trust_pushes_above_threshold() -> None:
    """Hyperlane case: 0 audits in DL/github/contest, but Immunefi bounty $2.5M
    → BOUNTY_TRUST source contributes weight 4 → under_audited=False.
    """
    candidate = _with_updates(
        _enriched(),
        bounty_program="immunefi",
        bounty_url="https://immunefi.com/bounty/hyperlane/",
        bounty_max_payout_usd=2_500_000,
    )
    result = compute_score(candidate, contest_sources=[])
    assert result.audit_density_score == 4  # bounty trust source = 4 pts
    assert result.under_audited is False
    # The synthetic source should be in the sources list for transparency
    assert any(s.source == "bounty_trust" for s in result.audit_sources_found)


def test_compute_score_defillama_count_one_does_not_override() -> None:
    """audit_count=1 is below the override threshold of 2 (single audit is weak signal)."""
    import datetime

    from tvl_scanner.models import (
        Chain,
        DiscoverySource,
        EnrichedCandidate,
        Language,
    )

    candidate = EnrichedCandidate(
        chain=Chain.ARBITRUM,
        address="0xABC",
        tvl_usd=500000,
        first_seen=datetime.date(2026, 3, 15),
        source=DiscoverySource.DEFILLAMA_CATALOG,
        target_name="test",
        display_name="One Audit Protocol",
        protocol_type="Lending on arbitrum",
        languages=[Language.SOLIDITY],
        defillama_audit_count=1,
    )
    result = compute_score(candidate)
    # Score=1, threshold=2 → still under_audited, override does NOT trigger
    assert result.under_audited is True


def test_bounty_scope_audit_clears_under_audited() -> None:
    """A program citing its own prior audit is audited, whatever else scores.

    Regression: Derive, Metronome and SPOT each linked an audit report in their
    Immunefi program text yet scored audit_density_score=0, because the only
    audit sources Stage 3 consulted were DefiLlama and the C4/Sherlock/Cantina
    contest orgs — none of which see PDF-publishing firms.
    """
    candidate = _with_updates(
        _enriched(),
        precomputed_audit_sources=[
            AuditSource(
                source=AuditSourceKind.BOUNTY_SCOPE_AUDIT,
                url="https://github.com/sigp/public-audits/blob/master/lyra-finance/review-round2.pdf",
                title="Audit report cited in bounty scope (sigp)",
                weight=2,
            )
        ],
    )

    scored = compute_score(candidate)

    assert scored.under_audited is False
    assert scored.audit_density_score >= 2


def test_no_scope_audit_leaves_candidate_under_audited() -> None:
    """The override must not fire for a candidate with genuinely no evidence."""
    scored = compute_score(_enriched())

    assert scored.under_audited is True
    assert scored.audit_density_score <= UNDER_AUDITED_THRESHOLD
