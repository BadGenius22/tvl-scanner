"""Resolve a DefiLlama Solana catalog candidate to its real on-chain program.

Catalog-sourced Solana candidates carry a synthetic address ``defillama:{slug}``
and no real program id. Stage 1's on-chain leg (``discover/rpc.py``) is EVM-only
by construction, so every Solana row in a scan is otherwise pure DefiLlama
hearsay — a TVL number with no auditable code pointer behind it.

This module closes that gap. Given the protocol's DefiLlama TVL-adapter module
name (the ``module`` field on the ``/protocol/{slug}`` detail endpoint, e.g.
``bulk-trade/index.js``) it:

  1. reads the token accounts the adapter sums (DefiLlama ``sumTokens`` registry),
  2. walks ``token account → SPL authority → owning program`` on-chain,
  3. profiles the program: its upgrade authority, the authority *type*
     (single keypair / Squads multisig / immutable), and the last-deploy date.

The upgrade-authority *type* is the load-bearing signal. A program that holds
real TVL whose upgrade authority is a single keypair can be drained by one
``deploy`` from whoever holds that key — a centralization posture an auditor
must know before spending time on the code.

Scope: covers protocols whose DefiLlama adapter uses the ``sumTokens`` registry
(the simple vault / pre-deposit class — exactly the tractable audit targets).
Protocols with bespoke ``projects/<slug>/index.js`` adapters, or whose TVL
account is held by a plain wallet / multisig rather than a custom program,
resolve to ``None`` and keep the placeholder. This is best-effort enrichment,
never fatal.

All RPC goes through the authenticated Alchemy endpoint when the ``alchemy``
secret is present (``deploy_watch._solana_rpc``), which sidesteps the public
endpoint's aggressive rate limiting.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

import httpx

from tvl_scanner.config import settings
from tvl_scanner.deploy_watch import _solana_rpc
from tvl_scanner.http import HttpError, post_json, shared_ssl_context

log = logging.getLogger(__name__)


# --- Well-known Solana program ids -----------------------------------------
SYSTEM_PROGRAM = "11111111111111111111111111111111"
SPL_TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
SPL_TOKEN_2022 = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
BPF_UPGRADEABLE_LOADER = "BPFLoaderUpgradeab1e11111111111111111111111"

# Squads is the dominant Solana multisig. An upgrade authority owned by one of
# these programs is a shared-custody signal (good), not a single hot key (bad).
SQUADS_PROGRAMS: dict[str, str] = {
    "SMPLecH534NA9acpos4G6x7uf3LWbCAwZQE9e8ZekMu": "Squads v3",
    "SQDS4ep65T869zMMBKyuUq6aD6EgTu8psMjkvj52pCf": "Squads v4",
}

# Upgrade-authority classifications (also used as the stored field value).
AUTH_SINGLE_KEYPAIR = "single_keypair"
AUTH_SQUADS_MULTISIG = "squads_multisig"
AUTH_IMMUTABLE = "immutable"
AUTH_UNKNOWN = "unknown"


# DefiLlama adapters repo — raw file host. The sumTokens registry is the main
# `registries/sumTokens.js` config plus the `sumTokens/dataN.js` shards it was
# split into. We fetch a generous fixed span and tolerate 404s: the registry
# grows by adding new dataN.js shards, so over-fetching a few empty slots keeps
# this correct without a directory-listing round-trip.
DL_ADAPTERS_RAW = "https://raw.githubusercontent.com/DefiLlama/DefiLlama-Adapters/main"
_REGISTRY_FILES: list[str] = ["registries/sumTokens.js"] + [
    f"registries/sumTokens/data{i}.js" for i in range(1, 9)
]

# A Solana address is 32-44 base58 chars (no 0, O, I, l).
_BASE58_RE = re.compile(r'"([1-9A-HJ-NP-Za-km-z]{32,44})"')


@dataclass(frozen=True)
class SolanaProgramProfile:
    """The on-chain program behind a DefiLlama Solana protocol's TVL."""

    program_id: str
    upgrade_authority: str | None  # None => immutable program
    authority_type: str  # one of the AUTH_* constants (or "program_controlled:…")
    deploy_slot: int | None
    deploy_date: date | None
    tvl_token_account: str  # the SPL account we walked in from
    loader: str  # "upgradeable" | "non_upgradeable"


# --- registry fetch + parse -------------------------------------------------

# Process-wide cache of the concatenated registry text. A scan resolves many
# Solana candidates; fetching ~9 files once and reusing the text avoids
# re-downloading the whole registry per candidate.
_REGISTRY_TEXT: str | None = None
_REGISTRY_LOCK = asyncio.Lock()


def clear_registry_cache() -> None:
    """Reset the module-level registry cache (used by tests)."""
    global _REGISTRY_TEXT
    _REGISTRY_TEXT = None


async def _fetch_text(url: str, client: httpx.AsyncClient | None = None) -> str | None:
    """GET `url` and return the response body as text, or None on any failure.

    The registry files are JavaScript, not JSON, so `http.get_json` can't be
    used. This is a thin best-effort text GET; a missing shard (404) is a
    normal, non-fatal outcome.
    """
    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(
            timeout=settings().HTTP_TIMEOUT_SECONDS,
            verify=shared_ssl_context(),
            follow_redirects=True,
        )
    assert client is not None
    try:
        resp = await client.get(url)
        if resp.status_code == 200:
            return resp.text
        return None
    except httpx.HTTPError as exc:
        log.debug("solana_rpc: registry fetch failed for %s: %s", url, exc)
        return None
    finally:
        if owns_client:
            await client.aclose()


async def load_sumtokens_registry(client: httpx.AsyncClient | None = None) -> str:
    """Fetch and cache the concatenated DefiLlama sumTokens registry text."""
    global _REGISTRY_TEXT
    if _REGISTRY_TEXT is not None:
        return _REGISTRY_TEXT
    async with _REGISTRY_LOCK:
        if _REGISTRY_TEXT is not None:
            return _REGISTRY_TEXT
        parts: list[str] = []
        for path in _REGISTRY_FILES:
            text = await _fetch_text(f"{DL_ADAPTERS_RAW}/{path}", client)
            if text:
                parts.append(text)
        _REGISTRY_TEXT = "\n".join(parts)
        return _REGISTRY_TEXT


def _match_braces(text: str, start: int) -> str | None:
    """Return the substring from the `{` at `start` through its matching `}`.

    None if `start` is not an opening brace or the braces never balance.
    """
    if start < 0 or start >= len(text) or text[start] != "{":
        return None
    depth = 0
    for i in range(start, len(text)):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _extract_token_accounts(registry_text: str, adapter_key: str) -> list[str]:
    """Extract the Solana `tokenAccounts` list for one adapter key.

    Finds ``"adapter_key": { … "solana": { … "tokenAccounts": [ … ] } }`` and
    returns the quoted base58 addresses inside the array. Comments (`// LABEL`)
    are ignored because only *quoted* strings are extracted. Returns [] when the
    key is absent or the adapter doesn't use the tokenAccounts shape (e.g. a
    bespoke `owners`/`tokens` config).
    """
    key_pos = registry_text.find(f'"{adapter_key}"')
    if key_pos == -1:
        return []
    brace = registry_text.find("{", key_pos)
    block = _match_braces(registry_text, brace)
    if not block:
        return []

    sol_pos = block.find("solana")
    if sol_pos == -1:
        return []
    sol_block = _match_braces(block, block.find("{", sol_pos))
    if not sol_block:
        return []

    ta_pos = sol_block.find("tokenAccounts")
    if ta_pos == -1:
        return []
    lb = sol_block.find("[", ta_pos)
    rb = sol_block.find("]", lb)
    if lb == -1 or rb == -1:
        return []
    return _BASE58_RE.findall(sol_block[lb + 1 : rb])


# --- on-chain walk ----------------------------------------------------------


async def _rpc(method: str, params: list[Any], client: httpx.AsyncClient | None) -> Any:
    """One Solana JSON-RPC call; returns the `result` field or raises HttpError."""
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    resp = await post_json(_solana_rpc(), json_body=body, client=client)
    if isinstance(resp, dict) and resp.get("error"):
        raise HttpError(f"solana rpc {method} error: {resp['error']}")
    return resp.get("result") if isinstance(resp, dict) else None


async def _get_account(addr: str, client: httpx.AsyncClient | None) -> dict[str, Any] | None:
    """getAccountInfo(jsonParsed) → the account `value` dict, or None if absent."""
    result = await _rpc(
        "getAccountInfo",
        [addr, {"encoding": "jsonParsed", "commitment": "finalized"}],
        client,
    )
    if not isinstance(result, dict):
        return None
    value = result.get("value")
    return value if isinstance(value, dict) else None


def _parsed_info(value: dict[str, Any]) -> dict[str, Any]:
    """Pull `data.parsed.info` from a jsonParsed account value ({} if unparsed)."""
    data = value.get("data")
    if not isinstance(data, dict):
        return {}
    parsed = data.get("parsed")
    if not isinstance(parsed, dict):
        return {}
    info = parsed.get("info")
    return info if isinstance(info, dict) else {}


async def resolve_program_from_token_account(
    token_account: str, client: httpx.AsyncClient | None
) -> tuple[str, str] | None:
    """Walk an SPL token account to the custom program that controls it.

    ``token account → authority (its SPL `owner`) → owning program (the
    authority account's `owner`)``. Returns ``(program_id, authority)`` or None
    when the account isn't an SPL token account, or its authority is a plain
    wallet / token program / Squads multisig rather than a custom program (i.e.
    the funds are custodied, with no bespoke program to audit).
    """
    value = await _get_account(token_account, client)
    if not value:
        return None
    authority = _parsed_info(value).get("owner")  # SPL token account authority
    if not isinstance(authority, str) or not authority:
        return None

    auth_value = await _get_account(authority, client)
    if not auth_value:
        return None
    program = auth_value.get("owner")
    if not isinstance(program, str):
        return None
    # The authority must be program-owned. System/token/Squads owners mean the
    # TVL is custodied directly, with no custom program behind it.
    if program in (SYSTEM_PROGRAM, SPL_TOKEN_PROGRAM, SPL_TOKEN_2022) or program in SQUADS_PROGRAMS:
        return None
    return program, authority


@dataclass(frozen=True)
class _RawProgramProfile:
    loader: str
    programdata: str | None
    upgrade_authority: str | None
    slot: int | None


async def profile_program(
    program_id: str, client: httpx.AsyncClient | None
) -> _RawProgramProfile | None:
    """Read a program's loader, ProgramData, upgrade authority and deploy slot.

    A non-upgradeable (finalized) program has no ProgramData and is effectively
    immutable. An upgradeable program's ProgramData carries the current upgrade
    `authority` (None once relinquished) and the last-deployed `slot`.
    """
    value = await _get_account(program_id, client)
    if not value or not value.get("executable"):
        return None
    if value.get("owner") != BPF_UPGRADEABLE_LOADER:
        # Non-upgradeable loader → immutable program, no ProgramData.
        return _RawProgramProfile("non_upgradeable", None, None, None)

    programdata = _parsed_info(value).get("programData")
    if not isinstance(programdata, str):
        return _RawProgramProfile("non_upgradeable", None, None, None)

    pd_value = await _get_account(programdata, client)
    pd_info = _parsed_info(pd_value) if pd_value else {}
    authority = pd_info.get("authority")  # None => upgrade authority relinquished
    slot = pd_info.get("slot")
    return _RawProgramProfile(
        loader="upgradeable",
        programdata=programdata,
        upgrade_authority=authority if isinstance(authority, str) else None,
        slot=int(slot) if isinstance(slot, (int, float)) else None,
    )


async def classify_authority(authority: str | None, client: httpx.AsyncClient | None) -> str:
    """Classify an upgrade authority as a keypair, Squads multisig, or immutable."""
    if authority is None:
        return AUTH_IMMUTABLE
    value = await _get_account(authority, client)
    if not value:
        return AUTH_UNKNOWN
    owner = value.get("owner")
    if isinstance(owner, str) and owner in SQUADS_PROGRAMS:
        return AUTH_SQUADS_MULTISIG
    if owner == SYSTEM_PROGRAM:
        # System-owned, zero-data account = a plain keypair (single signer).
        return AUTH_SINGLE_KEYPAIR
    if isinstance(owner, str) and owner:
        # Owned by some other program (custom governance / timelock).
        return f"program_controlled:{owner[:8]}"
    return AUTH_UNKNOWN


async def _slot_to_date(slot: int, client: httpx.AsyncClient | None) -> date | None:
    """Convert a slot to its UTC block date via getBlockTime (best-effort)."""
    try:
        ts = await _rpc("getBlockTime", [slot], client)
    except HttpError:
        return None
    if not isinstance(ts, (int, float)):
        return None
    return datetime.fromtimestamp(float(ts), tz=UTC).date()


async def resolve_solana_program(
    module: str,
    *,
    client: httpx.AsyncClient | None = None,
    registry_text: str | None = None,
) -> SolanaProgramProfile | None:
    """Resolve the on-chain program behind a DefiLlama Solana protocol.

    `module` is the protocol's DefiLlama adapter module (`/protocol/{slug}`
    detail `module` field, e.g. ``bulk-trade/index.js`` or ``bulk-trade``); its
    first path segment is the sumTokens registry key. `registry_text` may be
    injected to bypass the network fetch (tests); production loads it from the
    cached registry.

    Returns a profile for the first TVL token account that resolves to a custom
    upgradeable/immutable program, or None when nothing resolves.
    """
    adapter_key = module.split("/")[0].strip()
    if not adapter_key:
        return None

    text = registry_text if registry_text is not None else await load_sumtokens_registry(client)
    accounts = _extract_token_accounts(text, adapter_key)
    if not accounts:
        return None

    for account in accounts:
        try:
            walked = await resolve_program_from_token_account(account, client)
            if not walked:
                continue
            program_id, _authority = walked
            raw = await profile_program(program_id, client)
            if not raw:
                continue
            auth_type = await classify_authority(raw.upgrade_authority, client)
            deploy_date = await _slot_to_date(raw.slot, client) if raw.slot else None
        except HttpError as exc:
            log.debug("solana_rpc: walk failed for %s (%s): %s", adapter_key, account, exc)
            continue
        return SolanaProgramProfile(
            program_id=program_id,
            upgrade_authority=raw.upgrade_authority,
            authority_type=auth_type,
            deploy_slot=raw.slot,
            deploy_date=deploy_date,
            tvl_token_account=account,
            loader=raw.loader,
        )
    return None
