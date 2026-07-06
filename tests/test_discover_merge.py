"""Tests for candidate merge, dedup, and threshold filters."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from tvl_scanner.discover.merge import (
    _apply_filters,
    _dedup,
    _normalize_address,
    write_candidates,
)
from tvl_scanner.models import Chain, DiscoveredContract, DiscoverySource


def _contract(
    chain: Chain,
    address: str,
    tvl_usd: float = 200000,
    days_old: int = 30,
    users: int | None = 100,
    source: DiscoverySource = DiscoverySource.GECKOTERMINAL,
) -> DiscoveredContract:
    return DiscoveredContract(
        chain=chain,
        address=address,
        protocol_guess=None,
        tvl_usd=tvl_usd,
        first_seen=date(2026, 4, 13) - timedelta(days=days_old),
        unique_users_30d=users,
        source=source,
    )


def test_normalize_address_evm_lowercases() -> None:
    assert _normalize_address(Chain.ARBITRUM, "0xABCdef") == "0xabcdef"


def test_normalize_address_solana_preserves_case() -> None:
    addr = "SoLbIrd1eYePaIrAdDrEsS000000000000000000001"
    assert _normalize_address(Chain.SOLANA, addr) == addr


def test_dedup_keeps_highest_tvl_per_key() -> None:
    """When the same contract appears from two sources, keep the richer snapshot."""
    a = _contract(Chain.ARBITRUM, "0xAAA", tvl_usd=100000, source=DiscoverySource.GECKOTERMINAL)
    b = _contract(Chain.ARBITRUM, "0xaaa", tvl_usd=300000, source=DiscoverySource.BIRDEYE)
    c = _contract(Chain.BASE, "0xBBB", tvl_usd=500000)

    result = _dedup([a, b, c])
    assert len(result) == 2
    deduped_arb = next(r for r in result if r.chain == Chain.ARBITRUM)
    assert deduped_arb.tvl_usd == 300000


def test_filter_drops_below_min_tvl() -> None:
    low = _contract(Chain.BASE, "0xLOW", tvl_usd=50000)
    high = _contract(Chain.BASE, "0xHIGH", tvl_usd=500000)

    kept = _apply_filters([low, high], scan_date=date(2026, 4, 13))
    assert len(kept) == 1
    assert kept[0].address == "0xHIGH"


def test_filter_drops_older_than_max_age() -> None:
    young = _contract(Chain.BASE, "0xYOUNG", days_old=30)
    ancient = _contract(Chain.BASE, "0xOLD", days_old=800)

    kept = _apply_filters([young, ancient], scan_date=date(2026, 4, 13))
    assert len(kept) == 1
    assert kept[0].address == "0xYOUNG"


def test_filter_drops_tvl_ghosts_with_low_activity() -> None:
    ghost = _contract(Chain.BASE, "0xGHOST", users=5)
    active = _contract(Chain.BASE, "0xACTIVE", users=500)

    kept = _apply_filters([ghost, active], scan_date=date(2026, 4, 13))
    assert len(kept) == 1
    assert kept[0].address == "0xACTIVE"


def test_filter_allows_none_user_count() -> None:
    """Birdeye does not expose user count — None should not be treated as zero."""
    unknown = _contract(Chain.SOLANA, "SoLxxx", users=None)

    kept = _apply_filters([unknown], scan_date=date(2026, 4, 13))
    assert len(kept) == 1


def test_filter_rejects_future_dated_records() -> None:
    """Negative age (first_seen > scan_date) should be dropped as corrupt data."""
    future = _contract(Chain.BASE, "0xFUT", days_old=-5)
    kept = _apply_filters([future], scan_date=date(2026, 4, 13))
    assert kept == []


def test_write_candidates_round_trip(tmp_path: Path) -> None:
    c1 = _contract(Chain.ARBITRUM, "0xAAA")
    c2 = _contract(Chain.SOLANA, "SoLxxx")

    path = tmp_path / "candidates.json"
    write_candidates([c1, c2], path=path)

    raw = json.loads(path.read_text())
    assert len(raw) == 2
    assert raw[0]["chain"] == "arbitrum"
    assert raw[1]["chain"] == "solana"
    assert raw[0]["tvl_usd"] == 200000
