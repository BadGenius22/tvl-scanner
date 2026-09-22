#!/usr/bin/env python3
"""bounty_value — TypeSafe go/no-go composite for findings (#4).

Input: a JSON list of findings with a human summary, chain, and value estimate
(default: the real conclusions from the Lien deep-dive). Three independent
questions in one request: stranger_exploitable (Noul), bounty_worthiness
(Score 0-4), effort (Score 0-3). Weights and the decision are HERE, in code.

Run: python3 scripts/bounty_value.py [findings.json]
     (no arg -> built-in items from reports/2026-09-17-lien-deepdive.md)
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import typesafe_client as ts

# composite weights (code owns the policy)
W_EXPLOIT, W_BOUNTY = 0.6, 0.4
GO_FLOOR = 3.0   # 0-5 composite

DEFAULT_ITEMS = [
    {"id": "peakdefi-eoa-admin", "chain": "ethereum",
     "summary": "PEAK TokenProxy upgrade key is a bare EOA; DEFAULT_ADMIN_ROLE is a second EOA; burnFrom/mint roles exist. Full supply ~1.18B PEAK but market cap only ~$105k, deeply illiquid; 2021 mint incident history.",
     "value_usd": 105000},
    {"id": "lien-bondmaker-unpatched", "chain": "ethereum",
     "summary": "exchangeEquivalentBonds counter bug still live on both BondMakerCollateralizedEth instances; all sinks drained; exploit pays only if fresh collateral is deposited or a venue re-quotes the bond tokens.",
     "value_usd": 0},
    {"id": "bsc-lien-mirror", "chain": "bsc",
     "summary": "Full Lien suite mirror on BSC (3 vulnerable BondMakers + 9 GeneralizedDotc venues) by a different operator; verified TVL $836 in BNB gas residue; no seller allowances live.",
     "value_usd": 836},
    {"id": "lientoken-dividend-pool", "chain": "ethereum",
     "summary": "84.38 ETH sits in LienToken as holder dividends (open receive(), settleProfit/receiveDividend pro rata). Working as designed; claimable by LIEN holders; not a bug.",
     "value_usd": 206156},
]

QUESTIONS = {
    "stranger_exploitable": {
        "type": "noul",
        "instructions": "Can a stranger (not a key holder, not the team) extract meaningful value from this surface today, given the summary?",
        "criteria": {
            "true": "an unprivileged attacker has a concrete path to funds or influence",
            "false": "surface requires trusted keys, is economically pointless, or is empty/drained"
        }
    },
    "bounty_worthiness": {
        "type": "score",
        "instructions": "How likely is a security team or bounty program to pay meaningfully for a report of this finding?",
        "criteria": [
            "nil: defunct protocol, no program, no funds",
            "low: live-ish surface but tiny economics",
            "moderate: funded surface and a plausible audience",
            "high: active protocol with a program and real funds at stake",
            "critical: large funded surface with urgent live exposure"
        ]
    },
    "report_effort": {
        "type": "score",
        "instructions": "How much work is a quality report of this finding (PoC, write-up, responsible comms)?",
        "criteria": [
            "trivial: everything already documented",
            "light: assemble existing notes into a report",
            "moderate: needs a working PoC or extra on-chain proof",
            "heavy: needs sustained engagement with the team"
        ]
    },
}


def composite(a):
    # Score answers may come back as an index/label; map defensively.
    def level(x, n):
        if isinstance(x, int):
            return x / max(1, n - 1)
        if isinstance(x, str):
            digits = "".join(ch for ch in x if ch.isdigit())
            return (int(digits) / max(1, n - 1)) if digits else 0.0
        return 0.0
    expl = a.get("stranger_exploitable", {}).get("noul", 0) or 0
    bw = level(a.get("bounty_worthiness", {}).get("score"), 5)
    return W_EXPLOIT * expl + W_BOUNTY * bw


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else None
    items = json.load(open(path)) if path else DEFAULT_ITEMS
    out_path = "artifacts/bounty_value/results.json"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    results = []
    for it in items:
        a = ts.ask({"finding": it["summary"], "chain": it["chain"],
                    "value_usd_estimate": it.get("value_usd")}, QUESTIONS)
        score = round(composite(a) * 5, 2)
        decision = "GO" if score >= GO_FLOOR else "skip"
        eff = a.get("report_effort", {}).get("score")
        rec = dict(it, answers=a, composite=score, decision=decision, effort=str(eff))
        results.append(rec)
        print(f"[{decision}] {it['id']:28} composite={score:>4} "
              f"exploitable_p={a.get('stranger_exploitable',{}).get('noul')} "
              f"bounty={a.get('bounty_worthiness',{}).get('score')} effort={eff}", flush=True)
    json.dump(results, open(out_path, "w"), indent=1, default=str)
    print(f"saved {out_path}")


if __name__ == "__main__":
    main()
