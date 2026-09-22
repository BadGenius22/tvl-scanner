#!/usr/bin/env python3
"""protocol_family_scan — generalized deployer-walk + funding sweep (#sprint a).

For each protocol: start from anchor contracts, resolve creators, walk each
creator's full deployment history (normal + internal txs) across the chains
Etherscan V2 covers, and snapshot every discovered ethereum contract for funds.
Generalizes scripts/lien_family_scan.py to any protocol.

Anchors were collected from Dune's decoded registry (ethereum.contracts) and
DefiLlama. 'Funded' = ETH > 0.001 or any blue-chip token balance.

Run: python3 scripts/protocol_family_scan.py <slug> [<slug> ...]
     python3 scripts/protocol_family_scan.py all
"""
import importlib.util
import json
import os
import sys
import time
import urllib.request

spec = importlib.util.spec_from_file_location("tier0", os.path.join("scripts", "tier0_check.py"))
tier0 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tier0)
rpc, hexint = tier0.rpc, tier0.hexint

ALCHEMY = None
for line in open(".env"):
    if line.startswith("ALCHEMY_API_KEY") and "=" in line:
        ALCHEMY = line.split("=", 1)[1].strip()
if ALCHEMY:
    tier0.RPC["ethereum"].insert(0, f"https://eth-mainnet.g.alchemy.com/v2/{ALCHEMY}")
    tier0.RPC["bsc"].insert(0, f"https://bnb-mainnet.g.alchemy.com/v2/{ALCHEMY}")

KEY = None
for line in open(".env"):
    if line.startswith("ETHERSCAN_API_KEY") and "=" in line:
        KEY = line.split("=", 1)[1].strip()

CHAINS = {1: "ethereum", 56: "bsc", 137: "polygon", 10: "optimism", 42161: "arbitrum", 8453: "base"}
SNAPSHOT_CAP = 400

PROTOCOLS = {
    "sense": {"anchors": []},  # registry empty; add from docs if located
    "element": {"anchors": [
        "0xa2b3d083aa1eaa8453bfb477f062a208ed85cbbf",  # Tranche
        "0xeaa1cba8cc3cf01a92e9e853e90277b5b8a23e07",  # Tranche
        "0xb7561f547f3207edb42a6afa42170cd47add17bd",  # ConvergentCurvePoolFactory
        "0x6de73946eab234f1ee61256f10067d713af0e37a",  # VestingVault
    ]},
    "swivel": {"anchors": ["0x373a06bd3067f8da90239a47f316f09312b7800f"]},  # Swivel v3
    "yield-protocol": {"anchors": ["0xf94b5c5651c888d928439ab6514b93944eee6f48"]},  # Yield
    "saffron": {"anchors": [
        "0xb753428af26e81097e7fd17f40c88aaa3e04902c",  # SFI
        "0xf601912923d5fc15ad10bfdf5bbde949363fa703",  # SaffronStrategy
        "0xdc41bbb87200d4e28a244e008cfe39a459a87fde",  # DaiPool
    ]},
    "barnbridge": {"anchors": [
        "0x0391d2021f89dc339f60fff84546ea23e337750f",  # BOND
        "0xa7dad944581638ad570ce50e3e66e8cdea4f78ba",  # controller
        "0xa3c299eee1998f45c20010276684921ebe6423d9",  # CommunityVault
        "0x6324538cc222b43490dd95cebf72cf09d98d9dae",  # smartYield
    ]},
}


def es(module, action, chainid=1, tries=3, **params):
    q = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"https://api.etherscan.io/v2/api?chainid={chainid}&module={module}&action={action}&{q}&apikey={KEY}"
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "tvl-scanner"}), timeout=15) as r:
                d = json.load(r)
            if str(d.get("status")) == "0" and "rate" in str(d.get("message", "")).lower():
                raise RuntimeError("rate limited")
            return d
        except Exception as e:
            last = e
            time.sleep(0.5 * (i + 1))
    raise last


ALCHEMY_URL = f"https://eth-mainnet.g.alchemy.com/v2/{ALCHEMY}" if ALCHEMY else None


def _batch(reqs, tries=3):
    """Single POST with a JSON-RPC batch (Alchemy). Falls back to sequential rpc()."""
    if not ALCHEMY_URL:
        return None
    body = json.dumps(reqs).encode()
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(
                    ALCHEMY_URL, data=body, headers={"Content-Type": "application/json"}), timeout=20) as r:
                return json.load(r)
        except Exception as e:
            last = e
            time.sleep(0.5 * (i + 1))
    raise last


def snapshot(addr):
    """Batched snapshot: 7 calls in one POST instead of 7 round trips."""
    addr = addr.lower()
    out = {"code": 0, "eth": 0.0, "tokens": {}}
    toks = tier0.TOKENS["ethereum"]
    reqs = [
        {"jsonrpc": "2.0", "id": 0, "method": "eth_getCode", "params": [addr, "latest"]},
        {"jsonrpc": "2.0", "id": 1, "method": "eth_getBalance", "params": [addr, "latest"]},
    ]
    for j, (sym, taddr, dec) in enumerate(toks, start=2):
        reqs.append({"jsonrpc": "2.0", "id": j, "method": "eth_call",
                     "params": [{"to": taddr, "data": "0x70a08231" + addr.rjust(64, "0")}, "latest"]})
    try:
        resp = _batch(reqs)
    except Exception:
        resp = None
    if resp is None or not isinstance(resp, list):
        # fallback: sequential via tier0 failover
        return snapshot_seq(addr)
    by_id = {r.get("id"): r for r in resp}
    code = (by_id.get(0) or {}).get("result") or "0x"
    out["code"] = (len(code) - 2) // 2
    if out["code"] == 0:
        return out
    out["eth"] = hexint((by_id.get(1) or {}).get("result")) / 1e18
    for j, (sym, taddr, dec) in enumerate(toks, start=2):
        raw = (by_id.get(j) or {}).get("result") or "0x"
        if raw and raw != "0x":
            v = int(raw, 16) / 10**dec
            if v > 0:
                out["tokens"][sym] = round(v, 4)
    return out


def snapshot_seq(addr):
    addr = addr.lower()
    out = {"code": 0, "eth": 0.0, "tokens": {}}
    try:
        code = rpc("ethereum", "eth_getCode", [addr, "latest"])
        out["code"] = (len(code) - 2) // 2
        out["eth"] = hexint(rpc("ethereum", "eth_getBalance", [addr, "latest"])) / 1e18
    except Exception as e:
        out["rpc_err"] = str(e)[:60]
        return out
    if out["code"] == 0:
        return out
    for sym, taddr, dec in tier0.TOKENS["ethereum"]:
        try:
            h = rpc("ethereum", "eth_call", [{"to": taddr, "data": "0x70a08231" + addr.rjust(64, "0")}, "latest"])
        except Exception:
            h = "0x"
        if h and h != "0x":
            v = int(h, 16) / 10**dec
            if v > 0:
                out["tokens"][sym] = round(v, 4)
    return out


def sweep(slug, anchors):
    out_dir = os.path.join("artifacts", "family_sweeps", slug)
    os.makedirs(out_dir, exist_ok=True)
    creators = {}
    for a in anchors:
        try:
            d = es("contract", "getcontractcreation", contractaddresses=a)
            rows = d.get("result") or []
            if rows and isinstance(rows, list) and rows[0].get("contractCreator"):
                creators.setdefault(rows[0]["contractCreator"].lower(), []).append(a)
                print(f"  anchor {a[:12]}… creator {rows[0]['contractCreator']}", flush=True)
            else:
                print(f"  anchor {a[:12]}… creator unknown ({str(d.get('message'))[:30]})", flush=True)
        except Exception as e:
            print(f"  anchor {a[:12]}… lookup failed: {str(e)[:60]}", flush=True)
        time.sleep(0.3)

    deployments = {}
    for creator in creators:
        for chainid in CHAINS:
            for action in ("txlist", "txlistinternal"):
                try:
                    d = es("account", action, chainid=chainid, address=creator,
                           startblock=0, endblock=99999999, page=1, offset=1000, sort="asc")
                except Exception:
                    continue
                rows = d.get("result")
                if not isinstance(rows, list):
                    break
                for t in rows:
                    ca = t.get("contractAddress")
                    if ca:
                        deployments.setdefault((chainid, ca.lower()), creator)
                time.sleep(0.2)

    eth_addrs = sorted(set(a for (c, a) in deployments if c == 1))[:SNAPSHOT_CAP]
    non_eth = sorted({CHAINS[k[0]] for k in deployments if k[0] != 1})
    print(f"  deployments: {len(deployments)} total, {len(set(a for (c, a) in deployments if c == 1))} on ethereum"
          f" (cap {SNAPSHOT_CAP}); non-ethereum chains: {non_eth or 'none'}", flush=True)

    results, funded = [], []
    for i, addr in enumerate(eth_addrs):
        snap = snapshot(addr)
        is_funded = snap.get("eth", 0) > 0.001 or bool(snap.get("tokens"))
        if is_funded:
            funded.append({"address": addr, **snap})
        results.append({"address": addr, "creator": deployments[(1, addr)], **snap})
        if is_funded:
            print(f"  [{i+1}/{len(eth_addrs)}] FUNDED {addr} ETH={snap.get('eth',0):.4f} {snap.get('tokens') or ''}", flush=True)
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(eth_addrs)} snapshotted", flush=True)
        time.sleep(0.08)

    json.dump({"slug": slug, "anchors": anchors,
               "creators": sorted(creators),
               "deployments_by_chain": {f"{CHAINS[k[0]]}:{k[1]}": v for k, v in deployments.items()},
               "snapshot": results,
               "funded": funded},
              open(os.path.join(out_dir, "sweep.json"), "w"), indent=1)
    print(f"  => {slug}: {len(eth_addrs)} eth contracts, FUNDED: {len(funded)} -> {out_dir}/sweep.json", flush=True)
    return funded


def main():
    which = sys.argv[1:] or ["all"]
    slugs = list(PROTOCOLS) if "all" in which else which
    grand = {}
    for slug in slugs:
        anchors = PROTOCOLS[slug]["anchors"]
        print(f"=== {slug}: {len(anchors)} anchors", flush=True)
        if not anchors:
            print("  no anchors — skipped", flush=True)
            continue
        grand[slug] = sweep(slug, anchors)
    print("\n=== SPRINT SUMMARY (funded survivors per protocol) ===", flush=True)
    for slug, f in grand.items():
        tot_eth = sum(x.get("eth", 0) for x in f)
        print(f"  {slug:16} funded={len(f):3}  ETH={tot_eth:10.4f}", flush=True)


if __name__ == "__main__":
    main()
