#!/usr/bin/env python3
"""lien_probe — one-off investigation helper for the Lien Finance suite.

Fetches verified source for the Lien contracts named in the 2026-07-24 exploit
write-ups, snapshots on-chain holdings (native + blue chips + USDC-class), and
walks the exploit tx receipt to enumerate every contract that emitted or
received in the attack. Sources land in artifacts/lien/.

Run: python3 scripts/lien_probe.py
"""
import importlib.util
import json
import os
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

spec = importlib.util.spec_from_file_location("tier0", os.path.join("scripts", "tier0_check.py"))
tier0 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tier0)
rpc, hexint, eth_call = tier0.rpc, tier0.hexint, tier0.eth_call

# prefer a paid endpoint when configured (ALCHEMY_API_KEY in .env)
ALCHEMY = None
for line in open(".env"):
    if line.startswith("ALCHEMY_API_KEY") and "=" in line:
        ALCHEMY = line.split("=", 1)[1].strip()
if ALCHEMY:
    tier0.RPC["ethereum"].insert(0, f"https://eth-mainnet.g.alchemy.com/v2/{ALCHEMY}")

OUT = "artifacts/lien"
os.makedirs(OUT, exist_ok=True)

KEY = None
for line in open(".env"):
    if line.startswith("ETHERSCAN_API_KEY") and "=" in line:
        KEY = line.split("=", 1)[1].strip()

TARGETS = [
    # (label, address) — from VeriChains write-up + bugscan llama pool
    ("BondMakerCollateralizedEth", "0xDA6FC5625E617bB92F5359921D43321cEbC6BEf0"),  # exploited
    ("BondMaker", "0x843225CF6e663e4454732D6B551A737Ac7b47de0"),                    # cited source
    ("GeneralizedDotc", "0x656e5e976d523a427f05B0c212A22A89ccD9eF18"),              # OTC pool drained
    ("LienToken", "0xab37e1358b639fd877f015027bb62d3ddaa7557e"),                    # llama-flagged
]
EXPLOIT_TX = "0xb96d572b557a12f5ef193e88cca86123a6ae1b6e98b0eeee265870c85848e0e7"
ATTACKER = "0x0D7d9023531aD1A88414E216Ee2715F63561808a"
ORCH = "0xe74d17c1bE3721E65e0af286D47B3BA58B08062e"


def etherscan(module, action, **params):
    q = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"https://api.etherscan.io/v2/api?chainid=1&module={module}&action={action}&{q}&apikey={KEY}"
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "tvl-scanner"}), timeout=25) as r:
                return json.load(r)
        except Exception as e:
            if attempt == 2:
                raise
            time.sleep(1.5)


def fetch_source(addr):
    d = etherscan("contract", "getsourcecode", address=addr)
    if d.get("status") != "1" or not isinstance(d.get("result"), list):
        return {"verified": False, "name": None, "items": []}
    items = []
    for it in d["result"]:
        items.append({
            "name": it.get("ContractName"),
            "source": it.get("SourceCode") or "",
            "compiler": it.get("CompilerVersion"),
            "impl": it.get("Implementation") or None,
            "proxy": it.get("Proxy") == "1",
            "abi_present": bool(it.get("ABI") and it["ABI"] != "Contract source code not verified"),
        })
    return {"verified": bool(items and items[0]["source"].strip()), "items": items, "name": items[0]["name"] if items else None}


def rpc_retry(chain, method, params, tries=5):
    last = None
    for i in range(tries):
        try:
            return rpc(chain, method, params)
        except Exception as e:
            last = e
            time.sleep(0.8 * (i + 1))
    raise last


def snapshot(addr):
    addr = addr.lower()
    out = {"code_size": 0, "native_eth": 0.0, "tokens": {}}
    code = rpc_retry("ethereum", "eth_getCode", [addr, "latest"])
    out["code_size"] = (len(code) - 2) // 2
    if out["code_size"] == 0:
        return out
    out["native_eth"] = hexint(rpc_retry("ethereum", "eth_getBalance", [addr, "latest"])) / 1e18
    for sym, taddr, dec in tier0.TOKENS["ethereum"]:
        raw = hexint(eth_call("ethereum", taddr, "0x70a08231" + addr.rjust(64, "0")))
        if raw:
            out["tokens"][sym] = raw / 10**dec
    return out


def decode_logs(receipt):
    """Pull (address, topic0) pairs + transfer-like flows from the exploit receipt."""
    flows, emitters = [], {}
    for lg in receipt.get("logs", []):
        a = "0x" + lg["address"].lower()[-40:]
        emitters[a] = emitters.get(a, 0) + 1
        t0 = lg["topics"][0] if lg["topics"] else ""
        if t0 == "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef" and len(lg["topics"]) >= 3:
            src = "0x" + lg["topics"][1][-40:]
            dst = "0x" + lg["topics"][2][-40:]
            data = lg["data"][2:]
            val = int(data, 16) if data else 0
            flows.append({"token": a, "from": src, "to": dst, "raw": val})
    return emitters, flows


def main():
    # 1) source + holdings for the named suite
    suite = {}
    def work(item):
        label, addr = item
        src = fetch_source(addr)
        snap = snapshot(addr)
        d = os.path.join(OUT, f"{label}_{addr[:10]}")
        os.makedirs(d, exist_ok=True)
        for i, it in enumerate(src["items"]):
            fn = os.path.join(d, f"{i}_{it['name']}.sol")
            with open(fn, "w", encoding="utf-8") as f:
                f.write(it["source"])
        return label, {"address": addr, "name": src.get("name"), "verified": src["verified"],
                       "snapshot": snap, "dir": d}

    with ThreadPoolExecutor(max_workers=4) as ex:
        for label, info in ex.map(work, TARGETS):
            suite[label] = info
            s = info["snapshot"]
            toks = ", ".join(f"{k}={v:,.2f}" for k, v in s["tokens"].items()) or "-"
            print(f"{label:30} {info['address']}  verified={info['verified']}  "
                  f"code={s['code_size']:>6}B  ETH={s['native_eth']:.4f}  [{toks}]")

    # 2) exploit tx walk
    rcpt = rpc_retry("ethereum", "eth_getTransactionReceipt", [EXPLOIT_TX])
    if rcpt:
        emitters, flows = decode_logs(rcpt)
        print(f"\nexploit tx status={int(rcpt['status'],16)} gasUsed={int(rcpt['gasUsed'],16)} "
              f"logs={len(rcpt.get('logs', []))} block={int(rcpt['blockNumber'],16)}")
        print("emitters:", json.dumps(emitters, indent=0))
        # USDC transfers in the tx
        usdc = tier0.TOKENS["ethereum"][0][1].lower()
        for f in flows:
            if f["token"] == usdc:
                print(f"USDC {f['from']} -> {f['to']}  {f['raw']/1e6:,.2f}")
        json.dump({"emitters": emitters, "flows": flows},
                  open(os.path.join(OUT, "exploit_tx_flows.json"), "w"), indent=1)

    # 3) holdings snapshot of attacker/orchestrator (did funds move on?)
    for label, a in (("attacker", ATTACKER), ("orchestrator", ORCH)):
        s = snapshot(a)
        toks = ", ".join(f"{k}={v:,.2f}" for k, v in s["tokens"].items()) or "-"
        print(f"{label:30} {a}  ETH={s['native_eth']:.4f}  [{toks}]")

    # 4) address cross-reference from fetched sources
    refs = {}
    for label, info in suite.items():
        for fn in os.listdir(info["dir"]):
            text = open(os.path.join(info["dir"], fn), encoding="utf-8", errors="ignore").read()
            for m in re.findall(r"0x[a-fA-F0-9]{40}", text):
                a = m.lower()
                if a not in refs:
                    refs[a] = set()
                refs[a].add(label)
    json.dump({a: sorted(v) for a, v in sorted(refs.items())},
              open(os.path.join(OUT, "address_refs.json"), "w"), indent=1)
    print(f"\nunique address constants in sources: {len(refs)} (artifacts/lien/address_refs.json)")

    json.dump(suite, open(os.path.join(OUT, "suite_snapshot.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
