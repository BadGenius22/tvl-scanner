"""Tests for the audit-check orchestrator's skip optimization (Batch H fix #2)."""

from __future__ import annotations

import contextlib
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

from tvl_scanner.audit_check.checker import check_all, check_one
from tvl_scanner.models import (
    AuditedCandidate,
    AuditSource,
    AuditSourceKind,
    Chain,
    DiscoverySource,
    EnrichedCandidate,
    Language,
)


def _enriched(
    *,
    defillama_audit_count: int | None = None,
    defillama_slug: str | None = "test-protocol",
    precomputed_audit_sources: list[AuditSource] | None = None,
) -> EnrichedCandidate:
    return EnrichedCandidate(
        chain=Chain.ARBITRUM,
        address="0xABC",
        tvl_usd=250_000,
        first_seen=date(2026, 3, 15),
        source=DiscoverySource.DEFILLAMA_CATALOG,
        target_name="test-protocol",
        display_name="Test Protocol",
        protocol_type="Yield on arbitrum",
        languages=[Language.SOLIDITY],
        defillama_slug=defillama_slug,
        defillama_audit_count=defillama_audit_count,
        precomputed_audit_sources=precomputed_audit_sources or [],
    )


async def test_check_one_skips_github_when_defillama_reports_audits() -> None:
    """A candidate with defillama_audit_count > 0 must NOT call check_all_contests."""
    candidate = _enriched(defillama_audit_count=3)

    with patch(
        "tvl_scanner.audit_check.checker.check_all_contests",
        new=AsyncMock(return_value=[]),
    ) as mock_contests:
        result = await check_one(candidate)
        mock_contests.assert_not_called()

    # The candidate should still get scored using DefiLlama's audit count
    # (defillama_audit_count=3 → 3 phantom DL sources → score = 3)
    assert result.audit_density_score == 3


async def test_check_one_runs_github_when_defillama_reports_zero_audits() -> None:
    """When defillama_audit_count is 0, GitHub contest search MUST still run."""
    candidate = _enriched(defillama_audit_count=0)

    mock_contest_source = AuditSource(
        source=AuditSourceKind.CODE4RENA,
        url="https://github.com/code-423n4/2024-01-foo",  # type: ignore[arg-type]
        weight=3,
    )
    with patch(
        "tvl_scanner.audit_check.checker.check_all_contests",
        new=AsyncMock(return_value=[mock_contest_source]),
    ) as mock_contests:
        result = await check_one(candidate)
        mock_contests.assert_called_once()

    # Should have the single C4 source = 3 points
    assert result.audit_density_score == 3


async def test_check_one_runs_github_when_defillama_count_is_none() -> None:
    """Pool-based candidates never hit DefiLlama detail → audit_count stays None → must run GitHub."""
    candidate = _enriched(defillama_audit_count=None, defillama_slug=None)

    with patch(
        "tvl_scanner.audit_check.checker.check_all_contests",
        new=AsyncMock(return_value=[]),
    ) as mock_contests:
        await check_one(candidate)
        mock_contests.assert_called_once()


def _audited(slug: str) -> AuditedCandidate:
    return AuditedCandidate(
        chain=Chain.ARBITRUM,
        address="0xABC",
        tvl_usd=250_000,
        first_seen=date(2026, 3, 15),
        source=DiscoverySource.DEFILLAMA_CATALOG,
        target_name=slug,
        display_name=slug,
        protocol_type="Yield on arbitrum",
        languages=[Language.SOLIDITY],
        defillama_slug=slug,
        audit_density_score=3,
        under_audited=False,
    )


@contextlib.asynccontextmanager
async def _fake_client():
    yield MagicMock()


async def test_check_all_isolates_a_single_candidate_failure() -> None:
    """One candidate raising in Stage 3 must drop only that candidate, not the stage."""
    good = _enriched(defillama_audit_count=3, defillama_slug="good")
    bad = _enriched(defillama_audit_count=1, defillama_slug="bad")

    async def fake_check_one(candidate: EnrichedCandidate, *, client: object = None, token_cache: object = None) -> AuditedCandidate:
        if candidate.defillama_slug == "bad":
            raise RuntimeError("simulated stage-3 failure")
        return _audited("good")

    with (
        patch("tvl_scanner.audit_check.checker.make_client", _fake_client),
        patch("tvl_scanner.audit_check.checker.check_one", side_effect=fake_check_one),
    ):
        results = await check_all([good, bad])

    assert len(results) == 1
    assert results[0].defillama_slug == "good"


async def test_check_one_skips_github_when_scope_audit_already_found() -> None:
    """Prose-cited audits settle `under_audited` on their own, so re-confirming
    them via three GitHub searches only burns the 30/min search budget."""
    candidate = _enriched(
        defillama_audit_count=0,
        precomputed_audit_sources=[
            AuditSource(
                source=AuditSourceKind.BOUNTY_SCOPE_AUDIT,
                url="https://github.com/sigp/public-audits/lyra.pdf",
                title="Audit report cited in bounty scope (sigp)",
                weight=2,
            )
        ],
    )

    with patch(
        "tvl_scanner.audit_check.checker.check_all_contests",
        new=AsyncMock(return_value=[]),
    ) as mock_contests:
        result = await check_one(candidate)
        mock_contests.assert_not_called()

    assert result.under_audited is False


async def test_check_one_runs_github_when_no_evidence_at_all() -> None:
    """The skip must not swallow the genuinely-unknown case."""
    candidate = _enriched(defillama_audit_count=0, precomputed_audit_sources=[])

    with patch(
        "tvl_scanner.audit_check.checker.check_all_contests",
        new=AsyncMock(return_value=[]),
    ) as mock_contests:
        await check_one(candidate)
        mock_contests.assert_called_once()
