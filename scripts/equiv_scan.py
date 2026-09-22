#!/usr/bin/env python3
"""equiv_scan — running-counter equivalence signature (the Lien exchangeEquivalentBonds class).

Scans verified sources for the aggregate-counter equivalence shape:
  R1: require(<array>.length == <x>Count)      — length compared to a counter
  R2: <x>Count = <x>Count.add(1) / ++          — counter incremented
  R3: <x>Count = <x>Count.sub(1) / --          — counter decremented
A hit requires R1 and (R2 or R3) sharing the same counter identifier in one file.
Also collects keyword context hits for the tranche/bond architecture family.

Corpus: every flagged contract from the bugscan artifacts (sources re-fetched
from Etherscan V2 and cached under artifacts/equiv_corpus/).

Run: python3 scripts/equiv_scan.py
"""
import json
import os
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

KEY = None
for line in open(".env"):
    if line.startswith("ETHERSCAN_API_KEY") and "=" in line:
        KEY = line.split("=", 1)[1].strip()

CHAIN_IDS = {"ethereum": 1, "bsc": 56, "arbitrum": 42161, "base": 8453, "polygon": 137, "optimism": 10}
CACHE = "artifacts/equiv_corpus"
os.makedirs(CACHE, exist_ok=True)

# ---- signature ----
R1 = re.compile(r"require\s*\(\s*(\w+)\.length\s*==\s*(\w*[cC]ount\w*)\s*[,)]")
R2 = re.compile(r"(\w*[cC]ount\w*)\s*=\s*\1\s*\.\s*add\s*\(\s*1\s*\)|(\w*[cC]ount\w*)\+\+")
R3 = re.compile(r"(\w*[cC]ount\w*)\s*=\s*\1\s*\.\s*sub\s*\(\s*1\s*\)|--\s*(\w*[cC]ount\w*)")

# ---- architecture-family context keywords ----
FAMILY = re.compile(
    r"exchangeEquivalent|bondGroup|fnMap|registerNewBond|BondPricer|"
    r"tranche|Tranche|principalToken|yieldToken|splitAmount|mergeAmount",
)


def fetch(chain, addr):
    cache_file = os.path.join(CACHE, f"{chain}_{addr.lower()}.sol")
    if os.path.exists(cache_file):
        return cache_file
    cid = CHAIN_IDS[chain]
    url = (f"https://api.etherscan.io/v2/api?chainid={cid}&module=contract"
           f"&action=getsourcecode&address={addr}&apikey={KEY}")
    for i in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "tvl-scanner"}), timeout=30) as r:
                d = json.load(r)
            if d.get("status") == "1" and isinstance(d.get("result"), list):
                src = d["result"][0].get("SourceCode") or ""
                with open(cache_file, "w", encoding="utf-8") as f:
                    f.write(src)
                if not src.strip():
                    return None  # unverified — don't keep empty caches
                return cache_file
            return None
        except Exception:
            time.sleep(1.2 * (i + 1))
    return None


def scan(path):
    text = open(path, encoding="utf-8", errors="ignore").read()
    hits = []
    m1 = [(m.group(1), m.group(2)) for m in R1.finditer(text)]
    if m1:
        incs = set(m.group(1) or m.group(2) for m in R2.finditer(text))
        decs = set(m.group(1) or m.group(2) for m in R3.finditer(text))
        for arr, cnt in m1:
            if cnt in incs or cnt in decs:
                hits.append({"shape": "length==counter + +/-1", "array": arr, "counter": cnt,
                             "inc": cnt in incs, "dec": cnt in decs})
    fam = sorted(set(m.group(0) for m in FAMILY.finditer(text)))
    return hits, fam


def main():
    targets = []
    for f in ("artifacts/bugscan_results.json", "artifacts/bugscan_results_llama.json"):
        for c in json.load(open(f)):
            if c.get("findings"):
                targets.append((c["chain"], c["address"].lower(), c.get("name") or c.get("protocol_guess") or "?"))
    seen, uniq = set(), []
    for t in targets:
        if t[:2] not in seen:
            seen.add(t[:2])
            uniq.append(t)
    print(f"corpus: {len(uniq)} flagged contracts")

    with ThreadPoolExecutor(max_workers=4) as ex:
        paths = list(ex.map(lambda t: fetch(t[0], t[1]), uniq))
    fetched = [(t, p) for t, p in zip(uniq, paths) if p]
    print(f"sources fetched: {len(fetched)}")

    sig_hits, fam_hits = [], []
    for (chain, addr, name), path in fetched:
        hits, fam = scan(path)
        for h in hits:
            sig_hits.append({"chain": chain, "address": addr, "name": name, **h})
        if fam:
            fam_hits.append({"chain": chain, "address": addr, "name": name, "keywords": fam})

    print(f"\n=== signature hits: {len(sig_hits)} ===")
    for h in sig_hits:
        print(json.dumps(h))
    print(f"\n=== architecture-family keyword hits: {len(fam_hits)} ===")
    for h in fam_hits:
        print(f"{h['chain']:9} {h['address']}  {h['name'][:28]:28} {','.join(h['keywords'][:6])}")

    json.dump({"signature_hits": sig_hits, "family_hits": fam_hits},
              open("artifacts/equiv_scan_results.json", "w"), indent=1)
    print("\nsaved artifacts/equiv_scan_results.json")


if __name__ == "__main__":
    main()
