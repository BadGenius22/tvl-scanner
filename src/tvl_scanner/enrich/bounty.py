"""Bounty program lookup from the curated seeds file.

The scanner uses a YAML seeds file (`src/tvl_scanner/data/bounty_registry.yaml`)
rather than scraping Immunefi/HackerOne. Reasons:
    1. No HTML scraping fragility
    2. Deterministic, testable, versioned in git
    3. User can add new entries as they hunt — it's a flat file
    4. Still catches the >90% of interesting cases since the big bounty programs
       are stable over time

Matching: a candidate matches a registry entry if ANY of its identifying
strings (display_name, defillama_slug, target_name) equals ANY of the entry's
`slugs` (all case-insensitive, exact equality after normalization).

Loading is eager: the registry is parsed once per scanner process and cached.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from typing import Literal

import yaml

log = logging.getLogger(__name__)

BountyPlatform = Literal[
    "immunefi", "hackerone", "hackenproof", "cantina", "bugcrowd", "intigriti", "selfhosted"
]


@dataclass(frozen=True)
class BountyEntry:
    name: str
    slugs: tuple[str, ...]
    platform: BountyPlatform
    url: str
    max_payout_usd: int | None


def _normalize(s: str) -> str:
    return s.strip().lower().replace(" ", "-")


@lru_cache(maxsize=1)
def load_registry() -> list[BountyEntry]:
    """Load and parse the bounty_registry.yaml seeds file. Cached per process."""
    try:
        resource = files("tvl_scanner.data").joinpath("bounty_registry.yaml")
        raw = resource.read_text(encoding="utf-8")
    except Exception as exc:
        log.error("bounty registry not found: %s", exc)
        return []

    data = yaml.safe_load(raw) or []
    if not isinstance(data, list):
        log.error("bounty registry is not a list: got %s", type(data).__name__)
        return []

    entries: list[BountyEntry] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            slugs_raw = item.get("slugs") or []
            slugs = tuple(_normalize(str(s)) for s in slugs_raw)
            entries.append(
                BountyEntry(
                    name=str(item["name"]),
                    slugs=slugs,
                    platform=item.get("platform", "immunefi"),
                    url=str(item["url"]),
                    max_payout_usd=(
                        int(item["max_payout_usd"])
                        if item.get("max_payout_usd") is not None
                        else None
                    ),
                )
            )
        except (KeyError, ValueError, TypeError) as exc:
            log.warning("skipping malformed bounty registry entry: %s", exc)
    log.info("loaded %d bounty registry entries", len(entries))
    return entries


def match(
    *,
    display_name: str | None = None,
    defillama_slug: str | None = None,
    target_name: str | None = None,
) -> BountyEntry | None:
    """Return the first registry entry whose `slugs` list contains any of the
    candidate's identifying strings. None if no match.
    """
    candidates: set[str] = set()
    for raw in (display_name, defillama_slug, target_name):
        if raw:
            candidates.add(_normalize(raw))
    if not candidates:
        return None

    for entry in load_registry():
        for entry_slug in entry.slugs:
            if entry_slug in candidates:
                return entry
    return None
