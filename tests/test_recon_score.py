"""Tests for attack_surface_score and its sub-scores (unknown-neutral rule)."""

from __future__ import annotations

from tvl_scanner.models import ReconSignals
from tvl_scanner.recon.score import (
    attack_surface_score,
    fund_delta_score,
    oracle_score,
    privileged_score,
    untested_code_score,
)


def test_fund_delta_unknown_is_neutral() -> None:
    assert fund_delta_score(None, None) == 5.0
    assert fund_delta_score(None, 1000) == 5.0
    assert fund_delta_score(3, None) == 5.0


def test_fund_delta_zero_window_is_zero() -> None:
    """A real baseline with no fund-path churn is a known clean window, not unknown."""
    assert fund_delta_score(0, 0) == 0.0


def test_fund_delta_monotonic_in_additions() -> None:
    prev = fund_delta_score(5, 10)
    assert fund_delta_score(5, 100) > prev
    assert fund_delta_score(5, 1_000) > fund_delta_score(5, 100)
    # ceiling holds
    huge = fund_delta_score(100, 1_000_000)
    assert huge <= 10.0


def test_fund_delta_log_scaling_anchors() -> None:
    # +100 code lines → ~5, +10k → 10 (additions carry the score)
    s100 = fund_delta_score(0, 100)
    s10k = fund_delta_score(0, 10_000)
    assert 4.5 <= s100 <= 5.5
    assert s10k == 10.0
    # breadth bonus: 0.2/file, capped at +2
    assert fund_delta_score(3, 0) == 0.6
    assert fund_delta_score(10, 0) == 2.0
    assert fund_delta_score(100, 0) == 2.0  # cap


def test_test_gap_unknown_is_neutral() -> None:
    assert untested_code_score(ReconSignals()) == 5.0


def test_test_gap_no_tests_max() -> None:
    sig = ReconSignals(source_files=20, test_files=0)
    assert untested_code_score(sig) == 10.0


def test_test_gap_healthy_ratio_zero() -> None:
    sig = ReconSignals(source_files=20, test_files=10)  # ratio 0.5
    assert untested_code_score(sig) == 0.0


def test_test_gap_no_source_is_neutral() -> None:
    assert untested_code_score(ReconSignals(source_files=0, test_files=0)) == 5.0


def test_privileged_density() -> None:
    # 10 markers over 2kLOC = 5/kLOC → capped at 10
    sig = ReconSignals(
        source_files=50,
        privileged_markers=10,
        initializer_markers=0,
        upgradeable_markers=0,
        scanned_loc=2_000,
    )
    assert privileged_score(sig) == 10.0
    # zero markers over a real codebase is a known clean signal
    clean = ReconSignals(source_files=50, privileged_markers=0, scanned_loc=2_000)
    assert privileged_score(clean) == 0.0
    # too little scanned code → noise → neutral
    tiny = ReconSignals(source_files=1, privileged_markers=5, scanned_loc=100)
    assert privileged_score(tiny) == 5.0


def test_oracle_score_scaling_and_neutral() -> None:
    assert oracle_score(ReconSignals()) == 5.0  # unknown
    assert oracle_score(ReconSignals(oracle_markers=0, scanned_loc=5_000)) == 0.0
    assert oracle_score(ReconSignals(oracle_markers=30, scanned_loc=5_000)) == 10.0
    assert oracle_score(ReconSignals(oracle_markers=3, scanned_loc=5_000)) == 1.0


def test_all_unknown_scores_are_neutral_five() -> None:
    score, subscores = attack_surface_score(
        fund_path_files_changed=None, fund_path_additions=None, signals=ReconSignals()
    )
    assert score == 5.0
    assert set(subscores) == {"fund_delta", "test_gap", "privileged", "oracle"}
    assert all(v == 5.0 for v in subscores.values())


def test_score_bounded_0_10() -> None:
    hot = ReconSignals(
        source_files=100,
        test_files=0,
        privileged_markers=50,
        initializer_markers=10,
        upgradeable_markers=10,
        oracle_markers=60,
        scanned_loc=10_000,
    )
    score, _ = attack_surface_score(
        fund_path_files_changed=80, fund_path_additions=50_000, signals=hot
    )
    assert score == 10.0

    cold = ReconSignals(
        source_files=100,
        test_files=200,
        privileged_markers=0,
        oracle_markers=0,
        scanned_loc=10_000,
    )
    score, _ = attack_surface_score(
        fund_path_files_changed=0, fund_path_additions=0, signals=cold
    )
    assert score == 0.0
