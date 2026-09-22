#!/usr/bin/env python3
"""semantic_family_scan — TypeSafe semantic matching for families regex can't see (#2).

The regex scanner only matches hard-coded shapes; the 2026-07-24 Lien hack
(running-counter equivalence) proved the gap. For each finding context in the
bugscan corpus, ask one Noul per semantic family — independent questions over
the same state run in parallel in a single request.

Semantic-only families (regex has no signature for these):
  counter-equivalence   aggregate counter standing in for per-element multiset
                        verification across input/output/exception lists
  zero-amount-batch     batch loops crediting per-item state without amount check
  naive-nav             valuation read from live accounting a donor can inflate

Policy (here, in code): flag when any family Noul >= FLAG_FLOOR; escalate to
review at >= REVIEW_FLOOR.

Run:
  python3 scripts/semantic_family_scan.py --limit 30          # resumable sweep
  python3 scripts/semantic_family_scan.py --family all        # also re-ask regex families
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import typesafe_client as ts

SEMANTIC_FAMILIES = {
    "counter-equivalence": "an exchange/convert/migrate function that must burn one set and mint an equivalent set, but verifies equivalence by incrementing/decrementing a running counter on list membership instead of comparing elements one-to-one; duplicated list entries or exception lists can then mint without burning",
    "zero-amount-batch": "a batch operation that credits per-item state (balances, tiers, rewards) without requiring each amount to be non-zero",
    "naive-nav": "a valuation or share-price path that reads live accounting (totals, reserves, wrappers) which a direct donation can inflate in the same transaction",
}
FLAG_FLOOR = 0.60
REVIEW_FLOOR = 0.80


def questions(families):
    q = {}
    for fam, desc in families.items():
        q[fam] = {
            "type": "noul",
            "instructions": f"Does this code implement the following bug pattern? Pattern: {desc}",
            "criteria": {
                "true": "the pattern is present in this code with an attacker-reachable path",
                "false": "the pattern is absent, or present only as boilerplate with no attacker surface"
            }
        }
    return q


def state_for(item):
    return {
        "contract": {"name": item.get("name"), "chain": item.get("chain"),
                     "tvl_usd": item.get("tvl_usd"), "protocol": item.get("protocol_guess")},
        "code_context": (item.get("context") or "")[:1200],
        "regex_family_that_flagged_it": item.get("family"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--family", default="semantic", choices=["semantic", "all"])
    args = ap.parse_args()

    fams = SEMANTIC_FAMILIES
    out_path = "artifacts/semantic_family/results.jsonl"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    done = set()
    if os.path.exists(out_path):
        for line in open(out_path):
            try:
                r = json.loads(line)
                done.add((r["address"], r["family"], r["line"]))
            except Exception:
                pass

    items = []
    for path in ("artifacts/bugscan_results.json", "artifacts/bugscan_results_llama.json"):
        for c in json.load(open(path)):
            for f in c.get("findings") or []:
                items.append(dict(f, name=c.get("name"), chain=c["chain"],
                                  address=c["address"], tvl_usd=c.get("tvl_usd"),
                                  protocol_guess=c.get("protocol_guess")))
    todo = [i for i in items if (i["address"], i["family"], i["line"]) not in done][:args.limit]
    print(f"semantic scan: {len(todo)} contexts (resumable; cache avoids re-spend)", flush=True)

    outf = open(out_path, "a")
    flagged = 0
    for i, item in enumerate(todo):
        try:
            answers = ts.ask(state_for(item), questions(fams))
        except Exception as e:
            print(f"  API error: {str(e)[:100]} — stopping (rerun resumes)", flush=True)
            break
        best = max(answers.items(), key=lambda kv: kv[1].get("noul", 0))
        rec = dict(item, answers=answers,
                   best_family=best[0], best_p=best[1].get("noul", 0))
        rec["verdict"] = ("review" if rec["best_p"] >= REVIEW_FLOOR
                          else "flag" if rec["best_p"] >= FLAG_FLOOR else "clean")
        flagged += rec["verdict"] != "clean"
        outf.write(json.dumps(rec, default=str) + "\n")
        if rec["verdict"] != "clean":
            print(f"  [{rec['verdict'].upper()}] {item.get('name') or item['address'][:12]} "
                  f"{rec['best_family']} p={rec['best_p']:.2f}  ctx={ (item.get('context') or '')[:70]!r}", flush=True)
        if (i + 1) % 10 == 0:
            print(f"  {i+1}/{len(todo)} scanned, {flagged} flagged", flush=True)
    outf.close()
    ts._cache_save()
    print(f"done: {flagged} flagged of {len(todo)}; results: {out_path}")


if __name__ == "__main__":
    main()
