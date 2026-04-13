"""Curated slug → GitHub URL registry for protocols DefiLlama undercovers.

DefiLlama's `/protocols` catalog and `/protocol/{slug}` detail endpoint
don't reliably expose github URLs even for well-known protocols. This
fallback is loaded once per process and checked after both DefiLlama paths
fail to resolve a github URL.

Match semantics: exact slug lookup (case-insensitive, stripped). No fuzzy
matching — if the scanner's slug doesn't match an entry exactly, fall
through to None. Curation over algorithms.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from importlib.resources import files

import yaml

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def load_github_registry() -> dict[str, str]:
    """Parse `data/github_registry.yaml` into a slug → github URL dict.

    Cached per process. Degrades to an empty dict on parse failure so that
    a malformed seed file can't kill the scanner.
    """
    try:
        resource = files("tvl_scanner.data").joinpath("github_registry.yaml")
        raw = resource.read_text(encoding="utf-8")
    except Exception as exc:
        log.error("github registry not found: %s", exc)
        return {}

    data = yaml.safe_load(raw) or []
    if not isinstance(data, list):
        log.error("github registry is not a list")
        return {}

    mapping: dict[str, str] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        slug = item.get("slug")
        gh = item.get("github")
        if isinstance(slug, str) and isinstance(gh, str):
            mapping[slug.strip().lower()] = gh.strip()
    log.info("loaded %d github registry entries", len(mapping))
    return mapping


def lookup(slug: str | None) -> str | None:
    """Return the github URL for `slug`, or None if not in the registry."""
    if not slug:
        return None
    return load_github_registry().get(slug.strip().lower())
