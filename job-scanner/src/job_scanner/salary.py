"""Best-effort salary text → annualized USD range.

Job boards state compensation as free text ("$120,000 - $150,000", "80k–120k",
"€60k", "$95/hour"). This parser exists only to feed the compensation
sub-score, so it optimizes for "roughly right, never wildly wrong": anything it
can't read confidently returns None, which scores neutral.

Non-USD currencies are converted with rough constants — this is a ranking
signal, not payroll.
"""

from __future__ import annotations

import re

# Rough FX to USD, for ranking only.
_CURRENCY_TO_USD: dict[str, float] = {
    "$": 1.0,
    "usd": 1.0,
    "€": 1.1,
    "eur": 1.1,
    "£": 1.25,
    "gbp": 1.25,
}

# Pay-period → annualization multiplier (standard 40h week / 52 weeks).
_PERIOD_MULT: tuple[tuple[str, float], ...] = (
    ("hour", 2080.0),
    ("/hr", 2080.0),
    ("day", 260.0),
    ("week", 52.0),
    ("month", 12.0),
)

# A number like "120,000", "120000", "80.5", optionally suffixed with k.
_NUM_RE = re.compile(r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(k)?", re.IGNORECASE)

# Annualized-USD plausibility window. Values outside are parse noise (years,
# "top 1%", phone numbers), not compensation.
_MIN_PLAUSIBLE = 10_000
_MAX_PLAUSIBLE = 2_000_000


def parse_salary_text(text: str | None) -> tuple[int, int] | None:
    """Parse a salary string into an annualized (min_usd, max_usd) range.

    Returns None when nothing plausible can be extracted.
    """
    if not text:
        return None
    lower = text.lower()
    # "401k" would parse as 401 × 1000 — it's a retirement plan, not a salary.
    lower = re.sub(r"\b401\s*\(?k\)?", " ", lower)

    period = 1.0
    for token, mult in _PERIOD_MULT:
        if token in lower:
            period = mult
            break

    fx = 1.0
    for symbol, rate in _CURRENCY_TO_USD.items():
        if symbol in lower:
            fx = rate
            break

    values: list[float] = []
    for match in _NUM_RE.finditer(lower):
        num_text, k_suffix = match.group(1), match.group(2)
        value = float(num_text.replace(",", ""))
        if k_suffix:
            value *= 1000.0
        value *= period * fx
        if _MIN_PLAUSIBLE <= value <= _MAX_PLAUSIBLE:
            values.append(value)

    if not values:
        return None
    return int(min(values)), int(max(values))


def plausible_annual_usd(value: int | float | None) -> int | None:
    """Sanity-gate a numeric salary field a source provides directly.

    RemoteOK/Lever sometimes report 0 or junk; outside the plausibility window
    the value is discarded (None → neutral compensation score).
    """
    if value is None:
        return None
    if _MIN_PLAUSIBLE <= float(value) <= _MAX_PLAUSIBLE:
        return int(value)
    return None
