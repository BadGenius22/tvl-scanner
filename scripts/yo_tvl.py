#!/usr/bin/env python3
"""yo_tvl — verified TVL snapshot of Yo protocol vaults across chains.

For each vault: totalAssets() (vault-level TVL incl. allocated positions the
vault values), totalSupply(), and the underlying token balance held directly by
the vault. Also snapshots the YO Oracle and worker contracts' balances.
Run: python3 scripts/yo_tvl.py
"""
import json
import os
import time
import urllib.request

ALCHEMY_KEY = None
for line in open(".env"):
    if line.startswith("ALCHEMY_API_KEY") and "=" in line:
        ALCHEMY_KEY = line.split("=", 1)[1].strip()

URLS = {
    "ethereum": f"https://eth-mainnet.g.alchemy.com/v2/{ALCHEMY_KEY}",
    "arbitrum": f"https://arb-mainnet.g.alchemy.com/v2/{ALCHEMY_KEY}",
    "base": f"https://base-mainnet.g.alchemy.com/v2/{ALCHEMY_KEY}",
}

VAULTS = [
    # (label, chain, vault, underlying, underlying_decimals)
    ("yoUSD",      "ethereum", "0x0000000f2eb9f69274678c76222b35eec7588a65", "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48", 6),
    ("yoUSD",      "arbitrum", "0x0000000f2eb9f69274678c76222b35eec7588a65", "0xaf88d065e77c8cC2239327C5EDb3A432268e5831", 6),
    ("yoUSD",      "base",     "0x0000000f2eb9f69274678c76222b35eec7588a65", "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913", 6),
    ("yoUSDT",     "ethereum", "0xb9a7da9e90d3b428083bae04b860faa6325b721e", "0xdac17f958d2ee523a2206206994597c13d831ec7", 6),
    ("yoUSD-Edge", "ethereum", "0x5dd8bfa6c5c68d05d25ef6143e05c11e26c4cdb7", "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48", 6),
    ("yoUSD-Edge", "arbitrum", "0x5dd8bfa6c5c68d05d25ef6143e05c11e26c4cdb7", "0xaf88d065e77c8cC2239327C5EDb3A432268e5831", 6),
    ("yoETH",      "ethereum", "0x3a43aec53490cb9fa922847385d82fe25d0e9de7", "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2", 18),
    ("yoBTC",      "ethereum", "0xbcbc8cb4d1e8ed048a6276a5e94a3e952660bcbc", "0xcbb7c0000ab88b473b1f5afd9ef808440eed33bf", 8),
    ("yoGOLD",     "ethereum", "0x586675a3a46b008d8408933cf42d8ff6c9cc61a1", "0x68749665FF8D2d112Fa859AA293F07A622782F38", 18),
    ("yoEUR",      "ethereum", "0x50c749ae210d3977adc824ae11f3c7fd10c871e9", "0x1aBaEA1f7C830bD89Acc67eC4af516284b1bC33c", 6),
]

TOTAL_ASSETS = "0x01e1d114"   # totalAssets()
TOTAL_SUPPLY  = "0x18160ddd"  # totalSupply()
BALANCE_OF    = "0x70a08231"  # balanceOf(address)
ORACLE = "0x6E879d0CcC85085A709eBf5539224f53d0D396B0"
WORKER = "0x5c28b54e7e1f9aafbdc5c563c1a460106f41bd58"
REDEEMER = "0x0439e941841f97dc1334d1a433379c6fcdcc2162"


def batch(url, reqs, tries=3):
    body = json.dumps(reqs).encode()
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(
                    url, data=body, headers={"Content-Type": "application/json"}), timeout=20) as r:
                return json.load(r)
        except Exception as e:
            last = e
            time.sleep(0.6 * (i + 1))
    raise last


def main():
    results = []
    for label, chain, vault, underlying, dec in VAULTS:
        url = URLS[chain]
        reqs = [
            {"jsonrpc": "2.0", "id": 0, "method": "eth_call", "params": [{"to": vault, "data": TOTAL_ASSETS}, "latest"]},
            {"jsonrpc": "2.0", "id": 1, "method": "eth_call", "params": [{"to": vault, "data": TOTAL_SUPPLY}, "latest"]},
            {"jsonrpc": "2.0", "id": 2, "method": "eth_call", "params": [{"to": underlying, "data": BALANCE_OF + vault[2:].rjust(64, "0")}, "latest"]},
        ]
        try:
            resp = batch(url, reqs)
        except Exception as e:
            print(f"{label:10} {chain:9} batch error: {str(e)[:70]}")
            continue
        vals = {}
        for r in resp:
            rid = r.get("id")
            res = r.get("result")
            vals[rid] = int(res, 16) if isinstance(res, str) and res not in ("0x",) else None
        ta = vals.get(0); ts = vals.get(1); idle = vals.get(2)
        ta = ta / 10**dec if ta is not None else None
        ts = ts / 10**dec if ts is not None else None
        idle = idle / 10**dec if idle is not None else None
        pps = (ta / ts) if (ta is not None and ts) else None
        rec = {"label": label, "chain": chain, "vault": vault, "totalAssets": ta,
               "totalSupply": ts, "idle_underlying_in_vault": idle, "pps": pps}
        results.append(rec)
        ta_s = f"{ta:,.2f}" if ta is not None else "n/a"
        ts_s = f"{ts:,.2f}" if ts is not None else "n/a"
        idle_s = f"{idle:,.2f}" if idle is not None else "n/a"
        pps_s = f"{pps:.6f}" if pps else "n/a"
        print(f"{label:10} {chain:9} totalAssets={ta_s:>16}  supply={ts_s:>16}  idle={idle_s:>16}  assets/share={pps_s}")
        time.sleep(0.15)

    # eth balance of oracle/worker/redeemer on ethereum (gas wallets)
    url = URLS["ethereum"]
    reqs = [{"jsonrpc": "2.0", "id": i, "method": "eth_getBalance", "params": [a, "latest"]}
            for i, a in enumerate([ORACLE, WORKER, REDEEMER])]
    resp = batch(url, reqs)
    for i, a in enumerate([ORACLE, WORKER, REDEEMER]):
        eth = int((resp[i].get("result") or "0x0"), 16) / 1e18
        print(f"{'infra':10} {'ethereum':9} {a}  ETH={eth:.4f}")

    json.dump(results, open("artifacts/yo/tvl_snapshot.json", "w"), indent=1)
    print("saved artifacts/yo/tvl_snapshot.json")


if __name__ == "__main__":
    main()
