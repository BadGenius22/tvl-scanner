"""Tests for the Solana on-chain program resolver (enrich/solana_rpc.py).

The registry parser is tested against canned sumTokens text; the on-chain walk
is tested with a fake `post_json` that dispatches on RPC method + first param —
the same pattern as test_deploy_watch.py. No network, no `pass` access.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from tvl_scanner.enrich import solana_rpc as sr

# --- fixtures: realistic base58 ids (values are arbitrary; RPC is mocked) ----
TOKEN_ACCOUNT = "HwdwwKH1tMXo7ggTKcA5cdQrpcgqSoVib2eQh3BiyEQL"
AUTHORITY = "7Wpp33Dn5KKUFjaij4zKYy1XZ9kdBtHjUatAT6NcjjGt"
PROGRAM = "BULK2CNYn3mbgfYXEXiBBFxmmDChznpjQ4oRfce8w6R4"
PROGRAMDATA = "23M4ZyUfCzzXZBvuUT7yNji9xccQMhhTWwBv84S5g6mz"
UPGRADE_AUTH = "CUzXE1fSqYVFMh4TnmVBE7q2y3MijrEVsw7zbanyfuAM"
SLOT = 423580341
BLOCK_TIME = 1717239055  # 2024-06-01 UTC

REGISTRY = """
module.exports = {
  "some-other": {
    "solana": { "tokenAccounts": ["9OtherAcct1111111111111111111111111111111"] }
  },
  "bulk-trade": {
    "timetravel": false,
    "methodology": "Counts USDC deposited into the Bulk Trade Season 1 pre-deposits.",
    "solana": { "tokenAccounts": ["HwdwwKH1tMXo7ggTKcA5cdQrpcgqSoVib2eQh3BiyEQL"] }
  },
  "hylo": {
    "solana": {
      "tokenAccounts": [
        "2Y3TLkdGoJwbdizxqrZmQwNLYJyGKTgzC4tbetbkvQ43", // jitoSOL
        "7VNBQCDKt4cxLWW51suV8a6VAYC4R66CfyySiYJek7Rj"  // hyloSOL
      ]
    }
  },
  "custom-adapter": {
    "solana": { "owners": ["SomeOwner11111111111111111111111111111111111"] }
  }
}
"""


# --- registry parser (pure, no network) -------------------------------------


def test_extract_token_accounts_basic() -> None:
    assert sr._extract_token_accounts(REGISTRY, "bulk-trade") == [TOKEN_ACCOUNT]


def test_extract_token_accounts_ignores_comments() -> None:
    # Two quoted addresses; the `// jitoSOL` / `// hyloSOL` labels are not quoted
    # and must not leak into the result.
    accounts = sr._extract_token_accounts(REGISTRY, "hylo")
    assert accounts == [
        "2Y3TLkdGoJwbdizxqrZmQwNLYJyGKTgzC4tbetbkvQ43",
        "7VNBQCDKt4cxLWW51suV8a6VAYC4R66CfyySiYJek7Rj",
    ]


def test_extract_token_accounts_unknown_key() -> None:
    assert sr._extract_token_accounts(REGISTRY, "does-not-exist") == []


def test_extract_token_accounts_non_tokenaccounts_shape() -> None:
    # An adapter that uses `owners`/`tokens` rather than `tokenAccounts` is out
    # of scope for the vault walk and yields nothing (not a crash).
    assert sr._extract_token_accounts(REGISTRY, "custom-adapter") == []


def test_match_braces_nested() -> None:
    text = 'x = { "a": { "b": 1 }, "c": 2 } ;'
    start = text.find("{")
    assert sr._match_braces(text, start) == '{ "a": { "b": 1 }, "c": 2 }'


def test_match_braces_unbalanced_returns_none() -> None:
    assert sr._match_braces("{ oops", 0) is None
    assert sr._match_braces("no brace", 0) is None


# --- on-chain walk (mocked RPC) ---------------------------------------------


def _fake_rpc(
    *,
    token_authority_owner: str = PROGRAM,
    upgrade_authority: str | None = UPGRADE_AUTH,
    authority_owner: str = sr.SYSTEM_PROGRAM,
    slot: int | None = SLOT,
    block_time: int = BLOCK_TIME,
) -> Any:
    """Build a fake `post_json` answering the resolver's getAccountInfo chain."""

    async def fake(url: str, *, json_body: Any, headers: Any = None, client: Any = None) -> Any:
        method, params = json_body["method"], json_body["params"]
        if method == "getBlockTime":
            return {"result": block_time}
        if method != "getAccountInfo":
            raise AssertionError(f"unexpected method {method}")
        addr = params[0]
        if addr == TOKEN_ACCOUNT:
            return {
                "result": {
                    "value": {
                        "owner": sr.SPL_TOKEN_PROGRAM,
                        "data": {
                            "parsed": {"type": "account", "info": {"owner": AUTHORITY, "mint": "m"}},
                            "program": "spl-token",
                        },
                    }
                }
            }
        if addr == AUTHORITY:
            # PDA (or plain wallet, per token_authority_owner) — unparsed data.
            return {"result": {"value": {"owner": token_authority_owner, "data": ["ZGF0YQ==", "base64"]}}}
        if addr == PROGRAM:
            return {
                "result": {
                    "value": {
                        "executable": True,
                        "owner": sr.BPF_UPGRADEABLE_LOADER,
                        "data": {"parsed": {"type": "program", "info": {"programData": PROGRAMDATA}}},
                    }
                }
            }
        if addr == PROGRAMDATA:
            return {
                "result": {
                    "value": {
                        "owner": sr.BPF_UPGRADEABLE_LOADER,
                        "data": {
                            "parsed": {
                                "type": "programData",
                                "info": {"authority": upgrade_authority, "slot": slot},
                            }
                        },
                    }
                }
            }
        if upgrade_authority is not None and addr == upgrade_authority:
            return {"result": {"value": {"owner": authority_owner, "data": ["", "base64"], "space": 0}}}
        return {"result": {"value": None}}

    return fake


def _patch(monkeypatch: Any, fake: Any) -> None:
    monkeypatch.setattr("tvl_scanner.enrich.solana_rpc._solana_rpc", lambda: "http://rpc")
    monkeypatch.setattr("tvl_scanner.enrich.solana_rpc.post_json", fake)


async def test_resolve_single_keypair(monkeypatch: Any) -> None:
    _patch(monkeypatch, _fake_rpc())
    prof = await sr.resolve_solana_program("bulk-trade/index.js", registry_text=REGISTRY)
    assert prof is not None
    assert prof.program_id == PROGRAM
    assert prof.upgrade_authority == UPGRADE_AUTH
    assert prof.authority_type == sr.AUTH_SINGLE_KEYPAIR
    assert prof.deploy_slot == SLOT
    assert prof.deploy_date == datetime.fromtimestamp(BLOCK_TIME, tz=UTC).date()
    assert prof.tvl_token_account == TOKEN_ACCOUNT
    assert prof.loader == "upgradeable"


async def test_resolve_squads_multisig(monkeypatch: Any) -> None:
    squads = next(iter(sr.SQUADS_PROGRAMS))
    _patch(monkeypatch, _fake_rpc(authority_owner=squads))
    prof = await sr.resolve_solana_program("bulk-trade", registry_text=REGISTRY)
    assert prof is not None
    assert prof.authority_type == sr.AUTH_SQUADS_MULTISIG


async def test_resolve_immutable_program(monkeypatch: Any) -> None:
    _patch(monkeypatch, _fake_rpc(upgrade_authority=None))
    prof = await sr.resolve_solana_program("bulk-trade", registry_text=REGISTRY)
    assert prof is not None
    assert prof.upgrade_authority is None
    assert prof.authority_type == sr.AUTH_IMMUTABLE


async def test_resolve_custodial_authority_returns_none(monkeypatch: Any) -> None:
    # TVL account's authority is a plain wallet (System-owned) — no custom
    # program behind it, so there is nothing to resolve.
    _patch(monkeypatch, _fake_rpc(token_authority_owner=sr.SYSTEM_PROGRAM))
    prof = await sr.resolve_solana_program("bulk-trade", registry_text=REGISTRY)
    assert prof is None


async def test_resolve_squads_custodied_returns_none(monkeypatch: Any) -> None:
    # Authority owned directly by Squads = multisig custody, not a protocol
    # program. The walk should decline rather than mislabel Squads as the program.
    squads = next(iter(sr.SQUADS_PROGRAMS))
    _patch(monkeypatch, _fake_rpc(token_authority_owner=squads))
    prof = await sr.resolve_solana_program("bulk-trade", registry_text=REGISTRY)
    assert prof is None


async def test_resolve_unknown_module_returns_none(monkeypatch: Any) -> None:
    _patch(monkeypatch, _fake_rpc())
    prof = await sr.resolve_solana_program("no-such-adapter/index.js", registry_text=REGISTRY)
    assert prof is None


async def test_resolve_empty_module_returns_none(monkeypatch: Any) -> None:
    _patch(monkeypatch, _fake_rpc())
    assert await sr.resolve_solana_program("", registry_text=REGISTRY) is None
