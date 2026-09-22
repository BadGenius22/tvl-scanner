#!/usr/bin/env python3
"""dune_sigscan — ecosystem-wide hunt for Lien-family clones via Dune + grep.app.

Hunt 2 (event twins): every ethereum address that ever emitted Lien BondMaker's
distinctive event signatures (works on unverified/redeployed clones).
Hunt 3 (bytecode twins): ethereum.contracts rows whose deployed bytecode equals
(or shares the first N bytes with) the two exploited BondMaker instances.
Hunt 1 (source grep, fallback): grep.app over public GitHub for the distinctive
source strings (Dune has no verified-source table).

Results: artifacts/dune/*.json
Run: python3 scripts/dune_sigscan.py
"""
import json
import os
import time
import urllib.request
from Crypto.Hash import keccak

import importlib.util
spec = importlib.util.spec_from_file_location("tier0", os.path.join("scripts", "tier0_check.py"))
tier0 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tier0)
ALCHEMY = None
for line in open(".env"):
    if line.startswith("ALCHEMY_API_KEY") and "=" in line:
        ALCHEMY = line.split("=", 1)[1].strip()
if ALCHEMY:
    tier0.RPC["ethereum"].insert(0, f"https://eth-mainnet.g.alchemy.com/v2/{ALCHEMY}")

DUNE_KEY = None
for line in open(".env"):
    if line.startswith("DUNE_API_KEY") and "=" in line:
        DUNE_KEY = line.split("=", 1)[1].strip()

OUT = "artifacts/dune"
os.makedirs(OUT, exist_ok=True)
QID = 8762730  # reusable scratch query

BONDMAKERS = {
    "BMCE_0xDA6FC562": "0xDA6FC5625E617bB92F5359921D43321cEbC6BEf0",
    "BMCE_0x843225CF": "0x843225CF6e663e4454732D6B551A737Ac7b47de0",
}
EVENTS = {
    "LogNewBondGroup": "LogNewBondGroup(uint256,uint256,uint64,bytes32[])",
    "LogExchangeEquivalentBonds": "LogExchangeEquivalentBonds(address,uint256,uint256,uint256)",
    "LogIssueNewBonds": "LogIssueNewBonds(uint256,address,uint256)",
}


def topic0(sig):
    k = keccak.new(digest_bits=256)
    k.update(sig.encode())
    return "0x" + k.hexdigest()


def dune(method, path, body=None, timeout=40):
    req = urllib.request.Request(
        f"https://api.dune.com{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers={"X-DUNE-API-KEY": DUNE_KEY, "Content-Type": "application/json"},
        method=method,
    )
    return json.load(urllib.request.urlopen(req, timeout=timeout))


def run_dune_sql(sql, n=500, poll_secs=180):
    dune("PATCH", f"/api/v1/query/{QID}", {"query_sql": sql})
    dune("POST", f"/api/v1/query/{QID}/execute")
    deadline = time.time() + poll_secs
    while time.time() < deadline:
        time.sleep(4)
        d = dune("GET", f"/api/v1/query/{QID}/results?limit={n}")
        if d.get("is_execution_finished"):
            err = (d.get("error") or {}).get("message", "")
            if d["state"] != "QUERY_STATE_COMPLETED":
                return None, err
            return (d.get("result", {}).get("rows") or []), None
    return None, "timeout"


def runtime_code(addr):
    return tier0.rpc("ethereum", "eth_getCode", [addr.lower(), "latest"])


def hunt_event_twins():
    topics = {name: topic0(sig) for name, sig in EVENTS.items()}
    print("event topic hashes:", json.dumps(topics, indent=1))
    # topic0 is varbinary -> hex literals, not quoted strings
    t = ",".join(f"X'{h[2:]}'" for h in topics.values())
    sql = (
        "SELECT topic0, \"contract_address\" AS emitter, count(*) AS n, min(block_time) AS first_seen, max(block_time) AS last_seen "
        f"FROM ethereum.logs WHERE topic0 IN ({t}) "
        "GROUP BY 1,2 ORDER BY n DESC LIMIT 500"
    )
    rows, err = run_dune_sql(sql)
    if err:
        print("event-twin hunt FAILED:", err)
        return

    def norm(h):
        h = str(h)
        return ("0x" + h[-64:]) if not h.lower().startswith("0x") else h.lower()

    named = []
    for r in rows:
        hexh = norm(r["topic0"])
        name = next((k for k, v in topics.items() if norm(v) == hexh), hexh[:14] + "…")
        r["event"] = name
        named.append(r)
        print(f"  {name:28} {r['emitter']}  n={r['n']}  {str(r['first_seen'])[:10]} .. {str(r['last_seen'])[:10]}")
    json.dump(named, open(f"{OUT}/event_twins.json", "w"), indent=1)
    print(f"event twins: {len(named)} emitters -> {OUT}/event_twins.json")


def hunt_bytecode_twins():
    results = []
    for label, addr in BONDMAKERS.items():
        code = runtime_code(addr)  # '0x...' hex string
        hexfull = code[2:]
        print(f"{label}: runtime code {(len(hexfull)) // 2} bytes")
        variants = [("exact", hexfull), ("prefix", hexfull[:1020])]
        for mode, hexneedle in variants:
            lhs = "code" if mode == "exact" else "substr(code,1,510)"
            sql = (
                "SELECT address, name, created_at FROM ethereum.contracts "
                f"WHERE {lhs} = X'{hexneedle}' LIMIT 200"
            )
            rows, err = run_dune_sql(sql)
            if err:
                print(f"  {mode} hunt FAILED:", err[:200])
                continue
            for r in rows:
                r.update({"match": mode, "twin_of": label})
                results.append(r)
                print(f"  [{mode}] twin of {label}: {r['address']} ({r.get('name')}) created {str(r.get('created_at', ''))[:10]}")
            time.sleep(2)
    json.dump(results, open(f"{OUT}/bytecode_twins.json", "w"), indent=1)
    print(f"bytecode twins: {len(results)} -> {OUT}/bytecode_twins.json")


def hunt_source_grep():
    """grep.app over public GitHub for distinctive Lien source strings."""
    hits = {}
    for q in ["exchangeEquivalentBonds", "exceptionCount", "IDOLvsETHBoxExchange", "registerNewBondGroup"]:
        try:
            url = f"https://grep.app/api/search?q={urllib.request.quote(q)}"
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "tvl-scanner"}), timeout=25) as r:
                d = json.load(r)
            total = d.get("hits", {}).get("total")
            repos = sorted({h["repo"]["raw"] for h in d.get("hits", {}).get("hits", [])})
            hits[q] = {"total": total, "repos": repos}
            print(f"grep.app '{q}': {total} hits in {len(repos)} repos")
            for rp in repos[:10]:
                print("   ", rp)
        except Exception as e:
            print(f"grep.app '{q}' failed: {e}")
        time.sleep(1)
    json.dump(hits, open(f"{OUT}/source_grep.json", "w"), indent=1)


if __name__ == "__main__":
    import sys
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("all", "events"):
        hunt_event_twins()
    if which in ("all", "bytecode"):
        hunt_bytecode_twins()
    if which in ("all", "source"):
        hunt_source_grep()
