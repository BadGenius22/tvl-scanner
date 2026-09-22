#!/usr/bin/env python3
"""lien_family_scan — enumerate every contract in the Lien family.

Starts from the 8 known Lien contracts (2 BondMakers, 3 OTC venues, LienToken,
2 attack-minted bond tokens), resolves their creators via Etherscan
getcontractcreation, then walks each creator's full deployment history
(normal + internal txs, i.e. factory creations) across the 6 chains Etherscan
V2 covers. Snapshots every discovered ethereum contract for funds.

Output: artifacts/lien/family_deployments.json + console table.
Run: python3 scripts/lien_family_scan.py
"""
import importlib.util
import json
import os
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

KEY = None
for line in open(".env"):
    if line.startswith("ETHERSCAN_API_KEY") and "=" in line:
        KEY = line.split("=", 1)[1].strip()

KNOWN = [
    "0xDA6FC5625E617bB92F5359921D43321cEbC6BEf0",  # BondMakerCollateralizedEth #1
    "0x843225CF6e663e4454732D6B551A737Ac7b47de0",  # BondMakerCollateralizedEth #2
    "0x656e5e976d523a427f05B0c212A22A89ccD9eF18",  # GeneralizedDotc
    "0x7db84492cfd27e47c39499d852decc2a01476a75",  # OTC venue #2
    "0x0949c77ad52602ac61b42d2de0eeb1b7cc79250f",  # OTC venue #3
    "0xab37e1358b639fd877f015027bb62d3ddaa7557e",  # LienToken
    "0x814a4cb84a0a1bb69126e4ac871a7f09fc417b49",  # IMT10160000
    "0x793ec4a2b6da9995b959ef73cd10fdc41a4a25a5",  # LBT10164000
]
CHAINS = {1: "ethereum", 56: "bsc", 137: "polygon", 42161: "arbitrum", 8453: "base", 10: "optimism"}
TOKENS = tier0.TOKENS["ethereum"]


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


def snapshot(addr):
    addr = addr.lower()
    out = {"code": 0, "eth": 0.0, "usd_tokens": {}}
    try:
        code = rpc("ethereum", "eth_getCode", [addr, "latest"])
        out["code"] = (len(code) - 2) // 2
        out["eth"] = hexint(rpc("ethereum", "eth_getBalance", [addr, "latest"])) / 1e18
    except Exception as e:
        out["rpc_err"] = str(e)[:60]
        return out
    if out["code"] == 0:
        return out
    for sym, taddr, dec in TOKENS:
        h = "0x"
        try:
            h = rpc("ethereum", "eth_call", [{"to": taddr, "data": "0x70a08231" + addr.rjust(64, "0")}, "latest"])
        except Exception:
            pass
        if h and h != "0x":
            v = int(h, 16) / 10**dec
            if v > 0:
                out["usd_tokens"][sym] = round(v, 4)
    return out


def main():
    # 1) creators of the known suite
    creators = {}
    for a in KNOWN:
        d = es("contract", "getcontractcreation", contractaddresses=a)
        rows = d.get("result") or []
        if rows and isinstance(rows, list) and rows[0].get("contractCreator"):
            row = rows[0]
            creators.setdefault(row["contractCreator"].lower(), []).append(
                {"contract": a, "tx": row["txHash"], "block": row["blockNumber"]})
            print(f"creator of {a[:12]}… = {row['contractCreator']}  (block {row['blockNumber']})", flush=True)
        else:
            print(f"creator of {a[:12]}… = ? ({str(d.get('message'))[:30]})", flush=True)
        time.sleep(0.3)

    # 2) every contract each creator ever deployed, on all 6 chains
    deployments = {}  # (chainid, addr) -> creator
    for creator in creators:
        for chainid, chname in CHAINS.items():
            for action in ("txlist", "txlistinternal"):
                try:
                    d = es("account", action, chainid=chainid, address=creator,
                           startblock=0, endblock=99999999, page=1, offset=1000, sort="asc")
                except Exception as e:
                    print(f"  {chname}/{action} failed: {str(e)[:60]}")
                    continue
                rows = d.get("result")
                if not isinstance(rows, list):
                    break
                for t in rows:
                    ca = t.get("contractAddress")
                    if ca:
                        deployments[(chainid, ca.lower())] = creator
                if action == "txlist" and len(rows) == 1000:
                    print(f"  {chname}: creator {creator[:10]} has >1000 txs, capping page 1")
                time.sleep(0.25)

    print(f"\ndiscovered deployments across all chains: {len(deployments)}", flush=True)
    by_chain = {}
    for (chainid, addr) in deployments:
        by_chain.setdefault(CHAINS[chainid], []).append(addr)
    for ch, addrs in by_chain.items():
        print(f"  {ch}: {len(addrs)}", flush=True)

    # 3) funding snapshot for ethereum contracts (name lookup only when funded)
    results = []
    eth_addrs = sorted(set(a for (c, a) in deployments if c == 1))
    for i, addr in enumerate(eth_addrs):
        snap = snapshot(addr)
        name = None
        funded = snap.get("eth", 0) > 0 or snap.get("usd_tokens")
        if funded:
            try:
                d = es("contract", "getsourcecode", address=addr)
                if isinstance(d.get("result"), list):
                    name = d["result"][0].get("ContractName")
            except Exception:
                pass
        results.append({"address": addr, "creator": deployments[(1, addr)],
                        "name": name, **snap})
        flag = " <== FUNDED" if funded else ""
        print(f"[{i+1}/{len(eth_addrs)}] {addr}  {str(name)[:34]:34} "
              f"code={snap.get('code',0):>6} ETH={snap.get('eth',0):.4f} {snap.get('usd_tokens') or ''}{flag}", flush=True)
        time.sleep(0.1)

    json.dump({"creators": {k: v for k, v in creators.items()},
               "deployments_all_chains": {f"{CHAINS[c]}:{a}": cr for (c, a), cr in deployments.items()},
               "ethereum_snapshot": results},
              open("artifacts/lien/family_deployments.json", "w"), indent=1)
    print("\nsaved artifacts/lien/family_deployments.json")


if __name__ == "__main__":
    main()
