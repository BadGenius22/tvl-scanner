"""Tests for live Immunefi bounty enrichment."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from pytest_httpx import HTTPXMock

from tvl_scanner.enrich.immunefi import (
    IMMUNEFI_BOUNTIES_URL,
    ImmunefiIndex,
    build_index,
    fetch_programs,
    match,
    parse_program,
)

A1 = "0x" + "11" * 20
A2 = "0x" + "22" * 20


def _prog(slug: str, project: str, max_bounty: Any, kyc: bool, addrs: list[str]) -> dict[str, Any]:
    return {
        "slug": slug,
        "project": project,
        "maxBounty": max_bounty,
        "kyc": kyc,
        "assets": [
            {"type": "smart_contract", "url": f"https://etherscan.io/address/{a}#code"}
            for a in addrs
        ]
        + [{"type": "websites_and_applications", "url": "https://app.example.com"}],
    }


# --- parse_program -----------------------------------------------------------


def test_parse_program_extracts_addresses_and_meta() -> None:
    p = parse_program(_prog("aave", "Aave", 1_000_000, False, [A1]))
    assert p is not None
    assert p.slug == "aave"
    assert p.max_payout_usd == 1_000_000
    assert p.kyc is False
    assert p.url == "https://immunefi.com/bug-bounty/aave"
    assert A1.lower() in p.addresses
    assert "aave" in p.name_keys


def test_parse_program_no_slug_returns_none() -> None:
    assert parse_program({"project": "X", "assets": []}) is None


def test_parse_program_ignores_web_assets_and_null_bounty() -> None:
    p = parse_program({"slug": "x", "assets": [{"type": "websites_and_applications", "url": "u"}]})
    assert p is not None
    assert p.addresses == frozenset()
    assert p.max_payout_usd is None


# --- match -------------------------------------------------------------------


def _index() -> ImmunefiIndex:
    progs = [
        parse_program(_prog("aave", "Aave", 1_000_000, False, [A1])),
        parse_program(_prog("parallel", "Parallel Protocol", 250_000, True, [A2])),
    ]
    return build_index([p for p in progs if p is not None])


def test_match_by_address_is_definitive() -> None:
    m = match(_index(), address=A1)
    assert m is not None and m.slug == "aave" and m.reason == "address"


def test_match_by_address_case_insensitive() -> None:
    m = match(_index(), address=A1.upper())
    assert m is not None and m.slug == "aave"


def test_match_by_name_and_slug() -> None:
    idx = _index()
    m1 = match(idx, display_name="Aave")
    assert m1 is not None and m1.slug == "aave" and m1.reason == "name"
    m2 = match(idx, defillama_slug="parallel-protocol")
    assert m2 is not None and m2.slug == "parallel"


def test_match_address_beats_name() -> None:
    m = match(_index(), address=A2, display_name="Aave")
    assert m is not None and m.slug == "parallel" and m.reason == "address"


def test_match_no_hit_returns_none() -> None:
    idx = _index()
    assert match(idx, address="0x" + "99" * 20) is None
    assert match(idx, display_name="Nonexistent Fork") is None
    assert match(idx) is None


# --- fetch_programs (live catalogue) -----------------------------------------


async def test_fetch_programs_parses_catalogue(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=IMMUNEFI_BOUNTIES_URL,
        json=[_prog("aave", "Aave", 1_000_000, False, [A1]), {"no_slug": True}],
    )
    progs = await fetch_programs()
    assert len(progs) == 1  # the malformed (no-slug) entry is skipped
    assert progs[0].slug == "aave" and A1.lower() in progs[0].addresses


async def test_fetch_programs_tolerates_failure() -> None:
    # A fetch failure must degrade to [] (best-effort), never abort the scan.
    with patch("tvl_scanner.enrich.immunefi.get_json", side_effect=RuntimeError("boom")):
        assert await fetch_programs() == []
