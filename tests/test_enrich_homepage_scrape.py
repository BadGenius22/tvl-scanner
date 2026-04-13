"""Tests for the homepage scrape regex extractor (Batch K)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from pytest_httpx import HTTPXMock

from tvl_scanner.enrich.homepage_scrape import (
    AUDIT_FIRM_PHRASES,
    WRAPPER_PHRASES,
    HomepageScrapeResult,
    scrape_homepage,
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
