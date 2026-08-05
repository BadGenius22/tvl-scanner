"""Tests for the broad bug-bounty directory fallback (lissy93/bug-bounties).

Parsing + matching are pure and tested against canned YAML docs; the async
wrapper is tested with a monkeypatched index. No network.
"""

from __future__ import annotations

from typing import Any

import pytest

from tvl_scanner.enrich import bugbounty_directory as bd

# Canned docs mirroring the two real files' shapes (rewards aliases already
# resolved by yaml.safe_load in production → plain strings here).
INDEPENDENT = {
    "companies": [
        {  # self-hosted, paying → url host is the protocol's own domain
            "company": "0x",
            "url": "https://docs.0x.org/developer-resources/bounties",
            "rewards": ["Bounty"],
            "max_payout": 1000000.0,
        },
        {  # recognition-only VDP → must be dropped (not a payout path)
            "company": ".nz Registry",
            "url": "https://registry.internetnz.nz/vdp/",
            "rewards": ["Hall of Fame"],
        },
    ]
}
PLATFORM = {
    "companies": [
        {  # platform-hosted → host is immunefi.com, NOT the target's domain
            "company": "Berachain",
            "url": "https://immunefi.com/bug-bounty/berachain/",
            "rewards": ["Bounty"],
        },
        {  # platform-hosted with explicit in-scope domains
            "company": "Acme Finance Managed Bug Bounty Engagement",
            "url": "https://bugcrowd.com/engagements/acme",
            "rewards": ["Bounty"],
            "domains": ["*.acmefinance.io (excluding docs)", "api.acmefinance.io"],
            "max_payout": 50000,
            "currency": "EUR",  # non-USD → payout not trusted as USD
        },
    ]
}


def _index() -> list[bd.DirectoryProgram]:
    return bd.build_index([INDEPENDENT, PLATFORM])


# --- helpers ---------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("https://docs.0x.org/x", "0x.org"),
        ("atlan.com", "atlan.com"),
        ("*.acmefinance.io (excluding docs)", "acmefinance.io"),
        ("api.foo.co.uk", "co.uk"),  # naive last-two-labels (documented limitation)
        ("not a domain", None),
        ("", None),
    ],
)
def test_registrable_domain(raw: str, expected: str | None) -> None:
    assert bd._registrable_domain(raw) == expected


def test_platform_from_url() -> None:
    assert bd._platform_from_url("https://immunefi.com/x") == "immunefi"
    assert bd._platform_from_url("https://www.hackerone.com/x") == "hackerone"
    assert bd._platform_from_url("https://bugcrowd.com/x") == "bugcrowd"
    assert bd._platform_from_url("https://docs.0x.org/x") == "selfhosted"


# --- index build -----------------------------------------------------------


def test_build_index_drops_non_paying() -> None:
    idx = _index()
    names = {p.name for p in idx}
    assert "0x" in names
    assert ".nz Registry" not in names  # recognition-only VDP dropped
    assert len(idx) == 3


def test_selfhosted_uses_url_domain() -> None:
    zero_x = next(p for p in _index() if p.name == "0x")
    assert zero_x.platform == "selfhosted"
    assert "0x.org" in zero_x.domains
    assert zero_x.max_payout_usd == 1000000


def test_platform_hosted_excludes_platform_domain() -> None:
    bera = next(p for p in _index() if p.name == "Berachain")
    assert bera.platform == "immunefi"
    assert "immunefi.com" not in bera.domains  # platform host is not the target


def test_explicit_domains_and_non_usd_payout() -> None:
    acme = next(p for p in _index() if p.name.startswith("Acme"))
    assert "acmefinance.io" in acme.domains
    assert acme.max_payout_usd is None  # EUR → not trusted as USD
    assert "acme-finance" in acme.norm_names  # noise suffix stripped


# --- matching --------------------------------------------------------------


def test_match_by_domain() -> None:
    m = bd.match(_index(), display_name="0x Protocol", homepage_url="https://www.0x.org")
    assert m is not None and m.name == "0x"


def test_match_by_explicit_domain() -> None:
    m = bd.match(_index(), display_name="Acme", homepage_url="https://app.acmefinance.io")
    assert m is not None and m.platform == "bugcrowd"


def test_match_by_distinctive_name() -> None:
    m = bd.match(_index(), display_name="Berachain", target_name="berachain")
    assert m is not None and m.name == "Berachain"


def test_no_match_short_name() -> None:
    # A short name (<5 chars) must not name-match, to avoid web2 false positives.
    idx = bd.build_index([{"companies": [{"company": "Save", "url": "https://x.com", "rewards": ["Bounty"]}]}])
    assert bd.match(idx, display_name="Save", target_name="save") is None


def test_no_match_unrelated() -> None:
    assert bd.match(_index(), display_name="BULK", target_name="bulk") is None


# --- async wrapper ---------------------------------------------------------


async def test_match_directory_returns_bounty_entry(monkeypatch: Any) -> None:
    async def fake_load(client: Any = None) -> list[bd.DirectoryProgram]:
        return _index()

    monkeypatch.setattr(bd, "load_index", fake_load)
    entry = await bd.match_directory(display_name="0x", homepage_url="https://0x.org")
    assert entry is not None
    assert entry.platform == "selfhosted"
    assert entry.max_payout_usd == 1000000
    assert entry.slugs == ()  # directory entries carry no curated slugs


async def test_match_directory_none(monkeypatch: Any) -> None:
    async def fake_load(client: Any = None) -> list[bd.DirectoryProgram]:
        return _index()

    monkeypatch.setattr(bd, "load_index", fake_load)
    assert await bd.match_directory(display_name="Nonexistent Protocol") is None
