"""Tests for the deploy-watch orchestrator (on-chain deploy/upgrade triggers)."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from tvl_scanner.deploy_watch import (
    WatchTarget,
    check_target,
    load_state,
    load_watchlist,
    run_deploy_watch,
    save_state,
)

# Real Marinade upgradeable-program addresses (program -> its ProgramData).
PROG = "MarBmsSgKXdrN1egZf5sqe1TMai9K1rChYNDJgjq7aD"
PROGDATA = "MarPr0gDataAcct1111111111111111111111111111"
BASELINE_SLOT = 229946024


def _solana_rpc(slot: int) -> Any:
    """A fake `post_json` that answers Marinade's two getAccountInfo calls."""

    async def fake(url: str, *, json_body: Any, headers: Any = None, client: Any = None) -> Any:
        method, params = json_body["method"], json_body["params"]
        if method == "getAccountInfo" and params[0] == PROG:
            return {"result": {"value": {"data": {"parsed": {"info": {"programData": PROGDATA}}}}}}
        if method == "getAccountInfo" and params[0] == PROGDATA:
            return {"result": {"value": {"data": {"parsed": {"info": {"slot": slot}}}}}}
        raise AssertionError(f"unexpected call {method} {params}")

    return fake


def _evm_rpc(code: str) -> Any:
    async def fake(url: str, *, json_body: Any, headers: Any = None, client: Any = None) -> Any:
        assert json_body["method"] == "eth_getCode"
        return {"result": code}

    return fake


def _sol_target() -> WatchTarget:
    return WatchTarget(
        slug="marinade", chain="solana", note="n", program_id=PROG, baseline_slot=BASELINE_SLOT
    )


def _evm_target() -> WatchTarget:
    return WatchTarget(
        slug="pm", chain="evm", note="n", address="0x6c044c0D3801499bCAbfAd458B70880bc518e9F7"
    )


# ---------------------------------------------------------------------------
# watchlist parsing
# ---------------------------------------------------------------------------


def test_load_watchlist_parses_seed() -> None:
    slugs = {t.slug: t for t in load_watchlist()}
    assert {"marinade", "defisaver-aavev4"} <= set(slugs)
    assert slugs["marinade"].chain == "solana"
    assert slugs["marinade"].baseline_slot == BASELINE_SLOT
    assert slugs["defisaver-aavev4"].chain == "evm"
    assert slugs["defisaver-aavev4"].address is not None


def test_load_watchlist_filters_by_slug() -> None:
    assert {t.slug for t in load_watchlist({"marinade"})} == {"marinade"}


# ---------------------------------------------------------------------------
# solana slot logic
# ---------------------------------------------------------------------------


async def test_solana_dormant_when_slot_unchanged(monkeypatch: Any) -> None:
    monkeypatch.setattr("tvl_scanner.deploy_watch._solana_rpc", lambda: "http://rpc")
    monkeypatch.setattr("tvl_scanner.deploy_watch.post_json", _solana_rpc(BASELINE_SLOT))
    r = await check_target(_sol_target(), {}, None)  # type: ignore[arg-type]
    assert r.triggered is False
    assert r.current == str(BASELINE_SLOT)


async def test_solana_triggered_on_upgrade(monkeypatch: Any) -> None:
    monkeypatch.setattr("tvl_scanner.deploy_watch._solana_rpc", lambda: "http://rpc")
    monkeypatch.setattr("tvl_scanner.deploy_watch.post_json", _solana_rpc(BASELINE_SLOT + 5000))
    r = await check_target(_sol_target(), {}, None)  # type: ignore[arg-type]
    assert r.triggered is True
    assert r.current == str(BASELINE_SLOT + 5000)


# ---------------------------------------------------------------------------
# evm code logic
# ---------------------------------------------------------------------------


async def test_evm_dormant_when_no_code(monkeypatch: Any) -> None:
    monkeypatch.setattr("tvl_scanner.deploy_watch._evm_rpc", lambda name: "http://rpc")
    monkeypatch.setattr("tvl_scanner.deploy_watch.post_json", _evm_rpc("0x"))
    r = await check_target(_evm_target(), {}, None)  # type: ignore[arg-type]
    assert r.triggered is False
    assert r.current == "EMPTY"


async def test_evm_triggered_on_first_code(monkeypatch: Any) -> None:
    monkeypatch.setattr("tvl_scanner.deploy_watch._evm_rpc", lambda name: "http://rpc")
    monkeypatch.setattr("tvl_scanner.deploy_watch.post_json", _evm_rpc("0x6080604052"))
    r = await check_target(_evm_target(), {}, None)  # type: ignore[arg-type]
    assert r.triggered is True
    assert r.current.startswith("sha256:")


async def test_error_is_captured(monkeypatch: Any) -> None:
    async def boom(url: str, *, json_body: Any, headers: Any = None, client: Any = None) -> Any:
        return {"error": {"code": -32000, "message": "nope"}}

    monkeypatch.setattr("tvl_scanner.deploy_watch._solana_rpc", lambda: "http://rpc")
    monkeypatch.setattr("tvl_scanner.deploy_watch.post_json", boom)
    r = await check_target(_sol_target(), {}, None)  # type: ignore[arg-type]
    assert r.triggered is False
    assert r.error is not None


# ---------------------------------------------------------------------------
# state + end-to-end
# ---------------------------------------------------------------------------


def test_state_roundtrip(tmp_path: Path) -> None:
    p = tmp_path / "state.json"
    save_state({"marinade": {"current": "1", "chain": "solana"}}, p)
    assert load_state(p) == {"marinade": {"current": "1", "chain": "solana"}}


async def test_run_triggers_then_incremental(tmp_path: Any, monkeypatch: Any) -> None:
    """First run fires on an upgrade; once state is saved, a rerun stays dormant."""
    monkeypatch.setattr("tvl_scanner.deploy_watch._solana_rpc", lambda: "http://rpc")
    monkeypatch.setattr("tvl_scanner.deploy_watch.post_json", _solana_rpc(BASELINE_SLOT + 9000))
    state_p, reports = tmp_path / "s.json", tmp_path / "reports"

    path1 = await run_deploy_watch(
        {"marinade"}, scan_date=date(2026, 7, 14), state_path=state_p, reports_dir=reports
    )
    assert "TRIGGERED" in Path(path1).read_text()
    assert load_state(state_p)["marinade"]["current"] == str(BASELINE_SLOT + 9000)

    # Rerun: on-chain slot unchanged and now equals the saved baseline -> dormant.
    path2 = await run_deploy_watch(
        {"marinade"}, scan_date=date(2026, 7, 15), state_path=state_p, reports_dir=reports
    )
    assert "TRIGGERED" not in Path(path2).read_text()
