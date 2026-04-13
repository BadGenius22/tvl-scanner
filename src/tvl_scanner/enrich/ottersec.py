"""OtterSec reproducible-build verification for Solana programs.

Solana programs are eBPF bytecode compiled from Rust. Unlike EVM where
Etherscan matches deployed bytecode against recompiled source, Solana
verification is **reproducible builds**: the team publishes source + exact
git commit + build args, anyone runs `solana-verify build` at that commit,
the resulting bytecode hash is compared against the deployed program, and
if matching the entry is registered in OtterSec's public database.

Canonical endpoint: `https://verify.osec.io/status/<program_id>`
  Public, no API key, unauthenticated.

Response when verified:
    {
      "is_verified": true,
      "message": "On chain program verified",
      "on_chain_hash": "...",
      "executable_hash": "...",
      "last_verified_at": "2024-XX-XX",
      "repo_url": "https://github.com/...",
      "commit": "abc123def",
      "signer": "..."
    }

Response when not in the database:
    {
      "is_verified": false,
      "message": "Program not found"
    }
  or a 404 status code.

Coverage reality: as of early 2026, probably <20% of deployed Solana programs
are in OtterSec's DB. Big ones are (Jito, Kamino, Marinade, Drift, Jupiter,
Raydium). Most fresh deployments are not. So `is_verified=None` is a common
and expected state — we do NOT flag it as a red flag the way we do for EVM,
because EVM verification is nearly universal while Solana verification is
aspirational.
"""

from __future__ import annotations

import logging
import re

import httpx

from tvl_scanner.enrich.etherscan import VerificationResult
from tvl_scanner.http import HttpError, get_json

log = logging.getLogger(__name__)


# Solana program IDs are base58-encoded 32-byte ed25519 public keys, which
# serialize to 32-44 characters using the base58 alphabet (no 0, O, I, l).
_BASE58_ALPHABET = re.compile(r"^[1-9A-HJ-NP-Za-km-z]+$")

_EMPTY_UNKNOWN = VerificationResult(is_verified=False)


def _is_solana_program_id(address: str) -> bool:
    """Loose sanity check for a Solana base58 program ID.

    Rejects EVM addresses (start with 0x), synthetic catalog addresses
    (start with "defillama:"), and obviously-malformed strings. Does NOT
    validate ed25519 curve membership — the OtterSec endpoint will simply
    return is_verified=False for anything it doesn't recognize.
    """
    if not address or len(address) < 32 or len(address) > 44:
        return False
    if address.startswith("0x") or ":" in address:
        return False
    return bool(_BASE58_ALPHABET.match(address))


def _parse_ottersec_response(payload: dict) -> VerificationResult:
    """Parse an OtterSec verify API response into our shared VerificationResult.

    Field mapping:
        is_verified  → is_verified (direct)
        commit       → compiler_version ("solana-verify@<commit[:12]>")
                       Using compiler_version as the "verification provenance"
                       slot lets us reuse the existing schema without adding
                       fields specific to one chain's verification model.
        repo_url     → not stored on the candidate record (DefiLlama github_repo
                       already captures the repo; the scanner doesn't currently
                       need to track the exact verified commit separately).

    Solana has no proxy concept in the EIP-1967 sense, so is_proxy stays False
    and proxy_impl_address stays None. contract_name is left None because the
    OtterSec response doesn't carry a human-readable name — that comes from
    DefiLlama or on-chain IDL discovery, neither of which we do here.
    """
    is_verified = bool(payload.get("is_verified"))
    if not is_verified:
        return _EMPTY_UNKNOWN

    commit_raw = payload.get("commit")
    commit_short = None
    if isinstance(commit_raw, str) and commit_raw:
        commit_short = commit_raw[:12]

    compiler_version = (
        f"solana-verify@{commit_short}" if commit_short else "solana-verify"
    )

    return VerificationResult(
        is_verified=True,
        contract_name=None,
        compiler_version=compiler_version,
        is_proxy=False,
        proxy_impl_address=None,
    )


async def check_ottersec_verification(
    address: str, *, client: httpx.AsyncClient | None = None
) -> VerificationResult:
    """Query OtterSec for Solana program verification status.

    Returns a VerificationResult with `is_verified=False` on any non-success
    path (invalid address, HTTP failure, program not in DB). The caller cannot
    distinguish "explicitly unverified" from "not in database" — both yield
    the same empty result. That's intentional: Solana verification is opt-in
    and missing-from-DB is the DEFAULT state for most deployed programs, so
    treating it as a red flag would be misleading.

    For EVM addresses or synthetic catalog addresses, returns empty without
    hitting the API.
    """
    if not _is_solana_program_id(address):
        return _EMPTY_UNKNOWN

    url = f"https://verify.osec.io/status/{address}"

    try:
        payload = await get_json(url, client=client)
    except HttpError as exc:
        # 404 or 5xx — OtterSec returns 404 for programs that were never
        # submitted. Not an error, just "unknown".
        log.debug("ottersec verification fetch failed for %s: %s", address, exc)
        return _EMPTY_UNKNOWN

    if not isinstance(payload, dict):
        return _EMPTY_UNKNOWN

    return _parse_ottersec_response(payload)
