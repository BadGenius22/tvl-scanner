"""Tiny text helpers shared by the sources."""

from __future__ import annotations

import html
import re

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

# Descriptions only feed substring matching + a report snippet; a cap keeps
# artifacts and state small without hurting either use.
DESCRIPTION_CLIP = 4000


def strip_html(raw: str | None) -> str:
    """HTML → plain text: unescape entities, drop tags, collapse whitespace."""
    if not raw:
        return ""
    text = html.unescape(raw)
    text = _TAG_RE.sub(" ", text)
    return _WS_RE.sub(" ", text).strip()


def clip(text: str, limit: int = DESCRIPTION_CLIP) -> str:
    return text[:limit]
