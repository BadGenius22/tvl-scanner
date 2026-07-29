"""Tests for the homepage scrape regex extractor (Batch K + K2 fallback)."""

from __future__ import annotations

import re

from pytest_httpx import HTTPXMock

from tvl_scanner.enrich.homepage_scrape import (
    AUDIT_FIRM_PHRASES,
    WRAPPER_PHRASES,
    _extract_audit_relevant_links,
    _registered_domain,
    _slugify_display_name,
    derive_candidate_urls,
    github_url_matches_protocol,
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
    # 2026-05-26: rho-x-lp-vault regression — these firms had been missing.
    assert "zokyo" in tags
    assert "oxor" in tags
    assert "ottersec" in tags
    assert "cantina" in tags
    assert "hacken" in tags


# Synthetic rho.trading-style page: audit firm logos with direct links to
# the audit artifact, where the firm name appears in the URL but not as
# plaintext body text. This is the SPA pattern that defeated the original
# AUDIT_FIRM_PHRASES regex on rho.trading and caused rho-x-lp-vault to
# surface as a false-positive "under-audited" candidate in 2026-05-25-scan.
RHO_TRADING_AUDITS_HTML = """
<html><head><title>Rho — Yield</title></head>
<body>
<section class="security-section">
<h2 class="security-section-title">Security Audits</h2>
<p>We have successfully completed a smart contract audit with leading firms.</p>
<a href="https://audits.oxor.io/reports/-NsF0vIwYyzQJhrgL2nf" class="audits-logo-container">
  <img src="/oxor_logo.svg" alt="" class="security-logo"/>
</a>
<a href="https://github.com/zokyo-sec/audit-reports/blob/main/Rho%20Labs/Rho_Labs_Zokyo_audit_report_Sep23rd_2025.pdf" class="audits-logo-container">
  <img src="/zokyo_logo.svg" alt="" class="security-logo"/>
</a>
<a href="https://www.halborn.com/audits/rho-labs/vault-contracts-v2-9d7cbb" class="audits-logo-container">
  <img src="/halborn_logo.svg" alt="" class="security-logo"/>
</a>
</section>
</body></html>
"""


async def test_scrape_homepage_catches_rho_trading_audit_links(
    httpx_mock: HTTPXMock,
) -> None:
    """Regression for rho-x-lp-vault: the rho.trading homepage embeds Halborn,
    Zokyo, and oXor audit logos via direct anchor links to the audit reports.
    The plaintext "Halborn" word appears in body text, but "Zokyo" and "oXor"
    appear ONLY inside URLs. The AUDIT_FIRM_URL_PATTERNS fingerprint pass
    must catch all three.
    """
    httpx_mock.add_response(
        url="https://www.rho.trading/", text=RHO_TRADING_AUDITS_HTML
    )
    result = await scrape_homepage("https://www.rho.trading/")
    assert result.fetched is True
    assert "halborn" in result.audit_firm_matches
    assert "zokyo" in result.audit_firm_matches
    assert "oxor" in result.audit_firm_matches


async def test_scrape_homepage_catches_audit_url_without_firm_name_text(
    httpx_mock: HTTPXMock,
) -> None:
    """URL fingerprint regex must fire even when the firm name appears ONLY
    inside the URL (no plaintext mention, no audit-context word required).
    This is the hardest SPA case — server-rendered HTML carries the link
    but the rest of the page is JS-rendered.
    """
    html = """
    <html><body>
    <a href="https://audits.oxor.io/reports/abc"><img src="/logo.svg"/></a>
    <a href="https://github.com/zokyo-sec/audit-reports/blob/main/Foo.pdf"><img src="/z.svg"/></a>
    </body></html>
    """
    httpx_mock.add_response(url="https://example.com/", text=html)
    result = await scrape_homepage("https://example.com/")
    assert result.fetched is True
    assert "oxor" in result.audit_firm_matches
    assert "zokyo" in result.audit_firm_matches


async def test_scrape_homepage_truncation_cap_at_400k(httpx_mock: HTTPXMock) -> None:
    """rho.trading is 204KB — the audit logos live at byte ~118K. With the
    original 200KB cap, a slightly larger page would push firms out of range.
    The current 400KB cap gives meaningful headroom. Verify a 300KB page
    with firms past the 200K mark still triggers detection.
    """
    padding = "<div>." * 35_000  # ~245KB of filler in front
    html = (
        "<html><body>" + padding +
        "<p>Audited by</p>"
        "<a href='https://www.halborn.com/audits/foo/bar'>halborn</a>"
        "</body></html>"
    )
    assert 200_000 < len(html) < 400_000, f"test fixture out of range: {len(html)}"
    httpx_mock.add_response(url="https://big.example.com/", text=html)
    result = await scrape_homepage("https://big.example.com/")
    assert result.fetched is True
    assert "halborn" in result.audit_firm_matches


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
    """Ordered list is bounded at 50 entries (15 → 25 in Batch L when
    _AUDIT_PATHS grew to 18; → 50 when G1 added docs./app. subdomain probes).
    The real per-scan HTTP budget is enforced by max_attempts, not this cap —
    this only keeps the ordered candidate list bounded."""
    urls = derive_candidate_urls("SoDEX Bridge", "https://ssi.sosovalue.com/share/abc")
    assert len(urls) <= 50


def test_derive_candidate_urls_includes_deep_nesting() -> None:
    """Batch L: sodex.com/documentation/custody-and-security/audits must be
    a derived candidate so the brand's actual audit path is reachable without
    needing the link-crawl fallback."""
    urls = derive_candidate_urls("SoDEX Bridge", None)
    assert any(
        u.endswith("/documentation/custody-and-security/audits") for u in urls
    ), f"deep audit path missing from derived URLs: {urls}"


def test_derive_candidate_urls_includes_common_nesting() -> None:
    """Spot-check that the expanded path set covers the most common patterns."""
    urls = derive_candidate_urls("SoDEX Bridge", None)
    suffixes_required = {
        "/audit",
        "/audits",
        "/security",
        "/security/audits",
        "/docs/audits",
        "/documentation/security/audits",
    }
    found = {
        suffix
        for suffix in suffixes_required
        if any(u.endswith(suffix) for u in urls)
    }
    assert found == suffixes_required, (
        f"missing path suffixes: {suffixes_required - found}"
    )


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


# ─────────────────────────────────────────────────────────────────────────────
# BATCH L: Phase 3 link-crawl fallback tests
# ─────────────────────────────────────────────────────────────────────────────


def test_registered_domain_extracts_last_two_labels() -> None:
    assert _registered_domain("sodex.com") == "sodex.com"
    assert _registered_domain("docs.sodex.com") == "sodex.com"
    assert _registered_domain("app.docs.sodex.com") == "sodex.com"
    assert _registered_domain("SODEX.COM") == "sodex.com"  # case-insensitive
    assert _registered_domain("localhost") == "localhost"  # single label


def test_extract_audit_links_finds_href_keyword() -> None:
    """Anchor whose href contains 'audit' must be picked up."""
    html = '''
    <a href="/documentation/custody-and-security/audits">Reports</a>
    <a href="/about">About</a>
    '''
    links = _extract_audit_relevant_links(html, "https://sodex.com/")
    assert links == ["https://sodex.com/documentation/custody-and-security/audits"]


def test_extract_audit_links_finds_anchor_text_keyword() -> None:
    """Anchor whose VISIBLE TEXT contains 'security' must be picked up even when
    the href is opaque (common with hash-routed SPAs and CMS-generated slugs)."""
    html = '''
    <a href="/page-1234">Security &amp; Audits</a>
    <a href="/page-5678">Team</a>
    '''
    links = _extract_audit_relevant_links(html, "https://sodex.com/")
    assert links == ["https://sodex.com/page-1234"]


def test_extract_audit_links_ranks_strong_audit_matches_higher() -> None:
    """An href containing 'audits' should rank above one only matching 'security'."""
    html = '''
    <a href="/security/overview">Security overview</a>
    <a href="/audits">Audit reports</a>
    <a href="/about/review">Reviews</a>
    '''
    links = _extract_audit_relevant_links(html, "https://example.com/")
    # /audits should be first — both href and anchor have the strong "audit" token
    assert links[0] == "https://example.com/audits"


def test_extract_audit_links_filters_external_domains() -> None:
    """Out-of-domain links (twitter, partner blogs) must never be followed."""
    html = '''
    <a href="https://twitter.com/sodex/status/audit-results">Audit announcement</a>
    <a href="https://halborn.com/audits/sodex">Halborn audit page</a>
    <a href="/security">Our security</a>
    '''
    links = _extract_audit_relevant_links(html, "https://sodex.com/")
    # Only the same-domain link is kept
    assert links == ["https://sodex.com/security"]


def test_extract_audit_links_allows_subdomain_of_same_registered_domain() -> None:
    """docs.sodex.com is fair game when called from sodex.com."""
    html = '<a href="https://docs.sodex.com/security/audits">Security audits</a>'
    links = _extract_audit_relevant_links(html, "https://sodex.com/")
    assert links == ["https://docs.sodex.com/security/audits"]


def test_extract_audit_links_dedupes_and_normalizes() -> None:
    html = '''
    <a href="/audits">Audits</a>
    <a href="/audits#latest">Latest audits</a>
    <a href="/audits">Audits again</a>
    '''
    links = _extract_audit_relevant_links(html, "https://example.com/")
    assert links == ["https://example.com/audits"]


def test_extract_audit_links_ignores_javascript_and_mailto() -> None:
    html = '''
    <a href="javascript:openAudit()">Audit</a>
    <a href="mailto:security@sodex.com">Email security</a>
    <a href="#audit-section">Jump to audits</a>
    <a href="/audits">Real audit page</a>
    '''
    links = _extract_audit_relevant_links(html, "https://sodex.com/")
    assert links == ["https://sodex.com/audits"]


def test_extract_audit_links_empty_inputs() -> None:
    assert _extract_audit_relevant_links("", "https://sodex.com/") == []
    assert _extract_audit_relevant_links("<html></html>", "") == []
    assert _extract_audit_relevant_links("<a href='/audits'>x</a>", "not-a-url") == []


async def test_phase3_link_crawl_finds_custom_audit_path(
    httpx_mock: HTTPXMock,
) -> None:
    """The full SoDEX case end-to-end:
    - DefiLlama base_url returns the brand homepage (no audit firm text directly)
    - Derived /security, /audits etc. all 404
    - But the homepage HTML links to /documentation/custody-and-security/audits
    - Phase 3 follows that link and finds 'audited by Halborn'
    """
    # Phase 1: brand homepage with nav link to custom audit path
    httpx_mock.add_response(
        url="https://sodex.com/",
        text='''<html><body>
            <nav>
              <a href="/team">Team</a>
              <a href="/documentation/custody-and-security/audits">Custody &amp; Security</a>
            </nav>
            <h1>SoDEX — bridge</h1>
        </body></html>''',
    )
    # The custom audit page actually carries the audit text
    httpx_mock.add_response(
        url="https://sodex.com/documentation/custody-and-security/audits",
        text="<html>SoDEX has undergone a security audit by Halborn in 2026.</html>",
        is_reusable=True,
    )
    # Catch-all 404 for derived URL attempts (Phase 2) and anything else
    httpx_mock.add_response(
        url=re.compile(
            r"^https://(?!sodex\.com/documentation/custody-and-security/audits$"
            r"|sodex\.com/$).*"
        ),
        status_code=404,
        text="",
        is_reusable=True,
    )

    result = await scrape_homepage_with_fallback(
        "https://sodex.com/",
        "SoDEX Bridge",
        max_attempts=20,
    )
    assert result.fetched is True
    assert "halborn" in result.audit_firm_matches
    assert result.url.endswith("/documentation/custody-and-security/audits")


async def test_phase3_skipped_when_phase1_empty_html(
    httpx_mock: HTTPXMock,
) -> None:
    """If Phase 1 returns 404/empty, there's no HTML to link-crawl — Phase 3
    must short-circuit cleanly and not raise."""
    httpx_mock.add_response(
        url=re.compile(r"^https://.*$"),
        status_code=404,
        text="",
        is_reusable=True,
    )
    result = await scrape_homepage_with_fallback(
        "https://nowhere.example.com/", "Nowhere Protocol", max_attempts=20
    )
    assert result.fetched is False
    assert result.audit_firm_matches == []


# ── github_url_matches_protocol — audit-attribution ownership guard ──────────


def test_github_url_matches_protocol_accepts_own_repo() -> None:
    assert github_url_matches_protocol(
        "https://github.com/autonomoussoftware/metronome-synth-audit",
        slug="metronome",
        display_name="Metronome",
    )


def test_github_url_matches_protocol_rejects_upstream_vendor_repo() -> None:
    """Regression: KAST's Immunefi entry declares M^0's repo as its githubUrl.

    Crediting the `audits/` folder there cleared KAST's under-audited flag and
    dropped the only genuinely-unaudited target out of the report entirely.
    """
    assert not github_url_matches_protocol(
        "https://github.com/m0-foundation/solana-m-extensions",
        slug="KAST",
        display_name="KAST",
    )


def test_github_url_matches_protocol_needs_identity_tokens() -> None:
    """No usable tokens → refuse to attribute rather than guess."""
    assert not github_url_matches_protocol(
        "https://github.com/someone/somerepo", slug=None, display_name=None
    )


def test_github_url_matches_protocol_rejects_non_github_url() -> None:
    assert not github_url_matches_protocol(
        "https://example.com/audits", slug="example", display_name="Example"
    )
