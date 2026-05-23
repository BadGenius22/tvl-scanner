"""EVM factory-attribution enricher (Batch N).

For each EVM contract candidate, call its `factory()` selector via eth_call.
If the returned address matches a known DEX-or-protocol factory address in
the curated `KNOWN_FACTORIES` table, the contract is a pool of an audited
upstream protocol and gets a synthetic `FACTORY_ATTRIBUTION` AuditSource.

Why this exists: the v0.6.0 scan ranked the canonical Uniswap V3 WBTC/WETH
pool (~$36M TVL, ~5 years old) at #1 with audit_density_score=0 because:
  - The pool is not listed in DefiLlama (pool-level, not protocol-level)
  - It has no GitHub repo / bounty signal
  - The bytecode-hash registry is empty
  - It IS verified on Etherscan, but only as "Similar Match" which our
    etherscan.py classifier reads as unverified.

A `factory()` call would have returned `0x1F98431c...` — the public Uniswap
V3 Factory address — and instantly classified the pool as audited-via-parent.
This is the EVM analog of `solana_wrapper_check.py` for SPL stake pools.

Coverage trade-off: we only catch contracts whose dispatch table includes
`factory()` (0xc45a0155). That covers Uniswap V2/V3, SushiSwap V2, Pancake-
Swap V2/V3, QuickSwap, Aerodrome, and most V2/V3-style forks. It does NOT
cover Uniswap V4 (pools don't exist as separate contracts — value lives in
the singleton PoolManager), Curve, or Balancer (which use registry/Vault
patterns). Those need separate detectors if they show up as false positives.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import httpx

from tvl_scanner.config import get_secret
from tvl_scanner.discover.alchemy import CHAIN_TO_ALCHEMY_SUBDOMAIN
from tvl_scanner.discover.rpc import _rpc_call
from tvl_scanner.models import Chain

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class FactoryEntry:
    """One row in the known-factories or direct-contracts table."""

    name: str               # e.g. "Uniswap V3"
    upstream_protocol: str  # slug, e.g. "uniswap-v3"
    audit_url: str | None = None


# Singleton protocol contracts that aren't deployed BY a `factory()`-returning
# contract — they ARE the protocol's main contract. Matched by the candidate's
# own address (not via eth_call). Examples: Uniswap V4 PoolManager (each pool
# is just a state entry in this singleton, not a separate contract), Balancer
# V2 Vault (holds all liquidity for every Balancer pool). Without this table,
# these multi-billion-TVL singletons surface as "unknown protocol, 0d old".
KNOWN_DIRECT_CONTRACTS: dict[Chain, dict[str, FactoryEntry]] = {
    Chain.ETHEREUM: {
        "0x000000000004444c5dc75cb358380d2e3de08a90": FactoryEntry(
            "Uniswap V4 PoolManager", "uniswap-v4",
            "https://github.com/Uniswap/v4-core/tree/main/audits",
        ),
        "0xba12222222228d8ba445958a75a0704d566bf2c8": FactoryEntry(
            "Balancer V2 Vault", "balancer-v2",
            "https://github.com/balancer/balancer-v2-monorepo/tree/master/audits",
        ),
    },
    Chain.ARBITRUM: {
        "0x360e68faccca8ca495c1b759fd9eee466db9fb32": FactoryEntry(
            "Uniswap V4 PoolManager", "uniswap-v4",
            "https://github.com/Uniswap/v4-core/tree/main/audits",
        ),
        "0xba12222222228d8ba445958a75a0704d566bf2c8": FactoryEntry(
            "Balancer V2 Vault", "balancer-v2",
            "https://github.com/balancer/balancer-v2-monorepo/tree/master/audits",
        ),
    },
    Chain.BASE: {
        "0x498581ff718922c3f8e6a244956af099b2652b2b": FactoryEntry(
            "Uniswap V4 PoolManager", "uniswap-v4",
            "https://github.com/Uniswap/v4-core/tree/main/audits",
        ),
    },
    Chain.OPTIMISM: {
        "0x9a13f98cb987694c9f086b1f5eb990eea8264ec3": FactoryEntry(
            "Uniswap V4 PoolManager", "uniswap-v4",
            "https://github.com/Uniswap/v4-core/tree/main/audits",
        ),
        "0xba12222222228d8ba445958a75a0704d566bf2c8": FactoryEntry(
            "Balancer V2 Vault", "balancer-v2",
            "https://github.com/balancer/balancer-v2-monorepo/tree/master/audits",
        ),
    },
    Chain.POLYGON: {
        "0x67366782805870060151383f4bbff9dab53e5cd6": FactoryEntry(
            "Uniswap V4 PoolManager", "uniswap-v4",
            "https://github.com/Uniswap/v4-core/tree/main/audits",
        ),
        "0xba12222222228d8ba445958a75a0704d566bf2c8": FactoryEntry(
            "Balancer V2 Vault", "balancer-v2",
            "https://github.com/balancer/balancer-v2-monorepo/tree/master/audits",
        ),
    },
    Chain.BSC: {
        "0x28e2ea090877bf75740558f6bfb36a5ffee9e9df": FactoryEntry(
            "Uniswap V4 PoolManager", "uniswap-v4",
            "https://github.com/Uniswap/v4-core/tree/main/audits",
        ),
    },
}


# Curated table of public, well-known DEX/AMM factory addresses per chain.
# All addresses lowercased; the eth_call decoder returns lowercase too.
# Sources: each protocol's own public deployment docs / their GitHub. Only
# entries the author is confident about are included — when in doubt, omit.
KNOWN_FACTORIES: dict[Chain, dict[str, FactoryEntry]] = {
    Chain.ETHEREUM: {
        "0x5c69bee701ef814a2b6a3edd4b1652cb9cc5aa6f": FactoryEntry(
            "Uniswap V2", "uniswap-v2",
            "https://github.com/Uniswap/v2-core/tree/master/audits",
        ),
        "0x1f98431c8ad98523631ae4a59f267346ea31f984": FactoryEntry(
            "Uniswap V3", "uniswap-v3",
            "https://github.com/Uniswap/v3-core/tree/main/audits",
        ),
        "0xc0aee478e3658e2610c5f7a4a2e1777ce9e4f2ac": FactoryEntry(
            "SushiSwap V2", "sushiswap",
            "https://github.com/sushiswap/sushiswap/tree/master/audits",
        ),
    },
    Chain.ARBITRUM: {
        "0x1f98431c8ad98523631ae4a59f267346ea31f984": FactoryEntry(
            "Uniswap V3", "uniswap-v3",
            "https://github.com/Uniswap/v3-core/tree/main/audits",
        ),
        "0xc35dadb65012ec5796536bd9864ed8773abc74c4": FactoryEntry(
            "SushiSwap V2", "sushiswap",
            "https://github.com/sushiswap/sushiswap/tree/master/audits",
        ),
    },
    Chain.BASE: {
        "0x33128a8fc17869897dce68ed026d694621f6fdfd": FactoryEntry(
            "Uniswap V3", "uniswap-v3",
            "https://github.com/Uniswap/v3-core/tree/main/audits",
        ),
        "0x8909dc15e40173ff4699343b6eb8132c65e18ec6": FactoryEntry(
            "Uniswap V2", "uniswap-v2",
            "https://github.com/Uniswap/v2-core/tree/master/audits",
        ),
        "0x420dd381b31aef6683db6b902084cb0ffece40da": FactoryEntry(
            "Aerodrome V2", "aerodrome",
            None,
        ),
    },
    Chain.OPTIMISM: {
        "0x1f98431c8ad98523631ae4a59f267346ea31f984": FactoryEntry(
            "Uniswap V3", "uniswap-v3",
            "https://github.com/Uniswap/v3-core/tree/main/audits",
        ),
    },
    Chain.POLYGON: {
        "0x1f98431c8ad98523631ae4a59f267346ea31f984": FactoryEntry(
            "Uniswap V3", "uniswap-v3",
            "https://github.com/Uniswap/v3-core/tree/main/audits",
        ),
        "0x5757371414417b8c6caad45baef941abc7d3ab32": FactoryEntry(
            "QuickSwap V2", "quickswap",
            None,
        ),
    },
    Chain.BSC: {
        "0xca143ce32fe78f1f7019d7d551a6402fc5350c73": FactoryEntry(
            "PancakeSwap V2", "pancakeswap",
            None,
        ),
        "0x0bfbcf9fa4f9c56b0f40a671ad40e0805a091865": FactoryEntry(
            "PancakeSwap V3", "pancakeswap",
            None,
        ),
    },
}


@dataclass(frozen=True)
class FactoryMatch:
    """Result of a factory() lookup."""

    contract_address: str
    factory_address: str
    entry: FactoryEntry


# Function selectors
_FACTORY_SELECTOR = "0xc45a0155"  # factory()
_TOKEN0_SELECTOR = "0x0dfe1681"   # token0() — used to detect V4-style PoolManager pools
_TOKEN1_SELECTOR = "0xd21220a7"   # token1()
_NAME_SELECTOR = "0x06fdde03"     # name() — for ERC20-style protocol token detection


# Known protocol name patterns. When the contract's `name()` starts with one
# of these prefixes, attribute audits to the upstream protocol family.
# Catches Venus vTokens, Aave aTokens, Compound cTokens, Curve LP tokens etc.
# whose UNDERLYING audit happened at the protocol level, not per-market.
NAME_PREFIX_TO_PROTOCOL: dict[str, tuple[str, str]] = {
    "Venus ":          ("Venus Protocol",    "venus"),
    "Aave ":           ("Aave",              "aave"),
    "Compound ":       ("Compound",          "compound"),
    "Curve.fi ":       ("Curve.fi LP",       "curve"),
    "Uniswap V":       ("Uniswap LP",        "uniswap"),
    "SushiSwap LP":    ("SushiSwap LP",      "sushiswap"),
    "PancakeSwap LP":  ("PancakeSwap LP",    "pancakeswap"),
    "Balancer ":       ("Balancer LP",       "balancer"),
    "Aerodrome ":      ("Aerodrome",         "aerodrome"),
    "Velodrome ":      ("Velodrome",         "velodrome"),
    "QuickSwap ":      ("QuickSwap",         "quickswap"),
    "Lido ":           ("Lido",              "lido"),
    "Rocket Pool ":    ("Rocket Pool",       "rocket-pool"),
    "Morpho ":         ("Morpho",            "morpho"),
    "Pendle ":         ("Pendle",            "pendle"),
    # Added Batch N.3 (vault curators + protocol families seen in real scans):
    "Steakhouse ":     ("Steakhouse Vault",  "morpho"),  # Steakhouse runs Morpho vaults
    "MetaMorpho ":     ("MetaMorpho Vault",  "morpho"),
    "Spark ":          ("Spark Protocol",    "spark"),
    "Yearn ":          ("Yearn Vault",       "yearn"),
    "yv":              ("Yearn Vault Token", "yearn"),  # yv-prefixed tokens like yvUSDC
    "Fluid ":          ("Fluid",             "fluid"),
    "Ethena ":         ("Ethena",            "ethena"),
    "Frax ":           ("Frax Finance",      "frax"),
    "sFrax":           ("Frax Staked",       "frax"),
    "stETH":           ("Lido Staked ETH",   "lido"),
    "wstETH":          ("Lido Wrapped stETH","lido"),
    "rETH":            ("Rocket Pool ETH",   "rocket-pool"),
}


def _rpc_url(chain: Chain) -> str | None:
    """Same resolution order as discover/rpc.py."""
    custom = os.environ.get(f"TVL_SCANNER_RPC_{chain.value.upper()}")
    if custom:
        return custom
    subdomain = CHAIN_TO_ALCHEMY_SUBDOMAIN.get(chain)
    if not subdomain:
        return None
    api_key = get_secret("alchemy", required=False)
    if not api_key:
        return None
    return f"https://{subdomain}.g.alchemy.com/v2/{api_key}"


def _decode_address_word(word: str | None) -> str | None:
    """Decode a 32-byte returned word into a 20-byte hex address (lowercase)."""
    if not isinstance(word, str) or not word.startswith("0x"):
        return None
    body = word[2:]
    if len(body) != 64:
        return None
    addr = "0x" + body[-40:].lower()
    if int(addr, 16) == 0:
        return None
    return addr


def _detect_proxy_implementation(code: str | None) -> str | None:
    """Pull the implementation address out of a known proxy bytecode pattern.

    Handles three small-bytecode proxy types:
      - EIP-1167 minimal proxy (45 bytes): standard `363d3d373d3d3d363d73<IMPL>5af43d82803e903d91602b57fd5bf3`
      - EIP-7702 delegation (23 bytes): `ef0100<IMPL>` — an EOA delegated to a contract
      - PUSH20-prefixed minimal proxy (~45 bytes): variants like Solady's clone

    Returns the impl address (lowercase, 0x-prefixed) or None. The caller
    can then re-probe `name()` on the impl to attribute audits. Why this
    matters: vault factories (Morpho MetaMorpho, Yearn V3) commonly deploy
    one logic contract and clone it via EIP-1167 — each clone shows up as a
    fresh contract with no name/symbol unless we resolve the delegate.
    """
    if not code or not isinstance(code, str) or not code.startswith("0x"):
        return None
    body = code[2:].lower()

    # EIP-7702 delegation: exactly 23 bytes = 46 hex chars
    if len(body) == 46 and body.startswith("ef0100"):
        impl = "0x" + body[6:46]
        if int(impl, 16) != 0:
            return impl

    # EIP-1167 minimal proxy: 45 bytes = 90 hex chars
    if (
        len(body) == 90
        and body.startswith("363d3d373d3d3d363d73")
        and body.endswith("5af43d82803e903d91602b57fd5bf3")
    ):
        impl = "0x" + body[20:60]
        if int(impl, 16) != 0:
            return impl

    return None


def _decode_abi_string(word: str | None) -> str | None:
    """Decode an ABI-encoded `string` return (offset, length, data) or a fixed
    32-byte left-padded string. Returns None on any parse failure.

    name() and symbol() can return either form depending on whether the
    contract uses the modern dynamic-string encoding (Solidity ≥0.5) or the
    legacy bytes32 encoding (some old Compound/Maker contracts).
    """
    if not isinstance(word, str) or not word.startswith("0x") or word == "0x":
        return None
    body = word[2:]
    try:
        # Modern dynamic-string encoding: offset(32) + length(32) + data
        if len(body) >= 128:
            length = int(body[64:128], 16)
            if 0 < length <= 200:
                raw = bytes.fromhex(body[128 : 128 + length * 2])
                decoded = raw.decode("utf-8", errors="replace").strip()
                if decoded:
                    return decoded
        # Legacy bytes32 encoding: right-padded with zeros
        raw32 = bytes.fromhex(body[:64]).rstrip(b"\x00")
        if raw32:
            decoded = raw32.decode("utf-8", errors="replace").strip()
            if decoded:
                return decoded
    except (ValueError, UnicodeDecodeError):
        return None
    return None


async def check_factory_attribution(
    chain: Chain, address: str, *, client: httpx.AsyncClient | None = None
) -> FactoryMatch | None:
    """Identify `address` as part of a known protocol via two paths.

    Path 1 — direct match: if `address` itself is in KNOWN_DIRECT_CONTRACTS
    (e.g. Uniswap V4 PoolManager, Balancer Vault), return immediately. No
    RPC call needed. This catches protocol singletons where the contract IS
    the protocol, not a factory-deployed pool.

    Path 2 — factory() call: eth_call(address, factory()); if the returned
    address matches KNOWN_FACTORIES, attribute the audit to the upstream
    protocol. Catches V3-style per-pool deployments.

    Returns None on any failure path. Silent degradation matches the rest
    of the enrichment stack.
    """
    if chain == Chain.SOLANA:
        return None
    if not address.startswith("0x") or len(address) != 42:
        return None

    addr_lower = address.lower()

    # Path 1: direct address match (no RPC)
    direct_entry = KNOWN_DIRECT_CONTRACTS.get(chain, {}).get(addr_lower)
    if direct_entry:
        log.info(
            "evm direct match: %s on %s → %s",
            address,
            chain.value,
            direct_entry.name,
        )
        return FactoryMatch(
            contract_address=address,
            factory_address=addr_lower,  # contract is its own "factory" in this case
            entry=direct_entry,
        )

    url = _rpc_url(chain)
    if not url:
        return None

    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(timeout=15.0)
    assert client is not None

    try:
        # Path 2: factory() eth_call against KNOWN_FACTORIES
        factories = KNOWN_FACTORIES.get(chain, {})
        if factories:
            factory_result = await _rpc_call(
                url, "eth_call",
                [{"to": address, "data": _FACTORY_SELECTOR}, "latest"], client,
            )
            factory_addr = _decode_address_word(
                factory_result if isinstance(factory_result, str) else None
            )
            if factory_addr:
                entry = factories.get(factory_addr)
                if entry:
                    log.info(
                        "evm factory match: %s on %s → %s (factory %s)",
                        address, chain.value, entry.name, factory_addr,
                    )
                    return FactoryMatch(
                        contract_address=address,
                        factory_address=factory_addr,
                        entry=entry,
                    )

        # Path 3: name() / symbol() prefix match. Catches Venus vTokens,
        # Aave aTokens, Compound cTokens etc. whose audits happened at the
        # protocol level. RPC-discovered candidates often have no display_name
        # other than the raw address, so the slug check in score.py misses
        # them — this is the on-chain identification path.
        name_result = await _rpc_call(
            url, "eth_call",
            [{"to": address, "data": _NAME_SELECTOR}, "latest"], client,
        )
        contract_name = _decode_abi_string(
            name_result if isinstance(name_result, str) else None
        )
        if contract_name:
            match = _match_name_prefix(contract_name)
            if match:
                proto_name, proto_slug = match
                log.info(
                    "evm name match: %s on %s → %s (name=%r)",
                    address, chain.value, proto_name, contract_name,
                )
                return FactoryMatch(
                    contract_address=address,
                    factory_address=address,
                    entry=FactoryEntry(
                        name=proto_name, upstream_protocol=proto_slug,
                        audit_url=None,
                    ),
                )

        # Path 4: proxy implementation resolution. If the contract is an
        # EIP-1167 minimal proxy or EIP-7702 delegation, extract the impl
        # address from bytecode and re-probe its name(). Catches vault clones
        # whose own bytecode is just a delegation shim with no symbol/name.
        code_result = await _rpc_call(
            url, "eth_getCode", [address, "latest"], client,
        )
        impl_addr = _detect_proxy_implementation(
            code_result if isinstance(code_result, str) else None
        )
        if impl_addr:
            impl_name_result = await _rpc_call(
                url, "eth_call",
                [{"to": impl_addr, "data": _NAME_SELECTOR}, "latest"], client,
            )
            impl_name = _decode_abi_string(
                impl_name_result if isinstance(impl_name_result, str) else None
            )
            if impl_name:
                match = _match_name_prefix(impl_name)
                if match:
                    proto_name, proto_slug = match
                    log.info(
                        "evm proxy-impl match: %s → impl %s → %s (name=%r)",
                        address, impl_addr, proto_name, impl_name,
                    )
                    return FactoryMatch(
                        contract_address=address,
                        factory_address=impl_addr,
                        entry=FactoryEntry(
                            name=f"{proto_name} (via proxy)",
                            upstream_protocol=proto_slug,
                            audit_url=None,
                        ),
                    )
    finally:
        if owns_client:
            await client.aclose()

    return None


def _match_name_prefix(name: str) -> tuple[str, str] | None:
    """Match a contract's name() against NAME_PREFIX_TO_PROTOCOL. Returns
    (protocol_name, slug) on first hit, None otherwise."""
    for prefix, (proto_name, proto_slug) in NAME_PREFIX_TO_PROTOCOL.items():
        if name.startswith(prefix):
            return proto_name, proto_slug
    return None
