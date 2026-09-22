#!/usr/bin/env python3
"""bugscan — triage scanner for the bug families observed in DeFiHackLabs Jun–Aug 2026.

Fetches verified source for candidate contracts via Etherscan V2 (one key, all EVM
chains) and flags code patterns matching the incident root causes analyzed in
research/defihack-2026Q3:

  A1 spot-oracle-read   protocol values assets from AMM spot reserves / slot0 /
                        ERC-4626 convertToAssets (edel-xstock, LpdFi, Arrakis, Float)
  A2 fot-token          fee-on-transfer / mutable-decimals / burn-from-pair token
                        mechanics that corrupt pair reserves (OLPC, DIP, AIDC, RWT)
  A2 pair-write         non-pair contract pulls tokens from a live pair then sync()
                        (LULA recycle(); skim/sync upkeep)
  B2 unchecked-cast     int128 cast without bound check (Drips sign flip)
  B2 zero-amount-edge   batch loops crediting per-item state without amount check
                        (RoyalRoyalties zero-amount tier inflation)
  B3 ecrecover-unchecked ecrecover result never compared to address(0) (Lixir)
  B4 arbitrary-call     target.call(data) / user-supplied calldata forwarding
                        (SandboxOFT, Unistreet, UnprotectedArbBot)
  B4 proxy-write        delegatecall to caller-supplied address (Nereus)

This is regex-level triage, not a compiler-aware analysis: every flag needs manual
review. Run:  python3 scripts/bugscan.py [--artifacts artifacts] [--out artifacts/bugscan_results.json]
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.request

CHAIN_IDS = {
    "ethereum": 1, "eth": 1,
    "bsc": 56, "bnb": 56,
    "arbitrum": 42161,
    "base": 8453,
    "polygon": 137,
    "optimism": 10,
}
API = "https://api.etherscan.io/v2/api?chainid={chain}&module=contract&action=getsourcecode&address={addr}&apikey={key}"

# (family, weight, regex, family description used in the report)
PATTERNS = [
    ("spot-oracle-read", 30, re.compile(r"getReserves\s*\(|\.slot0\s*\(|sqrtPriceX96|convertToAssets\s*\("),
     "values assets from manipulable spot state (AMM reserves / V3 slot0 / ERC-4626 rate)"),
    ("share-nav-read", 20, re.compile(r"totalAssets\s*\(|pricePerShare|pricePerFullShare|getVirtualPrice|nav\s*\(", re.I),
     "share price / NAV derived from live accounting — donation-inflatable if unguarded"),
    ("pair-write", 25, re.compile(r"\.sync\s*\(\s*\)|\.skim\s*\(\s*\w|balanceOf\s*\(\s*\w*[Pp]air"),
     "reads/writes a live AMM pair's reserves from protocol logic (LULA recycle / skim-sync upkeep)"),
    ("fot-mechanics", 15, re.compile(r"_takeFee|takeFee|taxFee|liquidityFee|marketingFee|isExcludedFromFee|burnFrom\s*\(\s*pair|_burn\s*\(\s*\w*[Pp]air"),
     "fee-on-transfer style mechanics; burns/taxes charged to pools corrupt reserves"),
    ("mutable-decimals", 25, re.compile(r"setDecimals\s*\(|decimalsValue|updateDecimals|_setupDecimals\s*\("),
     "decimals settable at runtime — used in amount math in the OLPC incident"),
    ("ecrecover-unchecked", 30, re.compile(r"ecrecover\s*\("),
     "ecrecover signature path — verify the recovered address is checked against address(0) (Lixir dummy-signature drain)"),
    ("unchecked-cast", 20, re.compile(r"int128\s*\(\s*[A-Za-z_]|int256\s*\(\s*-?\s*uint|uint256\s*\(\s*int128"),
     "signed/unsigned cast — Drips-style sign flip if bounds are unchecked"),
    ("arbitrary-call", 30, re.compile(r"approveAndCall|\.\s*call\s*\{\s*value[^}]*\}\s*\(\s*(data|payload|_data|callData)|\.call\s*\(\s*(data|payload|_data|callData|abi\.encodeWith(Selector|Signature))"),
     "forwards caller-supplied calldata to an arbitrary target (SandboxOFT / Unistreet / unprotected forwarder)"),
    ("delegatecall-param", 25, re.compile(r"delegatecall\s*\(\s*[A-Za-z_]*\s*(data|target|impl|implementation|logic|to)\b|delegatecall\s*\(\s*abi\."),
     "delegatecall whose target may be caller-supplied — proxy upgrade abuse (Nereus)"),
    ("zero-amount-batch", 15, re.compile(r"batchTransfer|transferBatch|safeBatchTransferFrom|for\s*\(.*amounts\["),
     "batch loops crediting per-item accounting — check amounts[i] == 0 handling (RoyalRoyalties)"),
    ("balance-delta-accounting", 15, re.compile(r"balanceOf\(address\(this\)\)\s*-|before\s*=.*balanceOf|balanceDiff|_pairBalance"),
     "state credited from raw balance deltas — donations move accounting"),
]

def load_env_key():
    for line in open(".env"):
        line = line.strip()
        if line.startswith("ETHERSCAN_API_KEY") and "=" in line:
            return line.split("=", 1)[1].strip()
    sys.exit("ETHERSCAN_API_KEY not found in .env")

def fetch_source(chain_id, addr, key, timeout=20):
    url = API.format(chain=chain_id, addr=addr, key=key)
    req = urllib.request.Request(url, headers={"User-Agent": "tvl-scanner-bugscan"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.load(r)
    if d.get("status") != "1" or not isinstance(d.get("result"), list):
        return None
    return d["result"][0]

def parse_source_files(item):
    """Return {filename: source} from Etherscan SourceCode (single, JSON multi, or concatenated)."""
    raw = item.get("SourceCode") or ""
    if not raw.strip():
        return {"<source>": ""}
    s = raw.strip()
    if s.startswith("{{") and s.endswith("}}"):
        try:
            j = json.loads(s[1:-1])
            files = j.get("sources", j)
            return {k: v.get("content", "") if isinstance(v, dict) else str(v) for k, v in files.items()}
        except json.JSONDecodeError:
            pass
    if s.startswith("{") and s.endswith("}"):
        try:
            j = json.loads(s)
            files = j.get("sources", j)
            return {k: v.get("content", "") if isinstance(v, dict) else str(v) for k, v in files.items()}
        except json.JSONDecodeError:
            pass
    return {"<source>": raw}

def scan_text(text, fname="<source>"):
    hits = []
    lines = text.splitlines()
    for line_no, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith(("//", "*", "/*")):
            continue  # comments: doc text mentions patterns without implementing them
        if re.search(r"external\s+(pure|view)?\s*(public)?\s*(virtual\s+)?returns\s*;", line) or \
           re.search(r"function\s+\w+\s*\([^)]*\)\s+(external|public|internal)\s*(pure\s+|view\s+)?(virtual\s+)?returns?", line):
            continue  # interface/function declarations
        for family, weight, rx, _desc in PATTERNS:
            m = rx.search(line)
            if m:
                # ecrecover: only flag when no address(0) guard within +-6 lines
                if family == "ecrecover-unchecked":
                    window = "\n".join(lines[max(0, line_no - 7):line_no + 5])
                    if re.search(r"!=\s*address\s*\(\s*0\s*\)|==\s*address\s*\(\s*0\s*\)|require\s*\(\s*\w+\s*!=\s*address\s*\(\s*0", window):
                        continue
                ctx = lines[max(0, line_no - 2):line_no + 1]
                hits.append({
                    "family": family, "line": line_no, "match": m.group(0)[:60],
                    "context": "\n".join(x.strip() for x in ctx)[:300],
                    "boilerplate": ("@openzeppelin" in fname or "@uniswap" in fname
                                    or "@layerzerolabs" in fname
                                    or fname.rsplit("/", 1)[-1].startswith(("I", "Lib", "draft-"))
                                    or "mock" in fname.lower()),
                })
    # dedupe per family+line
    seen, out = set(), []
    for h in hits:
        k = (h["family"], h["line"])
        if k not in seen:
            seen.add(k)
            out.append(h)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifacts", default="artifacts")
    ap.add_argument("--targets", default="artifacts/candidates.json",
                    help="candidates JSON (chain/address/protocol_guess/tvl_usd)")
    ap.add_argument("--out", default="artifacts/bugscan_results.json")
    ap.add_argument("--limit", type=int, default=0, help="max contracts (0 = all)")
    ap.add_argument("--sleep", type=float, default=0.35, help="seconds between API calls")
    args = ap.parse_args()

    key = load_env_key()
    cands = json.load(open(args.targets))
    seen, targets = set(), []
    for c in cands:
        ch = (c.get("chain") or "").lower()
        if ch not in CHAIN_IDS:
            continue
        addr = (c.get("address") or "").lower()
        if not addr.startswith("0x") or (ch, addr) in seen:
            continue
        seen.add((ch, addr))
        targets.append(c)
        if args.limit and len(targets) >= args.limit:
            break

    print(f"scanning {len(targets)} EVM contracts "
          f"({len(cands) - len(targets)} skipped: non-EVM/dupe/no-address)")
    results = []
    for i, c in enumerate(targets, 1):
        ch, addr = c["chain"].lower(), c["address"].lower()
        try:
            item = fetch_source(CHAIN_IDS[ch], addr, key)
        except Exception as e:
            results.append({"chain": ch, "address": addr, "protocol_guess": c.get("protocol_guess"),
                            "tvl_usd": c.get("tvl_usd"), "status": f"api-error: {e}", "findings": []})
            continue
        if item is None:
            results.append({"chain": ch, "address": addr, "protocol_guess": c.get("protocol_guess"),
                            "tvl_usd": c.get("tvl_usd"), "status": "not-found", "findings": []})
            continue
        files = parse_source_files(item)
        if not any(files.values()):
            results.append({"chain": ch, "address": addr, "protocol_guess": c.get("protocol_guess"),
                            "tvl_usd": c.get("tvl_usd"), "status": "unverified",
                            "name": item.get("ContractName"), "findings": []})
            continue
        findings = []
        for fname, src in files.items():
            for h in scan_text(src, fname):
                h["file"] = fname
                findings.append(h)
        results.append({"chain": ch, "address": addr, "protocol_guess": c.get("protocol_guess"),
                        "tvl_usd": c.get("tvl_usd"), "status": "ok",
                        "name": item.get("ContractName"), "proxy": item.get("Proxy") == "1",
                        "implementation": item.get("Implementation"),
                        "files": list(files), "findings": findings})
        fams = sorted({h["family"] for h in findings})
        print(f"  [{i}/{len(targets)}] {ch}:{addr[:10]} {item.get('ContractName')}: "
              f"{len(findings)} flags {fams if fams else ''}")
        time.sleep(args.sleep)

    json.dump(results, open(args.out, "w"), indent=1)
    flagged = sum(1 for r in results if r.get("findings"))
    unverified = sum(1 for r in results if r.get("status") == "unverified")
    print(f"\ndone: {len(results)} scanned, {flagged} flagged, {unverified} unverified -> {args.out}")

if __name__ == "__main__":
    main()
