"""Shared test configuration.

All HTTP in the suite is mocked with pytest-httpx, so real-time waits between
(mocked) calls are pure dead time — they used to be ~80s of the suite's wall
clock. Two knobs are zeroed here; retry *counts* are unchanged everywhere:

  - tenacity backoff in http.get_json (via HTTP_BACKOFF_SECONDS=0)
  - Etherscan free-tier throttle + NOTOK retry sleep (module constants)
"""

from __future__ import annotations

import os

import httpx
import pytest

from tvl_scanner.config import settings
from tvl_scanner.enrich import etherscan

os.environ.setdefault("HTTP_BACKOFF_SECONDS", "0")
settings.cache_clear()


@pytest.fixture(autouse=True)
def _no_rate_limit_sleeps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(etherscan, "_ETHERSCAN_MIN_INTERVAL_SEC", 0.0)
    monkeypatch.setattr(etherscan, "_ETHERSCAN_NOTOK_RETRY_SEC", 0.0)


@pytest.fixture(autouse=True)
def _block_real_http(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fail fast on any real network I/O from tests.

    Tests that mock HTTP use the pytest-httpx fixture, which replaces the
    transport itself — those are left alone. Every other test gets a transport
    that raises ConnectError immediately, so code paths that would silently
    hit live APIs (and did: the enricher tests spent ~15s on real sockets)
    degrade the same way they would offline, instantly.
    """
    if "httpx_mock" in request.fixturenames:
        return

    def _blocked(self: object, req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"real HTTP blocked in tests: {req.url}")

    async def _blocked_async(self: object, req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"real HTTP blocked in tests: {req.url}")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", _blocked)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", _blocked_async)
