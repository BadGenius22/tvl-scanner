#!/usr/bin/env python3
"""hunt_campaign — the main hunt loop: funded live protocols → deployer walk → funded cores.

Selection: DefiLlama protocols with $10M–$300M TVL on EVM majors, category-
diversified (under-audited mid-band bias: sorted by TVL ascending, one per
category round-robin). Each candidate runs the full protocol_family_scan sweep
(anchor → creators → deployment walk across 6 chains → funding snapshot).

Output: artifacts/hunt_campaign/<slug>.json + a campaign summary of FUNDED
survivors — those become the bugscan/semantic-scan targets.

Run: python3 scripts/hunt_campaign.py --count 12 [--band 10 300]
"""
import argparse
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import protocol_family_scan as pfs

EXCLUDE_CATEGORIES = {
    "Chain", "CEX", "Stablecoin Issuer", "Infrastructure", "Wallet",
    "DataType", "NFT Marketplace", "Non-Fungible-Tokens", "Governance",
    "Messenger", "Privacy", "Computing", "DEX", "RWA Lending",
}
EXCLUDE_SLUGS = {"yield-protocol", "lien", "yo", "saffron-finance", "barnbridge",
                 "element-fi", "swivel-finance", "sense"}
EVM_CHAINS = {"Ethereum", "Arbitrum", "Base", "BSC", "Optimism", "Polygon"}


def llama_protocols():
    url = "https://api.llama.fi/protocols"
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "tvl-scanner"}), timeout=120) as r:
        return json.load(r)


def select(candidates, count):
    """Round-robin one per category over TVL-ascending candidates."""
    picked, used_cats = [], {}
    remaining = list(candidates)
    while remaining and len(picked) < count:
        # pick the lowest-TVL candidate whose category has been picked the
        # fewest times so far
        best, best_key = None, None
        for c in remaining:
            cat = c.get("category") or "Other"
            key = (used_cats.get(cat, 0), c["tvl"])
            if best_key is None or key < best_key:
                best, best_key = c, key
        if best is None:
            break
        cat = best.get("category") or "Other"
        used_cats[cat] = used_cats.get(cat, 0) + 1
        picked.append(best)
        remaining.remove(best)
    return picked


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=12)
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--min-tvl", type=float, default=10e6)
    ap.add_argument("--max-tvl", type=float, default=300e6)
    args = ap.parse_args()

    print("fetching llama protocol list…", flush=True)
    protos = llama_protocols()
    print(f"total protocols: {len(protos)}", flush=True)

    cands = []
    for p in protos:
        tvl = p.get("tvl") or 0
        cat = p.get("category")
        chains = set(p.get("chains") or [])
        slug = p.get("slug") or ""
        addr = p.get("address")
        if not (args.min_tvl <= tvl <= args.max_tvl):
            continue
        if cat in EXCLUDE_CATEGORIES or slug in EXCLUDE_SLUGS:
            continue
        if not chains & EVM_CHAINS:
            continue
        if not addr or not str(addr).startswith("0x"):
            continue
        cands.append({"slug": slug, "tvl": tvl, "category": cat or "Other",
                      "anchor": str(addr), "chains": sorted(chains & EVM_CHAINS)})

    cands.sort(key=lambda c: c["tvl"])
    print(f"candidates in band with anchors: {len(cands)}", flush=True)
    picked = select(cands, args.count + args.offset)[args.offset:args.offset + args.count]
    print(f"selected {len(picked)} (category-diversified, TVL-ascending):", flush=True)
    for c in picked:
        print(f"  {c['slug']:28} {c['category'] or '?':22} tvl=${c['tvl']/1e6:8.1f}M  chains={','.join(c['chains'])}", flush=True)
    os.makedirs("artifacts/hunt_campaign", exist_ok=True)
    json.dump(picked, open("artifacts/hunt_campaign/selection.json", "w"), indent=1)

    os.makedirs("artifacts/hunt_campaign", exist_ok=True)
    campaign = []
    for i, c in enumerate(picked):
        print(f"\n=== [{i+1}/{len(picked)}] {c['slug']} (tvl ${c['tvl']/1e6:.1f}M) ===", flush=True)
        try:
            funded = pfs.sweep(c["slug"], [c["anchor"]])
        except Exception as e:
            print(f"  sweep failed: {str(e)[:120]}", flush=True)
            funded = []
        tot_eth = sum(x.get("eth", 0) for x in funded)
        campaign.append({"slug": c["slug"], "tvl_llama": c["tvl"], "walked_funded": funded,
                         "funded_eth_total": tot_eth})
        print(f"  => {c['slug']}: funded survivors {len(funded)} (ETH {tot_eth:.4f})", flush=True)
        json.dump(campaign, open("artifacts/hunt_campaign/campaign_summary.json", "w"), indent=1, default=str)

    print("\n=== CAMPAIGN SUMMARY ===", flush=True)
    for c in campaign:
        print(f"  {c['slug']:28} llama=${c['tvl_llama']/1e6:8.1f}M  funded={len(c['walked_funded']):3}  ETH={c['funded_eth_total']:.4f}", flush=True)


if __name__ == "__main__":
    main()
