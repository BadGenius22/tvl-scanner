"""Shared test setup: instant retries and a fresh settings cache per test."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from job_scanner import config


@pytest.fixture(autouse=True)
def fast_http(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("JOB_SCANNER_HTTP_BACKOFF_SECONDS", "0")
    monkeypatch.setenv("JOB_SCANNER_HTTP_MAX_RETRIES", "2")
    config.settings.cache_clear()
    yield
    config.settings.cache_clear()
