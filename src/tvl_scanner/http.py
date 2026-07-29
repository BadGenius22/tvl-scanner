"""Shared async HTTP client with retry, timeout, and rate-limit friendliness.

All discover/enrich/audit_check modules go through this client so HTTP behavior
is consistent and tunable from one place. Per-client headers (API keys) are
passed via the `headers` kwarg on request methods, not stored on the client.
"""

from __future__ import annotations

import logging
import ssl
from functools import lru_cache
from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from tvl_scanner.config import settings

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def shared_ssl_context() -> ssl.SSLContext:
    """Process-wide TLS context. Loading the CA bundle costs ~25ms per
    httpx client; helpers that spin up short-lived clients (homepage scrape,
    RPC checks) multiply that into seconds per scan. Every client
    construction in this codebase should pass `verify=shared_ssl_context()`.
    """
    return httpx.create_ssl_context()


class HttpError(RuntimeError):
    """Wraps upstream HTTP failures after retries are exhausted."""


RETRYABLE = (
    httpx.ConnectError,
    httpx.ReadError,
    httpx.WriteError,
    httpx.PoolTimeout,
    httpx.ReadTimeout,
    httpx.ConnectTimeout,
    httpx.RemoteProtocolError,
)


def is_rate_limited(response: httpx.Response) -> bool:
    """True when a 403 is really a rate-limit rejection rather than a auth failure.

    GitHub reports both search (30/min) and secondary rate limits as 403, not 429.
    Treating those as fatal silently zeroes the audit signal for every candidate
    after the bucket drains, which reads as "no audits found" in the report.
    """
    if response.status_code == 429:
        # 429 is unambiguous: always back off and retry.
        return True
    if response.status_code != 403:
        return False
    # A 403 is overloaded — it covers both rate limits and auth failures, and
    # only the former is worth retrying. Require positive evidence.
    if response.headers.get("x-ratelimit-remaining") == "0":
        return True
    if "retry-after" in response.headers:
        return True
    return "rate limit" in response.text.lower()


async def get_json(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    client: httpx.AsyncClient | None = None,
) -> Any:
    """GET `url` and return parsed JSON. Retries transient errors with exponential backoff.

    Raises HttpError on non-2xx responses after retries are exhausted.
    """
    s = settings()
    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(
            timeout=s.HTTP_TIMEOUT_SECONDS,
            follow_redirects=True,
            verify=shared_ssl_context(),
        )
    assert client is not None  # for mypy

    try:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(s.HTTP_MAX_RETRIES),
            # min scales down with the multiplier so HTTP_BACKOFF_SECONDS=0
            # (tests) means no sleep at all; production (2.0) keeps min=1.
            wait=wait_exponential(
                multiplier=s.HTTP_BACKOFF_SECONDS,
                min=min(1.0, s.HTTP_BACKOFF_SECONDS),
                max=30,
            ),
            retry=retry_if_exception_type(RETRYABLE),
            reraise=True,
        ):
            with attempt:
                response = await client.get(url, params=params, headers=headers)
                if is_rate_limited(response):
                    raise httpx.ReadTimeout(f"{response.status_code} rate limited")
                if response.status_code >= 500:
                    raise httpx.ReadTimeout(f"upstream {response.status_code}")
                response.raise_for_status()
                return response.json()
    except httpx.HTTPStatusError as exc:
        raise HttpError(
            f"HTTP {exc.response.status_code} for {url}: {exc.response.text[:200]}"
        ) from exc
    except RETRYABLE as exc:
        raise HttpError(f"Transport failure for {url}: {exc}") from exc
    finally:
        if owns_client:
            await client.aclose()
    return None  # unreachable, mypy satisfaction


async def post_json(
    url: str,
    *,
    json_body: dict[str, Any] | list[Any],
    headers: dict[str, str] | None = None,
    client: httpx.AsyncClient | None = None,
) -> Any:
    """POST `json_body` to `url` and return parsed JSON.

    Same retry/timeout/429 handling as `get_json`, for endpoints that require a
    POST body — notably JSON-RPC nodes (Solana / EVM) used by the deploy-watch.
    """
    s = settings()
    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(timeout=s.HTTP_TIMEOUT_SECONDS, follow_redirects=True)
    assert client is not None  # for mypy

    try:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(s.HTTP_MAX_RETRIES),
            wait=wait_exponential(multiplier=s.HTTP_BACKOFF_SECONDS, min=1, max=30),
            retry=retry_if_exception_type(RETRYABLE),
            reraise=True,
        ):
            with attempt:
                response = await client.post(url, json=json_body, headers=headers)
                if is_rate_limited(response):
                    raise httpx.ReadTimeout(f"{response.status_code} rate limited")
                if response.status_code >= 500:
                    raise httpx.ReadTimeout(f"upstream {response.status_code}")
                response.raise_for_status()
                return response.json()
    except httpx.HTTPStatusError as exc:
        raise HttpError(
            f"HTTP {exc.response.status_code} for {url}: {exc.response.text[:200]}"
        ) from exc
    except RETRYABLE as exc:
        raise HttpError(f"Transport failure for {url}: {exc}") from exc
    finally:
        if owns_client:
            await client.aclose()
    return None  # unreachable, mypy satisfaction


def make_client(headers: dict[str, str] | None = None) -> httpx.AsyncClient:
    """Construct a reusable AsyncClient with the global timeout applied."""
    s = settings()
    return httpx.AsyncClient(
        timeout=s.HTTP_TIMEOUT_SECONDS,
        headers=headers or {},
        verify=shared_ssl_context(),
        # Follow 301s: GitHub permanently redirects renamed repos/orgs (e.g. an
        # Immunefi target that rebrands — marsfoundation → sparkdotfi) within
        # api.github.com. Not following them surfaces the rename as a spurious
        # "repo inaccessible" and silently drops the target from delta-watch.
        follow_redirects=True,
    )
