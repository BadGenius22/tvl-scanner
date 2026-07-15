"""EVM bytecode hash check for known pool/factory deployments.

For each EVM pool-based candidate, query `eth_getCode` on the contract
address, hash the runtime bytecode with keccak256, and check against a
curated registry of known DEX pool bytecode hashes.

If a match is found, the candidate is a deployment of a known factory
(Uniswap V2 pair, V3 pool, Curve gauge, etc.) — i.e. a pool of an
audited protocol, not a fresh code shipment. The scanner attributes the
audit history of the upstream protocol and demotes priority.

Why this matters: the v0.4.1 scan ranked SushiSwap (Arbitrum) at #9 with
$244K, 0d old. It's a brand-new SushiSwap pair contract — same Uniswap
V2 pair bytecode that's been audited 3+ times. Not a fresh protocol.

The registry starts empty and grows as we encounter and verify pool
hashes for each protocol. Adding a new entry is a one-time manual hash
extraction (`cast keccak $(cast code <pool_address> --rpc-url ...)`).
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files

import httpx
import yaml

from tvl_scanner.config import get_secret
from tvl_scanner.discover.alchemy import CHAIN_TO_ALCHEMY_SUBDOMAIN, _rpc_call
from tvl_scanner.http import shared_ssl_context
from tvl_scanner.models import Chain

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class BytecodePatternEntry:
    """One registry entry for a known pool bytecode hash."""

    bytecode_hash: str  # 0x-prefixed lowercase keccak256 hex
    name: str
    upstream_protocol: str
    audit_count: int
    audit_url: str | None


@dataclass(frozen=True)
class BytecodeMatch:
    """Result of a bytecode pattern lookup against an on-chain contract."""

    entry: BytecodePatternEntry
    contract_address: str


@lru_cache(maxsize=1)
def load_bytecode_registry() -> dict[str, BytecodePatternEntry]:
    """Parse data/evm_pool_bytecode_hashes.yaml into hash → entry."""
    try:
        resource = files("tvl_scanner.data").joinpath("evm_pool_bytecode_hashes.yaml")
        raw = resource.read_text(encoding="utf-8")
    except Exception as exc:
        log.error("evm bytecode registry not found: %s", exc)
        return {}

    data = yaml.safe_load(raw) or []
    if not isinstance(data, list):
        return {}

    mapping: dict[str, BytecodePatternEntry] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            entry = BytecodePatternEntry(
                bytecode_hash=str(item["bytecode_hash"]).strip().lower(),
                name=str(item["name"]),
                upstream_protocol=str(item["upstream_protocol"]),
                audit_count=int(item.get("audit_count", 0)),
                audit_url=item.get("audit_url"),
            )
            mapping[entry.bytecode_hash] = entry
        except (KeyError, ValueError, TypeError) as exc:
            log.warning("skipping malformed bytecode registry entry: %s", exc)
    log.info("loaded %d evm pool bytecode entries", len(mapping))
    return mapping


def keccak256_hex(data: bytes) -> str:
    """Compute keccak256 (Ethereum-style SHA3) of raw bytes, return 0x-prefixed hex.

    Note: hashlib.sha3_256 is FIPS-202 SHA3, NOT keccak — they differ in the
    padding domain byte and produce entirely different digests. The registry
    holds real Ethereum keccak256 hashes (`cast keccak $(cast code <addr>)`),
    so anything but true keccak here would silently never match. hashlib's
    `new('keccak_256')` works on OpenSSL builds that expose it; otherwise we
    fall back to the pure-python permutation below (validated against the
    standard keccak256(b"") / keccak256(b"abc") vectors in the test suite).
    """
    try:
        h = hashlib.new("keccak_256")
        h.update(data)
        return "0x" + h.hexdigest()
    except ValueError:
        return "0x" + _keccak256_pure(data).hex()


_KECCAK_RC = (
    0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000,
    0x000000000000808B, 0x0000000080000001, 0x8000000080008081, 0x8000000000008009,
    0x000000000000008A, 0x0000000000000088, 0x0000000080008009, 0x000000008000000A,
    0x000000008000808B, 0x800000000000008B, 0x8000000000008089, 0x8000000000008003,
    0x8000000000008002, 0x8000000000000080, 0x000000000000800A, 0x800000008000000A,
    0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008,
)

# Rotation offsets r[x][y] from the Keccak reference.
_KECCAK_ROT = (
    (0, 36, 3, 41, 18),
    (1, 44, 10, 45, 2),
    (62, 6, 43, 15, 61),
    (28, 55, 25, 21, 56),
    (27, 20, 39, 8, 14),
)

_U64 = 0xFFFFFFFFFFFFFFFF


def _rol64(v: int, s: int) -> int:
    return ((v << s) | (v >> (64 - s))) & _U64 if s else v


def _keccak_f1600(state: list[int]) -> None:
    """In-place Keccak-f[1600] permutation. Lane l = x + 5*y, little-endian."""
    for rc in _KECCAK_RC:
        # theta
        c = [state[x] ^ state[x + 5] ^ state[x + 10] ^ state[x + 15] ^ state[x + 20]
             for x in range(5)]
        d = [c[(x - 1) % 5] ^ _rol64(c[(x + 1) % 5], 1) for x in range(5)]
        for x in range(5):
            for y in range(0, 25, 5):
                state[x + y] ^= d[x]
        # rho and pi
        b = [0] * 25
        for x in range(5):
            for y in range(5):
                b[y + 5 * ((2 * x + 3 * y) % 5)] = _rol64(
                    state[x + 5 * y], _KECCAK_ROT[x][y]
                )
        # chi
        for y in range(0, 25, 5):
            for x in range(5):
                state[x + y] = b[x + y] ^ (
                    (~b[(x + 1) % 5 + y]) & b[(x + 2) % 5 + y] & _U64
                )
        # iota
        state[0] ^= rc


def _keccak256_pure(data: bytes) -> bytes:
    """Pure-python keccak-256 (original Keccak padding, 0x01 domain byte)."""
    rate = 136  # bytes; capacity 512 bits
    state = [0] * 25

    # Multi-rate padding: 0x01 ... 0x80; a single leftover byte collapses
    # both markers into one 0x81 byte.
    pad_len = rate - (len(data) % rate)
    suffix = b"\x81" if pad_len == 1 else b"\x01" + b"\x00" * (pad_len - 2) + b"\x80"
    padded = data + suffix

    for block_start in range(0, len(padded), rate):
        block = padded[block_start : block_start + rate]
        for lane in range(rate // 8):
            state[lane] ^= int.from_bytes(block[lane * 8 : lane * 8 + 8], "little")
        _keccak_f1600(state)

    out = b"".join(state[lane].to_bytes(8, "little") for lane in range(4))
    return out


async def fetch_contract_code(
    chain: Chain, address: str, *, client: httpx.AsyncClient | None = None
) -> bytes | None:
    """Return the deployed runtime bytecode for `address` on `chain`, or None.

    Uses the existing Alchemy infrastructure (same RPC URL/auth as
    discover/alchemy.py). Returns None if Alchemy is not configured for
    this chain or the call fails.
    """
    subdomain = CHAIN_TO_ALCHEMY_SUBDOMAIN.get(chain)
    if not subdomain:
        return None
    api_key = get_secret("alchemy", required=False)
    if not api_key:
        return None
    url = f"https://{subdomain}.g.alchemy.com/v2/{api_key}"

    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(timeout=15.0, verify=shared_ssl_context())
    assert client is not None
    try:
        result = await _rpc_call(url, "eth_getCode", [address, "latest"], client)
        if not isinstance(result, str) or not result.startswith("0x"):
            return None
        if result == "0x":
            # No code at this address (EOA or destroyed contract)
            return None
        try:
            return bytes.fromhex(result[2:])
        except ValueError:
            return None
    finally:
        if owns_client:
            await client.aclose()


async def check_bytecode_match(
    chain: Chain, address: str, *, client: httpx.AsyncClient | None = None
) -> BytecodeMatch | None:
    """Look up the contract at `address` on `chain` against the bytecode registry.

    Returns a BytecodeMatch if the runtime bytecode hash matches a known
    pattern, None otherwise (or on any failure).
    """
    registry = load_bytecode_registry()
    if not registry:
        return None  # no patterns registered yet, nothing to check

    code = await fetch_contract_code(chain, address, client=client)
    if not code:
        return None
    digest = keccak256_hex(code)
    entry = registry.get(digest)
    if entry is None:
        return None
    return BytecodeMatch(entry=entry, contract_address=address)
