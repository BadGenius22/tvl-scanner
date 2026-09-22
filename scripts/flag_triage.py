#!/usr/bin/env python3
"""flag_triage — TypeSafe triage of bugscan regex findings (#1).

For each (contract, finding): state = incident-family definition + the matched
line + surrounding context + contract metadata. Two independent questions in
one request: `mechanism_present` + `still_live` (Noul) and `triage` (Choice).
Policy is HERE, in
code — the model only judges:

  review     triage == real_finding @conf>=0.70, or mechanism_present >= 0.85
  dismiss    triage == boilerplate   and confidence >= 0.70
  needs_manual  everything else

Calibration: artifacts/flag_triage_labels.json carries ground truth from the
manual conclusions in reports/2026-09-16-bugscan.md. `--calibrate` runs only
labeled findings and reports agreement.

Run:
  python3 scripts/flag_triage.py --calibrate            # labeled subset only
  python3 scripts/flag_triage.py --limit 100            # unlabeled sweep, resumable
  python3 scripts/flag_triage.py --family ecrecover-unchecked
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import typesafe_client as ts

FAMILY_DESC = {
    "spot-oracle-read": "values assets from manipulable spot state (AMM getReserves/slot0, ERC-4626 convertToAssets)",
    "share-nav-read": "share price/NAV derived from live accounting, donation-inflatable if unguarded",
    "pair-write": "protocol logic reads/writes a live AMM pair's reserves (sync/skim upkeep)",
    "fot-mechanics": "fee-on-transfer style mechanics; taxes/burns charged to pools corrupt reserves",
    "mutable-decimals": "token decimals settable at runtime and used in amount math",
    "ecrecover-unchecked": "ecrecover signature path where the recovered signer is not checked against address(0) or a expected signer",
    "unchecked-cast": "signed/unsigned integer cast without a bound check (sign-flip class)",
    "arbitrary-call": "forwards caller-supplied target/calldata into a low-level call",
    "delegatecall-param": "delegatecall whose target may be caller-supplied",
    "zero-amount-batch": "batch loop crediting per-item accounting without checking amounts[i] == 0",
    "balance-delta-accounting": "accounting credited from raw balance deltas, donation-sensitive",
}

QUESTIONS = {
    "mechanism_present": {
        "type": "noul",
        "instructions": "Does this code excerpt implement the stated bug family's mechanism with attacker-controllable inputs, regardless of whether the contract is still active?",
        "criteria": {
            "true": "the mechanism exists here: attacker-chosen target/amount/signer, corruptible valuation, or missing bound check",
            "false": "syntactic match only: library/interface boilerplate, constructor-only setup, dead code, guarded path"
        }
    },
    "still_live": {
        "type": "noul",
        "instructions": "Is this contract plausibly still live and worth attention (verified source, non-trivial TVL, not a known-defunct protocol)?",
        "criteria": {
            "true": "verified source and/or non-trivial TVL suggests current use",
            "false": "defunct/historic protocol, zero TVL, unverified"
        }
    },
    "triage": {
        "type": "choice",
        "instructions": "Classify this scanner finding.",
        "criteria": {
            "real_finding": "matches the incident family with an attacker-controlled surface",
            "boilerplate": "regex-matched only syntactically: library internals, interface declarations, constructor-only setup, dead code, or expected by design (e.g. an AMM pool quoting spot)",
            "needs_manual": "cannot be decided from the given context"
        }
    },
}
MECHANISM_FLOOR = 0.70   # mechanism_present above this -> never auto-dismiss
REVIEW_CONF = 0.70


def flatten():
    out = []
    for path in ("artifacts/bugscan_results.json", "artifacts/bugscan_results_llama.json"):
        for c in json.load(open(path)):
            for f in c.get("findings") or []:
                out.append({
                    "chain": c["chain"], "address": c["address"], "name": c.get("name"),
                    "protocol": c.get("protocol_guess"), "tvl_usd": c.get("tvl_usd"),
                    "verified": c.get("status") == "ok", "proxy": c.get("proxy"),
                    "family": f.get("family"), "line": f.get("line"),
                    "match": f.get("match"), "context": f.get("context"),
                })
    return out


def state_for(item):
    return {
        "family": item["family"],
        "family_definition": FAMILY_DESC.get(item["family"], item["family"]),
        "matched_line": item["match"],
        "code_context": (item["context"] or "")[:900],
        "contract": {
            "name": item["name"], "chain": item["chain"],
            "approx_tvl_usd": item["tvl_usd"], "source_verified": item["verified"],
            "is_proxy": item["proxy"],
        },
    }


def policy(answer):
    tri = answer.get("triage", {})
    choice = tri.get("choice")
    conf = tri.get("confidence", 0) or 0
    mech = answer.get("mechanism_present", {}).get("noul", 0) or 0
    if choice == "real_finding" and conf >= REVIEW_CONF:
        return "review"
    if mech >= MECHANISM_FLOOR:
        # real mechanism: review if unambiguous or confirmed live, else flag for human
        return "review" if (mech >= 0.85 or choice == "real_finding") else "needs_manual"
    if choice == "boilerplate" and conf >= REVIEW_CONF:
        return "dismiss"
    return "needs_manual"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--calibrate", action="store_true", help="run only ground-truth-labeled findings")
    ap.add_argument("--limit", type=int, default=50, help="max new (uncached) findings this run")
    ap.add_argument("--family", action="append", default=None)
    args = ap.parse_args()

    labels = json.load(open("artifacts/flag_triage_labels.json"))["by_protocol"]
    items = flatten()
    if args.family:
        items = [i for i in items if i["family"] in args.family]

    results_path = "artifacts/flag_triage/results.jsonl"
    os.makedirs(os.path.dirname(results_path), exist_ok=True)
    done = set()
    if os.path.exists(results_path):
        for line in open(results_path):
            try:
                r = json.loads(line)
                done.add((r["address"], r["family"], r["line"]))
            except Exception:
                pass

    if args.calibrate:
        todo = [i for i in items if i["address"].lower() in labels]
    else:
        todo = [i for i in items if (i["address"], i["family"], i["line"]) not in done]
    print(f"findings to triage: {len(todo)} (spends ~{len(todo)}x0.7k tokens of quota unless cached)", flush=True)

    outf = open(results_path, "a")
    n_new = 0
    for i, item in enumerate(todo):
        key = (item["address"], item["family"], item["line"])
        if key in done:
            continue
        try:
            answers = ts.ask(state_for(item), QUESTIONS)
        except Exception as e:
            print(f"  API error at {item['address']} {item['family']}: {str(e)[:100]} — stopping (rerun to resume)", flush=True)
            break
        rec = dict(item, answers=answers, policy=policy(answers))
        outf.write(json.dumps(rec, default=str) + "\n")
        done.add(key)
        n_new += 1
        if n_new % 10 == 0:
            print(f"  {n_new} triaged", flush=True)
    outf.close()
    ts._cache_save()
    print(f"triaged {n_new} new; results: {results_path}", flush=True)

    # ---- report + calibration ----
    recs = [json.loads(l) for l in open(results_path)]
    labeled = [r for r in recs if r["address"].lower() in labels]
    if args.calibrate or labeled:
        agree = disagree = 0
        print(f"\ncalibration vs reports/2026-09-16-bugscan.md ground truth ({len(labeled)} labeled):")
        for r in labeled:
            truth = labels[r["address"].lower()].get(r["family"])
            if truth is None:
                continue
            # truth: 'noise' | 'exploitable'  vs policy: dismiss|review|needs_manual
            expected = "dismiss" if truth == "noise" else "review"
            ok = r["policy"] == expected or (expected == "review" and r["policy"] == "needs_manual")
            agree += ok
            disagree += (not ok)
            mark = "ok " if ok else "MISS"
            print(f"  [{mark}] {r['protocol'] or r['name'][:18]:20} {r['family']:22} "
                  f"policy={r['policy']:12} mech_p={r['answers'].get('mechanism_present',{}).get('noul')} truth={truth}")
        print(f"\nagreement: {agree}/{agree + disagree}")
    counts = {}
    for r in recs:
        counts[r["policy"]] = counts.get(r["policy"], 0) + 1
    print("policy distribution (all runs):", counts)


if __name__ == "__main__":
    main()
