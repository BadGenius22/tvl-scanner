"""Tests for the homepage scrape regex extractor (Batch K + K2 fallback)."""

from __future__ import annotations

import re
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from pytest_httpx import HTTPXMock

from tvl_scanner.enrich.homepage_scrape import (
    AUDIT_FIRM_PHRASES,
    WRAPPER_PHRASES,
    HomepageScrapeResult,
    _slugify_display_name,
    derive_candidate_urls,
    scrape_homepage,
    scrape_homepage_with_fallback,
)


# Synthetic homepage HTML samples
HYPERLANE_HTML = """
<html><head><title>Hyperlane</title></head>
<body>
<h1>Hyperlane is the universal interchain protocol</h1>
<p>Our protocol has been audited by Trail of Bits, Halborn, and Zellic.</p>
<a href="https://docs.hyperlane.xyz/security">Security</a>
</body></html>
"""

JAGPOOL_HTML = """
<html><head><title>JagPool</title></head>
<body>
<p>JagPool utilizes the Solana native stake pool program to manage all fund operations.</p>
</body></html>
"""

CUSTOM_PROTOCOL_HTML = """
<html><head><title>Custom Protocol</title></head>
<body>
<p>Welcome to our brand new vault! Built from scratch by our core team.</p>
</body></html>
"""

NO_AUDIT_NO_WRAPPER = "<html><body>Just a homepage with nothing interesting.</body></html>"


def test_pattern_dictionaries_are_non_empty() -> None:
    """Sanity: the regex catalogs must contain at least the canonical entries."""
    assert any(p.pattern == "native stake pool program" for p in WRAPPER_PHRASES)
    # Trail of Bits via either phrasing
    tags = set(AUDIT_FIRM_PHRASES.values())
    assert "trail_of_bits" in tags
    assert "halborn" in tags
    assert "zellic" in tags


async def test_scrape_homepage_invalid_url_returns_empty() -> None:
    result = await scrape_homepage(None)
    assert not result.fetched
    assert result.wrapper_matches == []
    assert result.audit_firm_matches == []

    result = await scrape_homepage("not-a-url")
    assert not result.fetched

    result = await scrape_homepage("")
    assert not result.fetched


async def test_scrape_homepage_extracts_audit_firms(httpx_mock: HTTPXMock) -> None:
    """Hyperlane-style page mentioning ToB / Halborn / Zellic must yield 3 hits."""
    httpx_mock.add_response(url="https://www.hyperlane.xyz/", text=HYPERLANE_HTML)
    result = await scrape_homepage("https://www.hyperlane.xyz/")
    assert result.fetched is True
    assert "trail_of_bits" in result.audit_firm_matches
    assert "halborn" in result.audit_firm_matches
    assert "zellic" in result.audit_firm_matches


async def test_scrape_homepage_extracts_wrapper_phrase(httpx_mock: HTTPXMock) -> None:
    """JagPool-style page citing the SPL stake pool program must trigger wrapper match."""
    httpx_mock.add_response(url="https://www.jagpool.xyz/", text=JAGPOOL_HTML)
    result = await scrape_homepage("https://www.jagpool.xyz/")
    assert result.fetched is True
    assert "spl_stake_pool" in result.wrapper_matches


async def test_scrape_homepage_clean_page_yields_no_matches(
    httpx_mock: HTTPXMock,
) -> None:
    """A page with no audit/wrapper claims should return empty match lists."""
    httpx_mock.add_response(url="https://example.com/", text=CUSTOM_PROTOCOL_HTML)
    result = await scrape_homepage("https://example.com/")
    assert result.fetched is True
    assert result.audit_firm_matches == []
    assert result.wrapper_matches == []


async def test_scrape_homepage_404_returns_empty(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="https://gone.example.com/", status_code=404, text="not found")
    result = await scrape_homepage("https://gone.example.com/")
    assert result.fetched is False
    assert result.wrapper_matches == []
    assert result.audit_firm_matches == []


# ─────────────────────────────────────────────────────────────────────────────
# BATCH K2: multi-URL fallback tests
# ─────────────────────────────────────────────────────────────────────────────


def test_slugify_display_name_strips_suffixes() -> None:
    assert _slugify_display_name("SoDEX Bridge") == "sodex"
    assert _slugify_display_name("Pendle Finance") == "pendle"
    assert _slugify_display_name("Aave V3") == "aave"
    assert _slugify_display_name("Spark Savings") == "spark"
    assert _slugify_display_name("Hyperlane") == "hyperlane"
    assert _slugify_display_name("Synapse Protocol") == "synapse"


def test_slugify_display_name_handles_edge_cases() -> None:
    assert _slugify_display_name("") is None
    assert _slugify_display_name("Bridge") is None  # only suffix word
    assert _slugify_display_name("V3") is None  # version-only
    assert _slugify_display_name("a") is None  # single character
    assert _slugify_display_name("123") is None  # all digits


def test_derive_candidate_urls_includes_input_url() -> None:
    """The input base_url must be the first candidate."""
    urls = derive_candidate_urls("SoDEX Bridge", "https://ssi.sosovalue.com/share/MAG7.ssi/abc")
    assert urls[0] == "https://ssi.sosovalue.com/share/MAG7.ssi/abc"


def test_derive_candidate_urls_strips_subdomain_prefix() -> None:
    """ssi.sosovalue.com → also try sosovalue.com root + audit paths."""
    urls = derive_candidate_urls("SoDEX Bridge", "https://ssi.sosovalue.com/share/abc")
    assert "https://sosovalue.com" in urls
    assert "https://sosovalue.com/security" in urls


def test_derive_candidate_urls_generates_slug_based_domains() -> None:
    """For SoDEX Bridge, also try sodex.com / sodex.io / sodex.xyz / etc."""
    urls = derive_candidate_urls("SoDEX Bridge", None)
    assert any("sodex.com" in u for u in urls)
    assert any("sodex.com/security" in u for u in urls)


def test_derive_candidate_urls_caps_total() -> None:
    """No more than 15 URLs to bound HTTP cost."""
    urls = derive_candidate_urls("SoDEX Bridge", "https://ssi.sosovalue.com/share/abc")
    assert len(urls) <= 15


def test_derive_candidate_urls_handles_no_inputs() -> None:
    assert derive_candidate_urls(None, None) == []
    assert derive_candidate_urls("", None) == []


async def test_fallback_returns_phase1_when_phase1_succeeds(
    httpx_mock: HTTPXMock,
) -> None:
    """If the base URL has audit text, Phase 2 should never fire — we register
    only one mock and verify it succeeds without unmatched-request errors.
    """
    httpx_mock.add_response(
        url="https://www.hyperlane.xyz/",
        text="<html>Audited by Trail of Bits, Halborn, and Zellic.</html>",
    )
    result = await scrape_homepage_with_fallback(
        "https://www.hyperlane.xyz/", "Hyperlane"
    )
    assert result.fetched is True
    assert "trail_of_bits" in result.audit_firm_matches


async def test_fallback_tries_derived_urls_when_phase1_empty(
    httpx_mock: HTTPXMock,
) -> None:
    """The SoDEX case: base URL is wrong, derived sodex.com/security has audit text."""
    # Phase 1 — invite link returns empty page with no audit text
    httpx_mock.add_response(
        url="https://ssi.sosovalue.com/share/MAG7.ssi/abc",
        text="<html><body>Welcome to SosoValue!</body></html>",
    )
    # Phase 2 — sodex.com/security returns audit text
    httpx_mock.add_response(
        url="https://sodex.com/security",
        text="<html>SoDEX has been audited by Halborn and BlockSec.</html>",
        is_reusable=True,
    )
    # Catch-all 404 for everything else (unmatched derived URL attempts)
    httpx_mock.add_response(
        url=re.compile(r"^https://(?!sodex\.com/security$).*"),
        status_code=404,
        text="",
        is_reusable=True,
    )

    result = await scrape_homepage_with_fallback(
        "https://ssi.sosovalue.com/share/MAG7.ssi/abc",
        "SoDEX Bridge",
        max_attempts=8,
    )
    assert result.fetched is True
    assert "halborn" in result.audit_firm_matches
    assert result.url == "https://sodex.com/security"


async def test_fallback_returns_empty_when_nothing_succeeds(
    httpx_mock: HTTPXMock,
) -> None:
    """If every URL 404s, return the empty primary result."""
    httpx_mock.add_response(
        url=re.compile(r"^https://.*$"), status_code=404, text="", is_reusable=True
    )
    result = await scrape_homepage_with_fallback(
        "https://gone.example.com/", "Ghost Protocol"
    )
    assert result.fetched is False
    assert result.audit_firm_matches == []
    assert result.wrapper_matches == []
