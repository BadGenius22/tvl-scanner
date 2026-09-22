#!/usr/bin/env python3
"""tier0_check — disambiguate the unverified-contract list from bugscan.

For every 'unverified' contract: confirm it is a contract, read native + major
stable/blue-chip token balances, resolve EIP-1967 proxy / beacon slots, and ask
Etherscan whether the implementation (or the contract itself) has verified source.
Classifies each into: verified-impl (false alarm) | unverified-impl (real finding)
| standalone-unverified | not-a-contract | empty (no holdings -> dropped).

Run: python3 scripts/tier0_check.py [--out artifacts/tier0_results.json]
"""
import json, re, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

RPC = {
    "ethereum": ["https://ethereum-rpc.publicnode.com", "https://eth.llamarpc.com", "https://cloudflare-eth.com"],
    "bsc": ["https://bsc-rpc.publicnode.com", "https://bsc-dataseed.binance.org"],
    "arbitrum": ["https://arbitrum-one-rpc.publicnode.com", "https://arb1.arbitrum.io/rpc"],
    "base": ["https://base-rpc.publicnode.com", "https://mainnet.base.org"],
    "polygon": ["https://polygon-bor-rpc.publicnode.com", "https://polygon-rpc.com"],
    "optimism": ["https://optimism-rpc.publicnode.com", "https://mainnet.optimism.io"],
}
RPC_IDX = {}
# blue-chip tokens worth checking for stranded TVL
TOKENS = {
    "ethereum": [("USDC", "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", 6), ("USDT", "0xdAC17F958D2ee523a2206206994597C13D831ec7", 6),
                 ("DAI", "0x6B175474E89094C44Da98b954EedeAC495271d0F", 18), ("WETH", "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2", 18),
                 ("WBTC", "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599", 8)],
    "bsc": [("USDT", "0x55d398326f99059fF775485246999027B3197955", 6), ("USDC", "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d", 6),
            ("WBNB", "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c", 18), ("CAKE", "0x0E09FaBB73Bd3Ade0a17ECC321fD13a19e81cE82", 18)],
    "arbitrum": [("USDC", "0xaf88d065e77c8cC2239327C5EDb3A432268e5831", 6), ("USDC.e", "0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8", 6),
                 ("WETH", "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1", 18), ("ARB", "0x912CE59144191C1204E64559FE8253a0e49E6548", 18)],
    "base": [("USDC", "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", 6), ("WETH", "0x4200000000000000000000000000000000000006", 18)],
    "polygon": [("USDC", "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359", 6), ("USDC.e", "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174", 6),
                ("WETH", "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619", 18)],
    "optimism": [("USDC", "0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85", 6), ("WETH", "0x4200000000000000000000000000000000000006", 18),
                 ("OP", "0x4200000000000000000000000000000000000042", 18)],
}
IMPL_SLOT = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"   # EIP-1967 implementation
BEACON_SLOT = "0xa3f0ad74e5423aebfd80d3ef4346578335a9a72aeaee59ff6cb3582b35133d50"  # EIP-1967 beacon
NATIVE_SYM = {"ethereum": "ETH", "bsc": "BNB", "arbitrum": "ETH", "base": "ETH", "polygon": "POL", "optimism": "ETH"}

def rpc(chain, method, params, timeout=15):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    last = None
    for _ in range(len(RPC[chain])):
        i = RPC_IDX.get(chain, 0)
        url = RPC[chain][i % len(RPC[chain])]
        req = urllib.request.Request(url, data=body, headers={
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) tvl-scanner/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                d = json.load(r)
            if "error" in d:
                raise RuntimeError(d["error"])
            return d["result"]
        except Exception as e:
            last = e
            RPC_IDX[chain] = i + 1  # fail over to next endpoint
            time.sleep(0.2)
    raise last

def hexint(h):
    return int(h, 16) if h and h != "0x" else 0

def eth_call(chain, to, data):
    try:
        return rpc(chain, "eth_call", [{"to": to, "data": data}, "latest"])
    except Exception:
        return "0x"

def addr_from_slot(h):
    a = hexint(h)
    return None if a == 0 else "0x" + h[-40:]

def main():
    key = None
    for line in open(".env"):
        if line.startswith("ETHERSCAN_API_KEY") and "=" in line:
            key = line.split("=", 1)[1].strip()

    unverified = []
    for f in ("artifacts/bugscan_results.json", "artifacts/bugscan_results_llama.json"):
        for r in json.load(open(f)):
            if r.get("status") == "unverified":
                unverified.append(r)
    seen, targets = set(), []
    for r in unverified:
        k = (r["chain"], r["address"].lower())
        if k not in seen:
            seen.add(k)
            targets.append(r)
    print(f"tier0: checking {len(targets)} unverified contracts\n")

    def check(r):
        ch, addr = r["chain"], r["address"].lower()
        out = dict(r, native_symbol=NATIVE_SYM[ch])
        try:
            code = rpc(ch, "eth_getCode", [addr, "latest"])
        except Exception as e:
            return dict(out, classification=f"rpc-error: {str(e)[:50]}", holdings_usd=0)
        out["code_size"] = (len(code) - 2) // 2
        if out["code_size"] == 0:
            return dict(out, classification="not-a-contract", holdings_usd=0)

        # holdings
        native = hexint(rpc(ch, "eth_getBalance", [addr, "latest"])) / 1e18
        out["native_balance"] = native
        tokens = []
        for sym, taddr, dec in TOKENS[ch]:
            raw = hexint(eth_call(ch, taddr, "0x70a08231" + addr.rjust(64, "0").replace("0x", "", 1)))  # balanceOf
            if raw:
                tokens.append({"symbol": sym, "amount": raw / 10**dec})
        out["tokens"] = tokens

        # proxy analysis
        impl = addr_from_slot(rpc(ch, "eth_getStorageAt", [addr, IMPL_SLOT, "latest"]))
        beacon = addr_from_slot(rpc(ch, "eth_getStorageAt", [addr, BEACON_SLOT, "latest"]))
        minimal = code.lower().startswith("0x363d3d373d3d3d363d73")
        if minimal and impl is None:
            impl = "0x" + code[22:62]  # EIP-1167: impl embedded in bytecode
        out["proxy_impl"], out["beacon"], out["minimal_proxy"] = impl, beacon, minimal

        # inline verification check (reuse bugscan's chain map)
        import importlib.util
        if "m" not in globals():
            spec = importlib.util.spec_from_file_location("bugscan", "scripts/bugscan.py")
            m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        chain_id = m.CHAIN_IDS[ch]

        def etherscan_verified(a):
            url = f"https://api.etherscan.io/v2/api?chainid={chain_id}&module=contract&action=getsourcecode&address={a}&apikey={key}"
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "tvl-scanner"}), timeout=20) as r:
                    d = json.load(r)
                if d.get("status") == "1" and isinstance(d.get("result"), list):
                    it = d["result"][0]
                    return {"verified": bool((it.get("SourceCode") or "").strip()),
                            "name": it.get("ContractName"), "impl": it.get("Implementation") or None}
            except Exception:
                pass
            return {"verified": None, "name": None, "impl": None}

        if impl:
            v = etherscan_verified(impl)
            out["impl_info"] = v
            out["classification"] = "proxy-unverified-impl" if not v["verified"] else "proxy-verified-impl"
        elif beacon:
            out["classification"] = "beacon-proxy-unresolved"
        else:
            out["classification"] = "standalone-unverified"
        time.sleep(0.25)
        return out

    with ThreadPoolExecutor(max_workers=6) as ex:
        results = list(ex.map(check, targets))

    # value holdings with llama prices (batch)
    ids = []
    for r in results:
        if r.get("native_balance"):
            ids.append(f"coingecko:{'binancecoin' if r['chain']=='bsc' else 'matic-network' if r['chain']=='polygon' else 'ethereum'}")
        for t in r.get("tokens", []):
            ids.append(f"{r['chain']}:{[x for x in TOKENS[r['chain']] if x[0]==t['symbol']][0][1].lower()}")
    prices = {}
    if ids:
        try:
            with urllib.request.urlopen("https://coins.llama.fi/prices/current/" + ",".join(dict.fromkeys(ids)), timeout=20) as r:
                prices = json.load(r)["coins"]
        except Exception as e:
            print("price fetch failed:", e)
    for r in results:
        usd = 0.0
        if r.get("native_balance"):
            pid = "coingecko:" + ("binancecoin" if r["chain"] == "bsc" else "matic-network" if r["chain"] == "polygon" else "ethereum")
            usd += r["native_balance"] * prices.get(pid, {}).get("price", 0)
        for t in r.get("tokens", []):
            taddr = [x for x in TOKENS[r["chain"]] if x[0] == t["symbol"]][0][1].lower()
            usd += t["amount"] * prices.get(f"{r['chain']}:{taddr}", {}).get("price", 0)
        r["holdings_usd"] = round(usd, 2)
        if r.get("classification") in ("not-a-contract",) or (r.get("code_size", 0) == 0):
            pass
        elif usd < 1 and r.get("native_balance", 0) < 0.001 and not r.get("tokens"):
            r["classification"] = "empty"

    results.sort(key=lambda r: -(r.get("holdings_usd") or 0))
    json.dump(results, open("artifacts/tier0_results.json", "w"), indent=1)

    print(f"{'USD holdings':>13}  {'classification':26} {'chain':9} {'address'}  protocol")
    for r in results:
        print(f"{r.get('holdings_usd', 0):13,.0f}  {r.get('classification', '?'):26} {r['chain']:9} {r['address']}  {r.get('protocol_guess', '?')}")

    keep = [r for r in results if r.get("classification") in ("proxy-unverified-impl", "standalone-unverified") and r.get("holdings_usd", 0) > 0]
    print(f"\nSURVIVORS (unauditable code + funded): {len(keep)}")
    for r in keep:
        ii = r.get("impl_info") or {}
        print(f"  {r['chain']:9} {r['address']}  ${r['holdings_usd']:,.0f}  {r.get('protocol_guess')}  impl={ii.get('name')}")

if __name__ == "__main__":
    main()
