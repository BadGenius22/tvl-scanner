"""Deploy-watch: alert when a watched on-chain program/contract goes live.

Companion to `delta_watch.py`. Delta-watch flags fresh *git commits* to fund-exit
paths; but some audit triggers are on-chain **deploy** events, not commits — a
protocol ships already-written, repo-visible code to mainnet, flipping a dormant
in-scope surface live. A git watcher can't see an on-chain upgrade; this can.

For each target we read a current deploy fingerprint and compare it to a baseline:
  - Solana: the upgradeable program's ProgramData `slot` (last-deployed slot).
    An upgrade increases the slot.
  - EVM: a hash of the contract's deployed bytecode (``EMPTY`` when there is no
    code). Code first appearing, or changing, is the trigger.

A change => TRIGGERED => the surface is now live; re-audit. Baselines start from
`data/deploy_watch_targets.yaml`; the last-observed fingerprint persists under
`ARTIFACTS_DIR/deploy_watch_state.json` so reruns are incremental.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import date
from importlib.resources import files
from pathlib import Path
from typing import Any

import httpx
import yaml

from tvl_scanner.config import get_secret, settings
from tvl_scanner.http import HttpError, post_json

log = logging.getLogger(__name__)

_EMPTY = "EMPTY"  # sentinel EVM fingerprint: address currently has no code


@dataclass(frozen=True)
class WatchTarget:
    """One deploy-watch entry parsed from the YAML watchlist."""

    slug: str
    chain: str  # "solana" | "evm"
    note: str
    enabled: bool = True
    # solana
    program_id: str | None = None
    baseline_slot: int | None = None
    # evm
    rpc: str = "ethereum"
    address: str | None = None
    baseline_codehash: str | None = None


@dataclass(frozen=True)
class DeployWatchResult:
    """Outcome of checking one target against its effective baseline."""

    slug: str
    chain: str
    triggered: bool
    baseline: str
    current: str
    note: str
    error: str | None = None


def load_watchlist(targets: set[str] | None = None) -> list[WatchTarget]:
    """Parse `data/deploy_watch_targets.yaml`; optionally filter to `targets` slugs."""
    resource = files("tvl_scanner.data").joinpath("deploy_watch_targets.yaml")
    data = yaml.safe_load(resource.read_text(encoding="utf-8")) or []
    out: list[WatchTarget] = []
    for entry in data:
        slug = str(entry["slug"]).lower()
        if targets is not None and slug not in targets:
            continue
        out.append(
            WatchTarget(
                slug=slug,
                chain=str(entry["chain"]).lower(),
                note=str(entry.get("note", "")).strip(),
                enabled=bool(entry.get("enabled", True)),
                program_id=entry.get("program_id"),
                baseline_slot=entry.get("baseline_slot"),
                rpc=str(entry.get("rpc", "ethereum")).lower(),
                address=entry.get("address"),
                baseline_codehash=entry.get("baseline_codehash"),
            )
        )
    return out


def _solana_rpc() -> str:
    key = get_secret("alchemy", required=False)
    return f"https://solana-mainnet.g.alchemy.com/v2/{key}" if key else settings().SOLANA_RPC_FALLBACK


def _evm_rpc(name: str) -> str:
    key = get_secret("alchemy", required=False)
    hosts = {"ethereum": "eth-mainnet", "base": "base-mainnet", "arbitrum": "arb-mainnet"}
    host = hosts.get(name)
    if key and host:
        return f"https://{host}.g.alchemy.com/v2/{key}"
    return settings().ETH_RPC_FALLBACK


async def _rpc(url: str, method: str, params: list[Any], client: httpx.AsyncClient) -> Any:
    """One JSON-RPC call; returns the `result` field or raises on an RPC error."""
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    resp = await post_json(url, json_body=body, client=client)
    if isinstance(resp, dict) and resp.get("error"):
        raise HttpError(f"RPC {method} error: {resp['error']}")
    return (resp or {}).get("result") if isinstance(resp, dict) else None


async def solana_deploy_slot(program_id: str, client: httpx.AsyncClient) -> int:
    """Return the last-deployed slot of an upgradeable Solana program.

    Program account -> its ProgramData address -> that account's `slot`.
    """
    opts = {"encoding": "jsonParsed", "commitment": "finalized"}
    prog = await _rpc(_solana_rpc(), "getAccountInfo", [program_id, opts], client)
    info = (((prog or {}).get("value") or {}).get("data") or {}).get("parsed", {}).get("info", {})
    programdata = info.get("programData")
    if not programdata:
        raise HttpError(f"{program_id}: not an upgradeable program (no programData)")
    pd = await _rpc(_solana_rpc(), "getAccountInfo", [programdata, opts], client)
    pd_info = (((pd or {}).get("value") or {}).get("data") or {}).get("parsed", {}).get("info", {})
    slot = pd_info.get("slot")
    if slot is None:
        raise HttpError(f"{program_id}: ProgramData {programdata} has no slot")
    return int(slot)


async def evm_code_fingerprint(address: str, rpc_name: str, client: httpx.AsyncClient) -> str:
    """Return a stable fingerprint of an EVM address's deployed code.

    ``EMPTY`` if the address has no code; otherwise a short SHA-256 of the code.
    (SHA-256 is only for change detection here — it need not match Ethereum's
    keccak codehash — which keeps this dependency-free.)
    """
    code = await _rpc(_evm_rpc(rpc_name), "eth_getCode", [address, "latest"], client)
    if not isinstance(code, str) or code in ("0x", "0x0", ""):
        return _EMPTY
    return "sha256:" + hashlib.sha256(bytes.fromhex(code[2:])).hexdigest()[:16]


async def check_target(
    target: WatchTarget, state: dict[str, dict[str, str]], client: httpx.AsyncClient
) -> DeployWatchResult:
    """Fetch the current fingerprint and decide whether the target has fired.

    The effective baseline is the last-observed value in `state` if present,
    otherwise the baseline declared in the YAML. This makes reruns incremental:
    once a trigger is acknowledged (state updated), it does not re-fire until the
    on-chain value changes again.
    """
    prior = state.get(target.slug, {}).get("current")
    try:
        if target.chain == "solana":
            if not target.program_id:
                raise HttpError("solana target missing program_id")
            slot = await solana_deploy_slot(target.program_id, client)
            current = str(slot)
            baseline_val = prior if prior is not None else target.baseline_slot
            baseline = "unknown" if baseline_val is None else str(baseline_val)
            triggered = baseline_val is not None and slot > int(baseline_val)
        elif target.chain == "evm":
            if not target.address:
                raise HttpError("evm target missing address")
            current = await evm_code_fingerprint(target.address, target.rpc, client)
            baseline_val = prior if prior is not None else (target.baseline_codehash or _EMPTY)
            baseline = str(baseline_val)
            triggered = current != _EMPTY and current != baseline
        else:
            raise HttpError(f"unknown chain '{target.chain}'")
    except HttpError as exc:
        return DeployWatchResult(
            target.slug, target.chain, False, "unknown", "error", target.note, str(exc)
        )
    return DeployWatchResult(
        target.slug, target.chain, triggered, baseline, current, target.note
    )


def _state_path() -> Path:
    return settings().artifacts_path / settings().DEPLOY_WATCH_STATE_FILE


def load_state(path: Path | None = None) -> dict[str, dict[str, str]]:
    p = path or _state_path()
    if not p.exists():
        return {}
    data = json.loads(p.read_text())
    return data if isinstance(data, dict) else {}


def save_state(state: dict[str, dict[str, str]], path: Path | None = None) -> None:
    p = path or _state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2, sort_keys=True))


def _report_markdown(results: list[DeployWatchResult], scan_date: date) -> str:
    fired = [r for r in results if r.triggered]
    errored = [r for r in results if r.error]
    lines = [
        f"# Deploy-watch — {scan_date.isoformat()}",
        "",
        f"Checked {len(results)} target(s): "
        f"**{len(fired)} triggered**, {len(errored)} error(s).",
        "",
        "| Slug | Chain | Status | Baseline | Current |",
        "|------|-------|--------|----------|---------|",
    ]
    for r in results:
        status = "🔴 TRIGGERED" if r.triggered else ("⚠️ error" if r.error else "· dormant")
        lines.append(f"| {r.slug} | {r.chain} | {status} | `{r.baseline}` | `{r.current}` |")
    if fired:
        lines += ["", "## Triggered — re-audit now", ""]
        for r in fired:
            lines += [f"### {r.slug} ({r.chain})", "", r.note, ""]
    if errored:
        lines += ["", "## Errors", ""]
        lines += [f"- **{r.slug}**: {r.error}" for r in errored]
    return "\n".join(lines) + "\n"


async def run_deploy_watch(
    targets: set[str] | None = None,
    *,
    scan_date: date | None = None,
    state_path: Path | None = None,
    reports_dir: Path | None = None,
) -> str:
    """Check every enabled watch target, write a report, persist state.

    Returns the report path. `scan_date`/`state_path`/`reports_dir` are injectable
    for tests; production uses today's date and the configured paths.
    """
    watchlist = [t for t in load_watchlist(targets) if t.enabled]
    if not watchlist:
        log.warning("deploy-watch: no enabled targets matched")
    state = load_state(state_path)
    sem = asyncio.Semaphore(settings().DEPLOY_WATCH_CONCURRENCY)

    async with httpx.AsyncClient(
        timeout=settings().HTTP_TIMEOUT_SECONDS, follow_redirects=True
    ) as client:

        async def _guarded(t: WatchTarget) -> DeployWatchResult:
            async with sem:
                return await check_target(t, state, client)

        results = await asyncio.gather(*(_guarded(t) for t in watchlist))

    for r in results:
        if r.error is None:
            state[r.slug] = {"current": r.current, "chain": r.chain}

    scan = scan_date or date.today()
    out_dir = reports_dir or settings().reports_path
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / f"{scan.isoformat()}-deploy-watch.md"
    report_path.write_text(_report_markdown(list(results), scan))
    save_state(state, state_path)

    fired = sum(1 for r in results if r.triggered)
    log.info("deploy-watch: %d target(s), %d triggered -> %s", len(results), fired, report_path)
    return str(report_path)
