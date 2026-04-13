"""Tests for the curated github seed registry (Batch I fix #1)."""

from __future__ import annotations

from tvl_scanner.enrich.github_registry import load_github_registry, lookup


def test_load_registry_not_empty() -> None:
    """The seeds file must parse cleanly and contain real entries."""
    load_github_registry.cache_clear()
    registry = load_github_registry()
    assert len(registry) > 50  # we seed with ~100 (entries cover aliases)
    assert all(isinstance(k, str) and isinstance(v, str) for k, v in registry.items())
    assert all("github.com" in v for v in registry.values())


def test_load_registry_includes_expected_big_protocols() -> None:
    """Spot-check that the seeds file covers the protocols we see in scans."""
    load_github_registry.cache_clear()
    registry = load_github_registry()
    for expected in (
        "pendle", "aave", "compound", "uniswap", "curve", "balancer",
        "makerdao", "spark", "silo", "morpho", "gearbox", "lido",
        "synapse", "hyperlane", "maple", "convex", "yearn", "beefy",
        "jito", "marinade", "kamino", "drift", "jupiter", "raydium", "orca",
    ):
        assert expected in registry, f"missing expected slug: {expected}"


def test_lookup_case_insensitive() -> None:
    load_github_registry.cache_clear()
    assert lookup("PENDLE") == lookup("pendle")
    assert lookup("  pendle  ") == lookup("pendle")


def test_lookup_missing_returns_none() -> None:
    load_github_registry.cache_clear()
    assert lookup("not-a-real-protocol-xyz-123") is None
    assert lookup("") is None
    assert lookup(None) is None


def test_lookup_alias_resolves_to_same_repo() -> None:
    """pendle and pendle-v2 should point at the same canonical repo."""
    load_github_registry.cache_clear()
    assert lookup("pendle") == lookup("pendle-v2")
    assert lookup("aave") == lookup("aave-v3")
