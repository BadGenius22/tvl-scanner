"""Shared async HTTP client with retry, timeout, and rate-limit friendliness.

All sources go through `get_json()` so HTTP behavior is consistent and tunable
from one place (adapted from the tvl-scanner http layer). Per-source headers
are passed via the `headers` kwarg on each request, not stored on the client.
Tests inject `client=` and mock with pytest-httpx.
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

from job_scanner.config import settings

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def shared_ssl_context() -> ssl.SSLContext:
    """Process-wide TLS context — loading the CA bundle costs ~25ms per client."""
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


async def get_json(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    client: httpx.AsyncClient | None = None,
) -> Any:
    """GET `url` and return parsed JSON. Retries transient errors with backoff.

    429/5xx are wrapped as ReadTimeout to trigger a retry. Raises HttpError on
    non-2xx after retries are exhausted.
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
                if response.status_code == 429:
                    raise httpx.ReadTimeout("429 rate limited")
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
        follow_redirects=True,
    )
