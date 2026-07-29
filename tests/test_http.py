"""Tests for the shared HTTP layer's rate-limit handling.

GitHub reports search (30/min) and secondary rate limits as 403, not 429. Before
`is_rate_limited` existed, those fell through to a hard HttpError, so a drained
bucket looked identical to "this protocol has no audit history" — every candidate
after the drain silently scored a perfect audit gap.
"""

from __future__ import annotations

import httpx
import pytest
from pytest_httpx import HTTPXMock

from tvl_scanner.http import HttpError, get_json, is_rate_limited


def _response(status_code: int, *, headers: dict[str, str] | None = None, text: str = "") -> httpx.Response:
    return httpx.Response(status_code, headers=headers or {}, text=text)


def test_is_rate_limited_detects_exhausted_remaining_header() -> None:
    assert is_rate_limited(_response(403, headers={"x-ratelimit-remaining": "0"}))


def test_is_rate_limited_detects_retry_after_header() -> None:
    assert is_rate_limited(_response(403, headers={"retry-after": "60"}))


def test_is_rate_limited_detects_message_body() -> None:
    assert is_rate_limited(_response(403, text='{"message": "API rate limit exceeded for user ID 1."}'))


def test_is_rate_limited_still_covers_429() -> None:
    assert is_rate_limited(_response(429, text="slow down"))


def test_is_rate_limited_ignores_plain_auth_failure() -> None:
    """A 403 from bad credentials is fatal, not transient — retrying wastes the budget."""
    assert not is_rate_limited(_response(403, text='{"message": "Bad credentials"}'))


def test_is_rate_limited_ignores_success_and_other_errors() -> None:
    assert not is_rate_limited(_response(200))
    assert not is_rate_limited(_response(422, text="rate limit"))


async def test_get_json_retries_403_rate_limit_then_succeeds(httpx_mock: HTTPXMock) -> None:
    url = "https://api.github.com/search/repositories"
    httpx_mock.add_response(
        url=url,
        status_code=403,
        headers={"x-ratelimit-remaining": "0"},
        json={"message": "API rate limit exceeded for user ID 1."},
    )
    httpx_mock.add_response(url=url, json={"items": [{"full_name": "code-423n4/x"}]})

    payload = await get_json(url)

    assert payload["items"][0]["full_name"] == "code-423n4/x"


async def test_get_json_does_not_retry_non_rate_limit_403(httpx_mock: HTTPXMock) -> None:
    """Bad credentials must fail fast rather than burning all retry attempts."""
    url = "https://api.github.com/search/repositories"
    httpx_mock.add_response(
        url=url,
        status_code=403,
        json={"message": "Bad credentials"},
    )

    with pytest.raises(HttpError, match="403"):
        await get_json(url)

    assert len(httpx_mock.get_requests()) == 1
