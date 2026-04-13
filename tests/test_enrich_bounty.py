"""Tests for the bounty registry seeds file and matcher."""

from __future__ import annotations

from tvl_scanner.enrich.bounty import BountyEntry, _normalize, load_registry, match


def test_normalize_lowercase_and_strip() -> None:
    assert _normalize("  Aave V3 ") == "aave-v3"
    assert _normalize("UNISWAP") == "uniswap"
    assert _normalize("Camelot V3") == "camelot-v3"


def test_load_registry_not_empty() -> None:
    """The seeds file must parse cleanly and contain real entries."""
    registry = load_registry()
    assert len(registry) > 20  # we seed with 30+
    assert all(isinstance(e, BountyEntry) for e in registry)
    assert all(e.name and e.slugs for e in registry)
    # Clear the lru_cache so other tests see a clean state
    load_registry.cache_clear()


def test_match_known_protocol_by_display_name() -> None:
    load_registry.cache_clear()
    hit = match(display_name="Aave")
    assert hit is not None
    assert hit.name == "Aave"
    assert hit.platform == "immunefi"
    assert hit.max_payout_usd == 1_000_000


def test_match_known_protocol_by_slug() -> None:
    load_registry.cache_clear()
    hit = match(defillama_slug="aave-v3")
    assert hit is not None
    assert hit.name == "Aave"


def test_match_case_insensitive() -> None:
    load_registry.cache_clear()
    hit = match(display_name="UNISWAP")
    assert hit is not None
    assert hit.name == "Uniswap"


def test_match_unknown_protocol_returns_none() -> None:
    load_registry.cache_clear()
    assert match(display_name="SomeFreshUnlistedFork") is None
    assert match(display_name="Random New Vault") is None


def test_match_empty_inputs_returns_none() -> None:
    load_registry.cache_clear()
    assert match() is None
    assert match(display_name="") is None
    assert match(display_name=None, defillama_slug=None) is None


def test_registry_includes_expected_protocols() -> None:
    """Spot-check that the big names we rely on are present."""
    load_registry.cache_clear()
    registry = load_registry()
    names = {e.name for e in registry}
    required = {"Aave", "Compound", "Uniswap", "Curve Finance", "Pendle", "Silo Finance",
                "Morpho", "Jito", "Jupiter", "Raydium"}
    missing = required - names
    assert not missing, f"Registry missing required entries: {missing}"
