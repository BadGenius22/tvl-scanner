#!/usr/bin/env python3
"""Shared TypeSafe (System One / Jev) client for the tvl-scanner pipeline.

Thin wrapper over POST https://api.typesafe.ai/v1/systemone. Independent
questions over the same state go in ONE request (they run in parallel and
cannot see each other's answers). Policy — thresholds, weights, escalation —
lives in the calling scripts, never here. API key read from
TYPESAFE_API_KEY in .env; keep it server-side.

Disk cache: identical (state, questions, model) tuples are served from
artifacts/typesafe_cache.json so re-runs don't re-spend quota.
"""
import hashlib
import json
import os
import time
import urllib.request

API = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-latest"
CACHE_PATH = os.path.join("artifacts", "typesafe_cache.json")

_key = None
_cache = None
_cache_dirty = False


def _load_key():
    global _key
    if _key is None:
        # 1) process environment (works across every repo once set at user level:
        #    setx TYPESAFE_API_KEY ...), 2) repo-local .env fallback
        _key = os.environ.get("TYPESAFE_API_KEY", "").strip()
        if not _key:
            for line in open(".env"):
                if line.startswith("TYPESAFE_API_KEY") and "=" in line:
                    _key = line.split("=", 1)[1].strip()
        if not _key:
            raise RuntimeError("TYPESAFE_API_KEY not found in environment or .env")
    return _key


def _cache_load():
    global _cache
    if _cache is None:
        if os.path.exists(CACHE_PATH):
            _cache = json.load(open(CACHE_PATH))
        else:
            _cache = {}
    return _cache


def _cache_key(state, questions, model):
    blob = json.dumps({"s": state, "q": questions, "m": model}, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:24]


def _cache_save():
    global _cache_dirty
    if _cache_dirty:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        json.dump(_cache, open(CACHE_PATH, "w"), indent=0)
        _cache_dirty = False


def ask(state, questions, model=MODEL, retries=4, use_cache=True):
    """Evaluate one state against a map of typed questions.

    questions: {id: {"type": "noul"|"choice"|"score", "instructions": ..., ...}}
    Returns the answers map {id: answer-dict}. Cached on disk.
    """
    ck = _cache_key(state, questions, model)
    cache = _cache_load()
    if use_cache and ck in cache:
        return cache[ck]
    body = json.dumps({"state": state, "model": model, "questions": questions}).encode()
    last = None
    for i in range(retries):
        req = urllib.request.Request(
            API, data=body,
            headers={"Authorization": f"Bearer {_load_key()}", "Content-Type": "application/json"},
            method="POST")
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                d = json.load(r)
            answers = d.get("answers", {})
            if use_cache:
                cache[ck] = answers
                _cache_dirty = True
                _cache_save()
            return answers
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="ignore")[:200]
            if e.code in (401, 403, 422):
                raise RuntimeError(f"TypeSafe API {e.code}: {detail}")
            last = RuntimeError(f"TypeSafe API {e.code}: {detail}")
        except Exception as e:
            last = e
        time.sleep(1.5 * (i + 1))
    raise last


def usage_note():
    """Reminder printed by calling scripts — token cost is real quota."""
    return "every uncached ask() spends quota; keep questions narrow, cache is resumable"
