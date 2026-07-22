"""Tests for the best-effort salary parser."""

from __future__ import annotations

from job_scanner.salary import parse_salary_text, plausible_annual_usd


def test_usd_range_with_commas() -> None:
    assert parse_salary_text("$120,000 - $150,000") == (120_000, 150_000)


def test_k_suffix_range_no_currency() -> None:
    assert parse_salary_text("80k–120k") == (80_000, 120_000)


def test_eur_converted_roughly() -> None:
    parsed = parse_salary_text("€60k")
    assert parsed is not None
    assert parsed == (66_000, 66_000)  # 60k × 1.1


def test_401k_is_not_a_salary() -> None:
    assert parse_salary_text("Great 401k match and free snacks") is None


def test_401k_alongside_real_salary() -> None:
    assert parse_salary_text("$100k plus 401(k) match") == (100_000, 100_000)


def test_hourly_rate_annualized() -> None:
    assert parse_salary_text("$95/hour") == (197_600, 197_600)  # 95 × 2080


def test_monthly_rate_annualized() -> None:
    assert parse_salary_text("$9,000 per month") == (108_000, 108_000)


def test_free_text_without_numbers() -> None:
    assert parse_salary_text("Competitive") is None
    assert parse_salary_text("") is None
    assert parse_salary_text(None) is None


def test_implausible_values_rejected() -> None:
    # "top 1%" style numbers and years must not parse as compensation
    assert parse_salary_text("Founded in 2019, top 1% team") is None


def test_plausible_annual_usd_gate() -> None:
    assert plausible_annual_usd(0) is None
    assert plausible_annual_usd(None) is None
    assert plausible_annual_usd(120_000) == 120_000
    assert plausible_annual_usd(5_000_000) is None
