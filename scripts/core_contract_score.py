#!/usr/bin/env python3
"""core_contract_score — TypeSafe ranking of core-protocol contracts (#3).

The pipeline's #1 documented gap: llama's bulk `address` surfaces tokens, while
exploitable core contracts never enter the candidate pool. This scores cached
verified sources: is this contract core value-bearing logic, or a token /
wrapper / governance shell? High-scoring cores that were never deep-triaged
become the next bugscan targets.

Policy in code: candidates with choice == core_logic and confidence >= 0.6 are
promoted to the priority pool.

Run: python3 scripts/core_contract_score.py --limit 30
Sources are read from the equiv_corpus cache (scripts/equiv_scan.py) or deep_b3b4.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import typesafe_client as ts

QUESTIONS = {
    "contract_role": {
        "type": "choice",
        "instructions": "What is this contract's role in its protocol?",
        "criteria": {
            "core_logic": "core value-bearing protocol logic: holds/moves user funds, prices assets, manages collateral or accounting",
            "token": "an ERC20/ERC721 token contract itself (governance or asset token)",
            "wrapper_peripheral": "wrapper, adapter, helper library, or UI-facing peripheral",
            "governance_admin": "governance, voting, timelock, or parameter admin",
            "other": "anything else"
        }
    },
    "value_density": {
        "type": "score",
        "instructions": "How much value does this contract custody or control, judging from its code and metadata?",
        "criteria": [
            "none: no user funds flow through it",
            "low: incidental balances only",
            "medium: meaningful protocol accounting depends on it",
            "high: primary custody or pricing contract for user funds"
        ]
    },
}
CORE_CONF = 0.60


def load_sources():
    """(chain, address, name, source_head) for every cached verified source."""
    out = []
    cache = "artifacts/equiv_corpus"
    if os.path.isdir(cache):
        for fn in os.listdir(cache):
            if not fn.endswith(".sol"):
                continue
            stem = fn[:-4]
            m = re.match(r"(\w+)_(0x[0-9a-fA-F]{40})$", stem)
            if not m:
                continue
            path = os.path.join(cache, fn)
            text = open(path, encoding="utf-8", errors="ignore").read()
            out.append({"chain": m.group(1), "address": m.group(2),
                        "source_head": text[:2500], "source_len": len(text)})
    return out


def meta_from_artifacts():
    meta = {}
    for path in ("artifacts/bugscan_results.json", "artifacts/bugscan_results_llama.json"):
        for c in json.load(open(path)):
            meta[c["address"].lower()] = {"name": c.get("name"), "tvl_usd": c.get("tvl_usd"),
                                          "protocol": c.get("protocol_guess")}
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=30)
    args = ap.parse_args()
    meta = meta_from_artifacts()
    out_path = "artifacts/core_contract/results.jsonl"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    done = set()
    if os.path.exists(out_path):
        for line in open(out_path):
            try:
                done.add(json.loads(line)["address"])
            except Exception:
                pass
    items = [s for s in load_sources() if s["address"] not in done][:args.limit]
    print(f"scoring {len(items)} cached contracts (resumable)", flush=True)
    outf = open(out_path, "a")
    promoted = []
    for i, s in enumerate(items):
        m = meta.get(s["address"], {})
        state = {
            "contract": {"name": m.get("name"), "chain": s["chain"],
                         "approx_tvl_usd": m.get("tvl_usd"), "protocol": m.get("protocol"),
                         "source_bytes": s["source_len"]},
            "source_head": s["source_head"],
        }
        try:
            answers = ts.ask(state, QUESTIONS)
        except Exception as e:
            print(f"  API error: {str(e)[:100]} — stopping (rerun resumes)", flush=True)
            break
        role = answers.get("contract_role", {}).get("choice")
        conf = answers.get("contract_role", {}).get("confidence", 0) or 0
        # score answer shape: {"score": index-or-label, ...} — accept either
        vd = answers.get("value_density", {})
        level = vd.get("score", vd.get("level"))
        rec = dict(s, name=m.get("name"), protocol=m.get("protocol"),
                   tvl_usd=m.get("tvl_usd"), answers=answers,
                   role=role, role_conf=conf, value_density=str(level))
        is_core = role == "core_logic" and conf >= CORE_CONF
        rec["promoted"] = is_core
        if is_core:
            promoted.append(rec)
            print(f"  [CORE] {m.get('name') or s['address'][:12]:22} conf={conf:.2f} "
                  f"value={level} tvl={m.get('tvl_usd')}", flush=True)
        outf.write(json.dumps(rec, default=str) + "\n")
        if (i + 1) % 10 == 0:
            print(f"  {i+1}/{len(items)} scored", flush=True)
    outf.close()
    ts._cache_save()
    print(f"promoted {len(promoted)} core-logic candidates -> {out_path}")


if __name__ == "__main__":
    main()
