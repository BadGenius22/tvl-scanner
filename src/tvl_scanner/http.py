"""Shared async HTTP client with retry, timeout, and rate-limit friendliness.

All discover/enrich/audit_check modules go through this client so HTTP behavior
is consistent and tunable from one place. Per-client headers (API keys) are
passed via the `headers` kwarg on request methods, not stored on the client.
"""

from __future__ import annotations

import logging
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
    """GET `url` and return parsed JSON. Retries transient errors with exponential backoff.

    Raises HttpError on non-2xx responses after retries are exhausted.
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
                response = await client.get(url, params=params, headers=headers)
                if response.status_code == 429:
                    # Rate-limited. Retry with backoff.
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
        # Follow 301s: GitHub permanently redirects renamed repos/orgs (e.g. an
        # Immunefi target that rebrands — marsfoundation → sparkdotfi) within
        # api.github.com. Not following them surfaces the rename as a spurious
        # "repo inaccessible" and silently drops the target from delta-watch.
        follow_redirects=True,
    )
