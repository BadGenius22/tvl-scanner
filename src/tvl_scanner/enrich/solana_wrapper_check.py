"""Solana wrapper-program detection and on-chain TVL sanity check.

Two related checks for Solana candidates discovered via DefiLlama:

1. **Wrapper program detection (Batch J1)**
   Query `getAccountInfo` on the candidate's primary contract account.
   The `owner` field returns the program that controls the account. If
   that program is in our curated registry of known wrapper programs
   (SPL Stake Pool, Token-2022, etc.), the candidate is a thin
   deployment of audited code and has no novel attack surface.

2. **On-chain TVL sanity check (Batch J2)**
   For LST candidates (Liquid Staking category), look up the LST mint
   address in our registry, fetch its total supply via getTokenSupply,
   and compute `actual_tvl = supply × native_price_usd`. If DefiLlama is
   off by more than 10x, override DefiLlama with on-chain reality.

Why this matters: the v0.4.1 scan ranked JagPool Staked SOL at #1 with
$63M claimed TVL. On-chain reality was 0.109 jagSOL (~$0.15) and the
account is owned by the SPL stake pool program. Both filters would have
caught it independently.

Uses Solana's public RPC (api.mainnet-beta.solana.com) which is free
and unauthenticated. Per-scan call volume is small (one call per
Solana candidate) so we don't hit rate limits in practice.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from typing import Any

import httpx
import yaml

log = logging.getLogger(__name__)


SOLANA_RPC_URL = "https://api.mainnet-beta.solana.com"


@dataclass(frozen=True)
class WrapperProgramEntry:
    """One registry entry for a known wrapper program."""

    program_id: str
    name: str
    audit_count: int
    audit_url: str | None
    description: str


@dataclass(frozen=True)
class WrapperMatch:
    """Result of a wrapper program lookup against an on-chain account."""

    entry: WrapperProgramEntry
    account_owner: str  # the actual owner field returned by the RPC


@lru_cache(maxsize=1)
def load_wrapper_registry() -> dict[str, WrapperProgramEntry]:
    """Parse data/solana_wrapper_programs.yaml into program_id → entry."""
    try:
        resource = files("tvl_scanner.data").joinpath("solana_wrapper_programs.yaml")
        raw = resource.read_text(encoding="utf-8")
    except Exception as exc:
        log.error("solana wrapper registry not found: %s", exc)
        return {}

    data = yaml.safe_load(raw) or []
    if not isinstance(data, list):
        log.error("solana wrapper registry is not a list")
        return {}

    mapping: dict[str, WrapperProgramEntry] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            entry = WrapperProgramEntry(
                program_id=str(item["program_id"]).strip(),
                name=str(item["name"]),
                audit_count=int(item.get("audit_count", 0)),
                audit_url=item.get("audit_url"),
                description=str(item.get("description", "")),
            )
            mapping[entry.program_id] = entry
        except (KeyError, ValueError, TypeError) as exc:
            log.warning("skipping malformed wrapper registry entry: %s", exc)
    log.info("loaded %d solana wrapper program entries", len(mapping))
    return mapping


@dataclass(frozen=True)
class LstRegistryEntry:
    """One LST registry entry: links a DefiLlama slug to its on-chain accounts.

    Either `mint` or `stake_pool` (or both) must be set. `mint` is required
    for the J2 on-chain TVL sanity check; `stake_pool` is required for the
    J1 wrapper-program detection via check_lst_wrapper.
    """

    slug: str
    mint: str | None = None
    stake_pool: str | None = None


@lru_cache(maxsize=1)
def load_lst_mint_registry() -> dict[str, LstRegistryEntry]:
    """Parse data/solana_lst_mints.yaml into protocol slug → LstRegistryEntry."""
    try:
        resource = files("tvl_scanner.data").joinpath("solana_lst_mints.yaml")
        raw = resource.read_text(encoding="utf-8")
    except Exception as exc:
        log.error("solana lst mint registry not found: %s", exc)
        return {}

    data = yaml.safe_load(raw) or []
    if not isinstance(data, list):
        return {}

    mapping: dict[str, LstRegistryEntry] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        slug = item.get("slug")
        mint = item.get("mint")
        stake_pool = item.get("stake_pool")
        if not isinstance(slug, str):
            continue
        # Accept entries with mint OR stake_pool (or both). Wrapper-detection
        # only needs stake_pool; TVL sanity check only needs mint.
        if not isinstance(mint, str) and not isinstance(stake_pool, str):
            continue
        mapping[slug.strip().lower()] = LstRegistryEntry(
            slug=slug.strip().lower(),
            mint=mint.strip() if isinstance(mint, str) else None,
            stake_pool=stake_pool.strip() if isinstance(stake_pool, str) else None,
        )
    log.info("loaded %d solana LST mint entries", len(mapping))
    return mapping


async def _rpc(
    method: str,
    params: list[Any],
    *,
    client: httpx.AsyncClient | None = None,
) -> Any:
    """Make a JSON-RPC POST to the public Solana RPC. Returns result field or None."""
    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(timeout=15.0)
    assert client is not None
    try:
        response = await client.post(
            SOLANA_RPC_URL,
            json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
        )
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict):
            return data.get("result")
        return None
    except (httpx.HTTPError, ValueError) as exc:
        log.debug("solana rpc %s failed: %s", method, exc)
        return None
    finally:
        if owns_client:
            await client.aclose()


async def check_wrapper_program(
    account_address: str, *, client: httpx.AsyncClient | None = None
) -> WrapperMatch | None:
    """Query the Solana account's owner field; return a WrapperMatch if recognized.

    Returns None if:
      - the address is not a valid Solana address (synthetic defillama: prefix)
      - the RPC call fails
      - the owner is not in our registry
    """
    if not account_address or ":" in account_address or account_address.startswith("0x"):
        return None

    result = await _rpc(
        "getAccountInfo",
        [account_address, {"encoding": "base64"}],
        client=client,
    )
    if not isinstance(result, dict):
        return None
    value = result.get("value")
    if not isinstance(value, dict):
        return None

    owner = value.get("owner")
    if not isinstance(owner, str):
        return None

    registry = load_wrapper_registry()
    entry = registry.get(owner)
    if entry is None:
        return None

    return WrapperMatch(entry=entry, account_owner=owner)


async def fetch_lst_supply(
    mint_address: str, *, client: httpx.AsyncClient | None = None
) -> float | None:
    """Return the LST mint's total supply (UI amount) or None on failure."""
    result = await _rpc("getTokenSupply", [mint_address], client=client)
    if not isinstance(result, dict):
        return None
    value = result.get("value")
    if not isinstance(value, dict):
        return None
    raw = value.get("uiAmount")
    if isinstance(raw, (int, float)):
        return float(raw)
    return None


async def compute_on_chain_lst_tvl(
    slug: str,
    native_token_usd: float,
    *,
    client: httpx.AsyncClient | None = None,
) -> float | None:
    """For a known LST slug, return actual on-chain TVL in USD or None.

    Caller is responsible for native token price (via the existing PriceCache).
    """
    if not slug or native_token_usd <= 0:
        return None
    registry = load_lst_mint_registry()
    entry = registry.get(slug.strip().lower())
    if not entry or not entry.mint:
        return None
    supply = await fetch_lst_supply(entry.mint, client=client)
    if supply is None:
        return None
    return supply * native_token_usd


async def check_lst_wrapper(
    slug: str, *, client: httpx.AsyncClient | None = None
) -> WrapperMatch | None:
    """For a known LST slug, look up its stake_pool address and check if that
    account is owned by a registered wrapper program (e.g. SPL Stake Pool).

    This is the bridge between catalog candidates (which have synthetic
    `defillama:slug` addresses, not real on-chain addresses) and the wrapper
    detection. Without this, J1 couldn't apply to catalog-discovered Solana
    candidates because they don't have a real address to query.
    """
    if not slug:
        return None
    registry = load_lst_mint_registry()
    entry = registry.get(slug.strip().lower())
    if not entry or not entry.stake_pool:
        return None
    return await check_wrapper_program(entry.stake_pool, client=client)
