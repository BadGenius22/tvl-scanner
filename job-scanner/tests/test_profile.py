"""Tests for profile loading + resolution order."""

from __future__ import annotations

from pathlib import Path

import pytest

from job_scanner import config
from job_scanner.profile import load_profile


def test_packaged_default_loads() -> None:
    profile = load_profile()
    assert profile.role_keywords  # non-empty
    assert profile.core_skills
    assert profile.remote_only is True
    assert 0 < profile.min_salary_usd <= profile.target_salary_usd


def test_explicit_path_partial_override(tmp_path: Path) -> None:
    """A minimal personal profile overrides only what it states."""
    p = tmp_path / "mine.yaml"
    p.write_text(
        """
name: mine
role_keywords: [protocol engineer]
compensation:
  min_salary_usd: 90000
  target_salary_usd: 200000
unknown_key: ignored
"""
    )
    profile = load_profile(p)
    assert profile.name == "mine"
    assert profile.role_keywords == ["protocol engineer"]
    assert profile.min_salary_usd == 90_000
    assert profile.target_salary_usd == 200_000
    # unstated sections fall back to field defaults
    assert profile.remote_only is True
    assert profile.max_age_days == 45


def test_explicit_missing_path_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_profile(tmp_path / "nope.yaml")


def test_env_profile_path_wins_over_packaged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = tmp_path / "env-profile.yaml"
    p.write_text("name: from-env\n")
    monkeypatch.setenv("JOB_SCANNER_PROFILE_PATH", str(p))
    config.settings.cache_clear()
    profile = load_profile()
    assert profile.name == "from-env"


def test_keywords_are_lowercased_and_deduped(tmp_path: Path) -> None:
    p = tmp_path / "case.yaml"
    p.write_text(
        """
role_keywords: [Solidity, solidity, "  RUST  "]
"""
    )
    profile = load_profile(p)
    assert profile.role_keywords == ["solidity", "rust"]
