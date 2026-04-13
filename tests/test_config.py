"""Tests for the config and secrets layer."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from tvl_scanner.config import SecretsError, Settings, get_secret, settings


def test_settings_defaults() -> None:
    """Settings should load with sane defaults even without .env."""
    # Clear the lru_cache so we get a fresh read
    settings.cache_clear()
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.MIN_TVL_USD == 100_000
    assert s.MAX_AGE_DAYS == 365
    assert "solana" in s.chain_list
    assert "arbitrum" in s.chain_list
    assert "base" in s.chain_list
    assert "leverage" in s.EDGE_MATCH_KEYWORDS


def test_settings_chain_list_parsing() -> None:
    """Comma-separated CHAINS should split cleanly with whitespace tolerance."""
    s = Settings(CHAINS="solana, arbitrum ,base", _env_file=None)  # type: ignore[call-arg]
    assert s.chain_list == ["solana", "arbitrum", "base"]


def test_get_secret_env_fallback() -> None:
    """When pass lookup fails, env var fallback should work."""
    get_secret.cache_clear()
    with patch.dict(os.environ, {"TVL_SCANNER_TEST_KEY": "env-fallback-value"}):
        with patch("tvl_scanner.config.shutil.which", return_value=None):
            value = get_secret("test_key")
            assert value == "env-fallback-value"


def test_get_secret_strips_whitespace() -> None:
    """Secrets with trailing newlines should be stripped."""
    get_secret.cache_clear()
    with patch.dict(os.environ, {"TVL_SCANNER_TEST_KEY": "  padded-value  \n"}):
        with patch("tvl_scanner.config.shutil.which", return_value=None):
            value = get_secret("test_key")
            assert value == "padded-value"


def test_get_secret_missing_required_raises() -> None:
    """Required secret that is missing everywhere should raise SecretsError."""
    get_secret.cache_clear()
    with patch.dict(os.environ, {}, clear=True):
        with patch("tvl_scanner.config.shutil.which", return_value=None):
            with pytest.raises(SecretsError, match="not found in pass"):
                get_secret("nonexistent_key", required=True)


def test_get_secret_missing_optional_returns_none() -> None:
    """Optional secret that is missing should return None, not raise."""
    get_secret.cache_clear()
    with patch.dict(os.environ, {}, clear=True):
        with patch("tvl_scanner.config.shutil.which", return_value=None):
            value = get_secret("nonexistent_key", required=False)
            assert value is None
