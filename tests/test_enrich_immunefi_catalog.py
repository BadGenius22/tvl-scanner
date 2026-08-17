"""Tests for bounty-first discovery from the live Immunefi catalogue."""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import AsyncMock, patch

from tvl_scanner.enrich.defillama import DefiLlamaCatalog
from tvl_scanner.enrich.immunefi_catalog import (
    _audit_signal,
    _build_candidate,
    _chain_from_explorer,
    _ecosystem_chain,
    _has_unmapped_mainnet_explorer,
    _is_testnet,
    _languages,
    _pick_scope,
    _tvl_on_scope_chain,
    discover_from_immunefi_catalog,
)
from tvl_scanner.enrich.immunefi_filter import REASON_NO_CHAIN
from tvl_scanner.models import Chain, DiscoverySource, Language

EVM = "0x" + "ab" * 20  # 40 hex chars
ALL = set(Chain)


def _sc(url: str) -> dict[str, Any]:
    return {"type": "smart_contract", "url": url}


def _program(
    *,
    slug: str = "royco",
    project: str = "Royco",
    kyc: bool = False,
    max_bounty: Any = 250_000,
    ecosystem: list[str] | None = None,
    language: list[str] | None = None,
    assets: list[dict[str, Any]] | None = None,
    audits: list[dict[str, Any]] | None = None,
    github: str | None = None,
    launch: str | None = "2026-02-17T10:24:00.000Z",
) -> dict[str, Any]:
    return {
        "slug": slug,
        "project": project,
        "kyc": kyc,
        "maxBounty": max_bounty,
        "ecosystem": ecosystem if ecosystem is not None else ["ETH"],
        "language": language if language is not None else ["Solidity"],
        "assets": assets
        if assets is not None
        else [_sc(f"https://etherscan.io/address/{EVM}#code")],
        "audits": audits or [],
        "githubUrl": github,
        "launchDate": launch,
        "projectType": ["Defi"],
    }


def _catalog(protocols: list[dict[str, Any]]) -> DefiLlamaCatalog:
    c = DefiLlamaCatalog()
    c._protocols = protocols
    c._loaded = True
    return c


# --- chain inference ---------------------------------------------------------


def test_chain_from_explorer_maps_domains() -> None:
    assert _chain_from_explorer("https://etherscan.io/address/0xabc") == Chain.ETHEREUM
    assert _chain_from_explorer("https://arbiscan.io/address/0xabc") == Chain.ARBITRUM
    assert _chain_from_explorer("https://basescan.org/address/0xabc") == Chain.BASE
    assert _chain_from_explorer("https://polygonscan.com/x") == Chain.POLYGON
    assert _chain_from_explorer("https://solscan.io/account/x") == Chain.SOLANA
    assert _chain_from_explorer("https://snowtrace.io/x") is None  # avalanche unsupported


def test_optimism_matched_before_etherscan_suffix() -> None:
    # optimistic.etherscan.io embeds "etherscan.io" — must resolve to OPTIMISM.
    assert _chain_from_explorer("https://optimistic.etherscan.io/address/0xabc") == Chain.OPTIMISM


def test_is_testnet_flags_non_mainnet_subdomains() -> None:
    assert _is_testnet("https://hoodi.etherscan.io/address/0xabc")
    assert _is_testnet("https://sepolia.basescan.org/x")
    assert not _is_testnet(f"https://etherscan.io/address/{EVM}")


def test_is_testnet_flags_solana_cluster_query() -> None:
    """TruYields listed explorer.solana.com/…?cluster=devnet as a live contract."""
    assert _is_testnet(
        "https://explorer.solana.com/address/6EZAJVrNQdnBJU6ULxXSDaEoK6fN7C3iXTCkZKRWDdGM?cluster=devnet"
    )
    assert not _is_testnet("https://explorer.solana.com/address/6EZAJVrNQdnBJU6ULxXSDaEoK6fN7C3iXTCkZKRWDdGM")


# --- scope selection ---------------------------------------------------------


def test_pick_scope_extracts_evm_address_and_chain() -> None:
    chain, addr, count = _pick_scope(_program(), ALL)
    assert chain == Chain.ETHEREUM
    assert addr == EVM
    assert count == 1


def test_pick_scope_skips_testnet_and_placeholder_assets() -> None:
    prog = _program(
        assets=[
            _sc("https://immunefi.com"),  # Primacy-of-Impact placeholder
            _sc(f"https://hoodi.etherscan.io/address/{EVM}"),  # testnet
            _sc(f"https://arbiscan.io/address/{EVM}#code"),  # real
        ]
    )
    chain, addr, count = _pick_scope(prog, ALL)
    assert chain == Chain.ARBITRUM
    assert addr == EVM
    assert count == 1  # placeholder AND testnet excluded from the in-scope count


def test_pick_scope_returns_none_when_chain_not_configured() -> None:
    chain, addr, _ = _pick_scope(_program(), {Chain.ARBITRUM})
    assert chain is None and addr is None


def test_unmapped_explorer_is_not_an_ethereum_target() -> None:
    """katanascan.com is Katana L2, not Ethereum, even if ecosystem says ETH."""
    prog = _program(
        slug="katana",
        project="Katana",
        ecosystem=["ETH"],
        assets=[_sc("https://katanascan.com/address/" + EVM)],
    )
    assert _has_unmapped_mainnet_explorer(prog, ALL) is True
    assert _build_candidate(prog, _catalog([]), ALL, date(2026, 8, 17)) is None


def test_majority_unmapped_explorers_are_not_an_l1_target() -> None:
    """Katana: ~18 katanascan rows + a handful of L1 OFT/bridge etherscan links.

    Picking the first mapped explorer made it an Ethereum program with $0 TVL.
    The L2 majority is the program; skip it.
    """
    katana = "https://katanascan.com/address/"
    prog = _program(
        slug="katana",
        project="Katana",
        ecosystem=["ETH"],
        assets=[
            _sc(katana + "0x" + "11" * 20),
            _sc(katana + "0x" + "22" * 20),
            _sc(katana + "0x" + "33" * 20),
            _sc(f"https://etherscan.io/address/{EVM}"),  # L1 OFT leftover
        ],
    )
    assert _has_unmapped_mainnet_explorer(prog, ALL) is True
    assert _build_candidate(prog, _catalog([]), ALL, date(2026, 8, 17)) is None


def test_testnet_explorer_beats_ecosystem_list_order() -> None:
    """TruYields: Solana devnet + github, ecosystem starts with ETH."""
    prog = _program(
        slug="trufin",
        project="TruYields",
        ecosystem=["ETH", "Polygon", "Solana"],
        language=["Solidity", "Rust"],
        assets=[
            _sc(
                "https://explorer.solana.com/address/"
                "6EZAJVrNQdnBJU6ULxXSDaEoK6fN7C3iXTCkZKRWDdGM?cluster=devnet"
            ),
            {
                "type": "smart_contract",
                "url": "https://github.com/TruFin-io/smart-contracts-solana-public",
            },
        ],
    )
    cand = _build_candidate(prog, _catalog([]), ALL, date(2026, 8, 17))
    assert cand is not None
    assert cand.chain == Chain.SOLANA


def test_github_only_program_still_uses_ecosystem_fallback() -> None:
    prog = _program(
        ecosystem=["Solana"],
        assets=[{"type": "smart_contract", "url": "https://github.com/TruFin-io/smart-contracts-solana-public"}],
    )
    assert _has_unmapped_mainnet_explorer(prog, ALL) is False
    cand = _build_candidate(prog, _catalog([]), ALL, date(2026, 8, 17))
    assert cand is not None
    assert cand.chain == Chain.SOLANA


def test_ecosystem_chain_fallback() -> None:
    assert _ecosystem_chain(_program(ecosystem=["ETH"]), ALL) == Chain.ETHEREUM
    assert _ecosystem_chain(_program(ecosystem=["Solana"]), ALL) == Chain.SOLANA
    assert _ecosystem_chain(_program(ecosystem=["Avalanche"]), ALL) is None


# --- audit signal ------------------------------------------------------------


def test_audit_signal_counts_and_notes() -> None:
    count, urls, note = _audit_signal(
        _program(
            audits=[
                {"url": "https://github.com/x/audit", "date": "2026-02-17"},
                {"url": "not-a-url", "date": "2025-11-01"},
            ]
        )
    )
    assert count == 2
    assert urls == ["https://github.com/x/audit"]
    assert note is not None and "2 prior audit" in note and "2026-02-17" in note


def test_audit_signal_empty() -> None:
    assert _audit_signal(_program(audits=[])) == (0, [], None)


# --- candidate build ---------------------------------------------------------


def _dl(slug: str = "royco", name: str = "Royco", tvl: float = 5_000_000, audits: Any = 2) -> dict[str, Any]:
    return {"slug": slug, "name": name, "tvl": tvl, "category": "Lending", "audits": audits}


def test_build_candidate_happy_path() -> None:
    cand = _build_candidate(_program(), _catalog([_dl()]), ALL, date(2026, 7, 15))
    assert cand is not None
    assert cand.chain == Chain.ETHEREUM
    assert cand.address == EVM
    assert cand.onchain_address == f"ethereum:{EVM}"
    assert cand.tvl_usd == 5_000_000
    assert cand.source == DiscoverySource.IMMUNEFI_CATALOG
    assert cand.bounty_program == "immunefi"
    assert cand.bounty_max_payout_usd == 250_000
    assert cand.bounty_url == "https://immunefi.com/bug-bounty/royco"
    assert cand.defillama_slug == "royco"
    assert cand.defillama_audit_count == 2  # max(DL=2, immunefi=0)
    assert Language.SOLIDITY in cand.languages


def test_build_candidate_no_longer_filters() -> None:
    """The builder decides coverage only; every user constraint is ProgramFilter's.

    Keeping filtering out of the builder is what lets each drop carry a named
    reason in the funnel instead of vanishing as a bare None.
    """
    assert _build_candidate(_program(kyc=True), _catalog([]), ALL, date(2026, 7, 15)) is not None
    assert (
        _build_candidate(_program(max_bounty=1_000), _catalog([]), ALL, date(2026, 7, 15))
        is not None
    )


def test_build_candidate_unsupported_chain_skipped() -> None:
    prog = _program(ecosystem=["Avalanche"], assets=[_sc("https://snowtrace.io/address/0xabc")])
    assert _build_candidate(prog, _catalog([]), ALL, date(2026, 7, 15)) is None


def test_build_candidate_synthetic_address_when_no_evm() -> None:
    # No smart-contract assets, Solana ecosystem → synthetic address, no onchain_address.
    prog = _program(ecosystem=["Solana"], assets=[])
    cand = _build_candidate(prog, _catalog([]), ALL, date(2026, 7, 15))
    assert cand is not None
    assert cand.chain == Chain.SOLANA
    assert cand.address == "immunefi:royco"
    assert cand.onchain_address is None
    assert cand.tvl_usd == 0.0  # no DefiLlama match


def test_build_candidate_folds_immunefi_audits_when_no_dl() -> None:
    prog = _program(audits=[{"date": "2026-01-01"}, {"date": "2026-02-01"}, {"date": "2026-03-01"}])
    cand = _build_candidate(prog, _catalog([]), ALL, date(2026, 7, 15))
    assert cand is not None
    assert cand.defillama_audit_count == 3
    assert cand.defillama_audit_note is not None and "3 prior audit" in cand.defillama_audit_note


# --- end-to-end discovery ----------------------------------------------------


async def test_discover_skips_unsupported_and_resolves_deploy_date() -> None:
    supported = _program(slug="royco", project="Royco")
    unsupported = _program(slug="ava", project="Ava", ecosystem=["Avalanche"], assets=[_sc("https://snowtrace.io/x")])
    with (
        patch("tvl_scanner.enrich.immunefi.fetch_raw", new=AsyncMock(return_value=[supported, unsupported])),
        patch(
            "tvl_scanner.enrich.immunefi_catalog.fetch_creation_dates_batch",
            new=AsyncMock(return_value={EVM.lower(): date(2026, 6, 1)}),
        ),
    ):
        results, funnel = await discover_from_immunefi_catalog(
            catalog=_catalog([_dl()]), scan_date=date(2026, 7, 15)
        )

    assert len(results) == 1  # the Avalanche-only program is skipped
    # The skip is attributed, not silent.
    assert funnel.fetched == 2
    assert funnel.dropped[REASON_NO_CHAIN] == 1
    cand = results[0]
    assert cand.target_name == "royco"
    assert cand.source == DiscoverySource.IMMUNEFI_CATALOG
    assert cand.first_seen == date(2026, 6, 1)  # deploy date overrode launchDate


async def test_discover_empty_catalogue_returns_empty() -> None:
    with patch("tvl_scanner.enrich.immunefi.fetch_raw", new=AsyncMock(return_value=[])):
        results, funnel = await discover_from_immunefi_catalog(catalog=_catalog([]))
    assert results == []
    assert funnel.fetched == 0


# ---- Bounty program profile attachment (12-criteria rubric) ----


def test_build_candidate_attaches_the_bounty_profile() -> None:
    program = _program(
        max_bounty=250_000,
        launch="2026-02-17T10:24:00.000Z",
        assets=[
            {
                "type": "smart_contract",
                "url": f"https://etherscan.io/address/{EVM}#code",
                "addedAt": "2026-03-20T00:00:00.000Z",
                "revision": 1,
            }
        ],
    )
    program.update(
        {
            "updatedDate": "2026-04-01T00:00:00.000Z",
            "rewards": [
                {
                    "severity": "critical",
                    "assetType": "smart_contract",
                    "rewardModel": "range",
                    "minReward": 50_000,
                    "maxReward": 250_000,
                    "rewardCalculationPercentage": 10,
                }
            ],
            "knownIssues": [{"description": "Known rounding drift."}],
        }
    )
    cand = _build_candidate(
        program, _catalog([]), ALL, date(2026, 4, 13)
    )

    assert cand is not None
    profile = cand.bounty_profile
    assert profile is not None
    assert profile.max_bounty_usd == 250_000
    assert profile.critical_min_usd == 50_000
    assert profile.program_age_days == 55
    assert profile.days_since_program_update == 12
    assert profile.known_issue_count == 1
    assert profile.smart_contract_assets == 1
    assert profile.assets_added_90d == 1
    assert profile.assets_revised == 1
    # TVL is unresolved without a DefiLlama match, so the payout ratio stays
    # unknown rather than dividing by a 0.0 placeholder.
    assert cand.tvl_resolved is False
    assert profile.max_payout_vs_tvl_pct is None


def test_languages_prefer_program_list_over_chain_default() -> None:
    """A Rust program with an Ethereum explorer row is Rust, not [solidity, rust]."""
    prog = _program(language=["Rust"], ecosystem=["ETH"])
    assert _languages(prog, Chain.ETHEREUM) == [Language.RUST]


def test_languages_fall_back_to_chain_default_when_unpublished() -> None:
    prog = _program(language=[])
    assert _languages(prog, Chain.ETHEREUM) == [Language.SOLIDITY]
    assert _languages(prog, Chain.SOLANA) == [Language.RUST]


def test_tvl_uses_in_scope_chain_not_protocol_total() -> None:
    """Regression: Immunefi-scan inherited the catalog path's SUBFROST bug.

    A Bitcoin metaprotocol with a thin Ethereum explorer row must report the
    Ethereum leg, not the $7.3M protocol-wide total.
    """
    dl = {
        "slug": "subfrost",
        "name": "SUBFROST",
        "tvl": 7_308_915.58,
        "chainTvls": {"Ethereum": 6_050.08, "Bitcoin": 7_302_865.50},
        "category": "Bridge",
    }
    tvl, resolved = _tvl_on_scope_chain(dl, Chain.ETHEREUM)
    assert resolved is True
    assert tvl == 6_050.08


def test_tvl_unresolved_when_money_sits_off_the_scope_chain() -> None:
    """If chainTvls has no in-scope leg, do not steal the protocol total."""
    dl = {
        "slug": "offchain-only",
        "tvl": 50_000_000.0,
        "chainTvls": {"Bitcoin": 50_000_000.0},
    }
    tvl, resolved = _tvl_on_scope_chain(dl, Chain.ETHEREUM)
    assert resolved is False
    assert tvl == 0.0


def test_tvl_falls_back_to_total_when_no_chain_tvls() -> None:
    tvl, resolved = _tvl_on_scope_chain(
        {"slug": "royco", "tvl": 5_000_000.0}, Chain.ETHEREUM
    )
    assert resolved is True
    assert tvl == 5_000_000.0


def test_build_candidate_does_not_inherit_off_chain_tvl() -> None:
    prog = _program(slug="subfrost", project="SUBFROST")
    catalog = _catalog(
        [
            {
                "slug": "subfrost",
                "name": "SUBFROST",
                "tvl": 7_308_915.58,
                "chainTvls": {"Ethereum": 6_050.08, "Bitcoin": 7_302_865.50},
                "category": "Bridge",
            }
        ]
    )
    cand = _build_candidate(prog, catalog, ALL, date(2026, 8, 10))
    assert cand is not None
    assert cand.chain == Chain.ETHEREUM
    assert cand.tvl_usd == 6_050.08
    assert cand.tvl_resolved is True
    # $6k is below the ratio floor, so criterion 3 must not see 400,000%.
    assert cand.bounty_profile is not None
    assert cand.bounty_profile.max_payout_vs_tvl_pct is None


def test_payout_ratio_resolves_when_defillama_supplies_tvl() -> None:
    cand = _build_candidate(
        _program(max_bounty=250_000),
        _catalog([{"name": "Royco", "slug": "royco", "tvl": 25_000_000, "category": "Yield"}]),
        ALL,
        date(2026, 4, 13),
    )
    assert cand is not None
    assert cand.tvl_resolved is True
    assert cand.bounty_profile is not None
    assert cand.bounty_profile.max_payout_vs_tvl_pct == 1.0


def test_profile_survives_a_program_with_no_optional_sections() -> None:
    """The catalogue's thin records must still produce a usable profile."""
    cand = _build_candidate(
        _program(audits=[], github=None),
        _catalog([]),
        ALL,
        date(2026, 4, 13),
    )
    assert cand is not None
    assert cand.bounty_profile is not None
    assert cand.bounty_profile.known_issue_count == 0
    assert cand.bounty_profile.audit_count == 0
