"""Tests for DefiLlama /protocol/{slug} detail enrichment (Batch D)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pytest_httpx import HTTPXMock

from tvl_scanner.audit_check.score import _defillama_sources, compute_score
from tvl_scanner.enrich.defillama import DefiLlamaCatalog
from tvl_scanner.enrich.enricher import _coerce_audit_count
from tvl_scanner.models import (
    AuditSource,
    AuditSourceKind,
    Chain,
    DiscoverySource,
    EnrichedCandidate,
    Language,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def dl_protocol_detail() -> dict:
    return json.loads((FIXTURES / "defillama_protocol_detail.json").read_text())


# ---- _coerce_audit_count utility ----


def test_coerce_audit_count_accepts_int() -> None:
    assert _coerce_audit_count(3) == 3
    assert _coerce_audit_count(0) == 0


def test_coerce_audit_count_accepts_string() -> None:
    assert _coerce_audit_count("3") == 3
    assert _coerce_audit_count("0") == 0


def test_coerce_audit_count_rejects_garbage() -> None:
    assert _coerce_audit_count(None) is None
    assert _coerce_audit_count("not-a-number") is None
    assert _coerce_audit_count({}) is None


# ---- DefiLlamaCatalog.fetch_detail ----


async def test_fetch_detail_caches_per_slug(
    httpx_mock: HTTPXMock, dl_protocol_detail: dict
) -> None:
    """Second fetch of the same slug must not hit HTTP again."""
    httpx_mock.add_response(
        url="https://api.llama.fi/protocol/uniswap-v3",
        json=dl_protocol_detail,
    )
    catalog = DefiLlamaCatalog()

    first = await catalog.fetch_detail("uniswap-v3")
    assert first is not None
    assert first["audits"] == 3
    assert first["audit_note"].startswith("Last audited")

    # Second call should use cache, no HTTP
    second = await catalog.fetch_detail("uniswap-v3")
    assert second is first  # same object


async def test_fetch_detail_http_failure_returns_none(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://api.llama.fi/protocol/ghost",
        status_code=404,
        json={"error": "not found"},
        is_reusable=True,
    )
    catalog = DefiLlamaCatalog()
    result = await catalog.fetch_detail("ghost")
    assert result is None


# ---- Updated score.py _defillama_sources ----


def _enriched(
    *,
    audit_links: list[str] | None = None,
    audit_count: int | None = None,
    audit_note: str | None = None,
) -> EnrichedCandidate:
    from datetime import date
    return EnrichedCandidate(
        chain=Chain.ARBITRUM,
        address="0xABC",
        tvl_usd=200_000,
        first_seen=date(2026, 3, 15),
        source=DiscoverySource.GECKOTERMINAL,
        target_name="test",
        display_name="Test Protocol",
        protocol_type="unknown protocol on arbitrum",
        languages=[Language.SOLIDITY],
        defillama_audit_links=audit_links or [],  # type: ignore[arg-type]
        defillama_audit_count=audit_count,
        defillama_audit_note=audit_note,
    )


def test_defillama_sources_uses_links_when_present() -> None:
    """Two concrete links → two AuditSource records with URLs."""
    candidate = _enriched(
        audit_links=["https://example.com/a.pdf", "https://example.com/b.pdf"],
        audit_count=2,
    )
    sources = _defillama_sources(candidate)
    assert len(sources) == 2
    assert all(s.url is not None for s in sources)
    assert all(s.weight == 1 for s in sources)


def test_defillama_sources_adds_phantom_entries_when_count_exceeds_links() -> None:
    """3 audits reported but only 1 linked → 1 real + 2 phantom-URL entries."""
    candidate = _enriched(
        audit_links=["https://example.com/a.pdf"],
        audit_count=3,
        audit_note="Last audited 2024-05 by Trail of Bits, ABDK, Certora.",
    )
    sources = _defillama_sources(candidate)
    assert len(sources) == 3
    # First entry has a URL; entries 2-3 are phantom with title from audit_note
    urls_present = [s for s in sources if s.url is not None]
    urls_absent = [s for s in sources if s.url is None]
    assert len(urls_present) == 1
    assert len(urls_absent) == 2
    for phantom in urls_absent:
        assert phantom.title is not None
        assert "Trail of Bits" in phantom.title


def test_defillama_sources_respects_cap_of_three() -> None:
    """10 links should still only produce 3 scored entries."""
    candidate = _enriched(
        audit_links=[f"https://example.com/audit{i}.pdf" for i in range(10)],
        audit_count=10,
    )
    sources = _defillama_sources(candidate)
    assert len(sources) == 3


def test_defillama_sources_zero_count_no_links_returns_empty() -> None:
    candidate = _enriched()
    assert _defillama_sources(candidate) == []


def test_compute_score_uses_audit_count_signal() -> None:
    """A protocol with audit_count=3 but no links should still score 3 points."""
    candidate = _enriched(
        audit_links=[],
        audit_count=3,
        audit_note="Audited by ToB, OZ, Spearbit.",
    )
    result = compute_score(candidate)
    # 3 phantom DL entries × 1pt = 3 → exceeds under_audited threshold (2)
    assert result.audit_density_score == 3
    assert result.under_audited is False
