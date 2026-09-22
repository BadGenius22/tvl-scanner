#!/usr/bin/env python3
"""oracle_verifier_check — Bonzo-class degenerate-input hunt (#sprint b).

For the top BLS-precompile-calling contracts (artifacts/oracle_hunt/bls_callers.json):
fetch verified source from Etherscan, then ask TypeSafe two independent Noul
questions — (1) does the verifier accept degenerate/identity BLS elements or skip
subgroup-membership checks, (2) is the failure mode reachable by an unprivileged
caller. Policy in code: review when q1 >= 0.5 (any doubt on degenerate handling
goes to a human — this class produced $9.05M on Bonzo).

Run: python3 scripts/oracle_verifier_check.py [--top 10]
"""
import argparse
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
import typesafe_client as ts

KEY = None
for line in open(".env"):
    if line.startswith("ETHERSCAN_API_KEY") and "=" in line:
        KEY = line.split("=", 1)[1].strip()

QUESTIONS = {
    "degenerate_input_risk": {
        "type": "noul",
        "instructions": "Does this signature-verifier code accept degenerate cryptographic inputs — identity/zero points, elements not proven to be in the correct subgroup, or missing canonical-encoding checks — in the signature or public-key path before verification?",
        "criteria": {
            "true": "inputs are passed to pairing/verification without subgroup-membership, non-identity, or canonical-form validation",
            "false": "subgroup checks, identity rejection, or canonical validation are present before verification"
        }
    },
    "unprivileged_reachable": {
        "type": "noul",
        "instructions": "Is the verification path reachable by an unprivileged external caller (anyone can trigger verification that gates value, pricing, or registration)?",
        "criteria": {
            "true": "anyone can call the verify/submit path and influence outcome",
            "false": "only trusted operators can trigger it, or it gates nothing"
        }
    },
}
REVIEW_FLOOR = 0.50  # any doubt on degenerate handling -> human


def etherscan_source(addr):
    url = f"https://api.etherscan.io/v2/api?chainid=1&module=contract&action=getsourcecode&address={addr}&apikey={KEY}"
    for i in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "tvl-scanner"}), timeout=25) as r:
                d = json.load(r)
            if d.get("status") == "1" and isinstance(d.get("result"), list):
                it = d["result"][0]
                return bool((it.get("SourceCode") or "").strip()), (it.get("SourceCode") or "")[:4000], it.get("ContractName")
            return False, "", None
        except Exception:
            time.sleep(1.5 * (i + 1))
    return False, "", None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=10)
    args = ap.parse_args()
    callers = json.load(open("artifacts/oracle_hunt/bls_callers.json"))[: args.top]
    out_path = "artifacts/oracle_hunt/verifier_check.jsonl"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    done = set()
    if os.path.exists(out_path):
        for line in open(out_path):
            try:
                done.add(json.loads(line)["caller"])
            except Exception:
                pass
    outf = open(out_path, "a")
    flagged = 0
    for c in callers:
        addr = c["caller"].lower()
        if addr in done:
            continue
        verified, src, name = etherscan_source(addr)
        if not verified:
            print(f"  {addr}  unverified/no-source — flagging for manual look", flush=True)
            outf.write(json.dumps({"caller": addr, "calls": c["calls"], "verified": False,
                                   "verdict": "needs_manual"}, default=str) + "\n")
            continue
        try:
            a = ts.ask({"contract_name": name, "calls_to_bls_precompiles": c["calls"],
                        "source_head": src}, QUESTIONS)
        except Exception as e:
            print(f"  API error: {str(e)[:100]} — stopping (rerun resumes)", flush=True)
            break
        q1 = a.get("degenerate_input_risk", {}).get("noul", 0) or 0
        q2 = a.get("unprivileged_reachable", {}).get("noul", 0) or 0
        verdict = "review" if q1 >= REVIEW_FLOOR else "clean"
        flagged += verdict == "review"
        rec = {"caller": addr, "name": name, "calls": c["calls"], "answers": a,
               "degenerate_p": q1, "reachable_p": q2, "verdict": verdict}
        outf.write(json.dumps(rec, default=str) + "\n")
        mark = "REVIEW" if verdict == "review" else "clean "
        print(f"  [{mark}] {addr} ({name}) degenerate_p={q1:.2f} reachable_p={q2:.2f} calls={c['calls']}", flush=True)
        time.sleep(0.3)
    outf.close()
    ts._cache_save()
    print(f"flagged {flagged} -> {out_path}")


if __name__ == "__main__":
    main()
