#!/usr/bin/env python3
"""delta_triage — TypeSafe prioritization of delta-watch changed files (#5).

Parses the pipe-tables in reports/<date>-delta-watch/targets/*.md
(`| path | status | +n/-n | role |`) and asks one Noul per changed file:
does this change touch security-relevant logic? Policy here: review first —
sorted by (noul, churn) — everything below PRIORITY_FLOOR deprioritized.

Run: python3 scripts/delta_triage.py [report-dir]
     (default: newest reports/*-delta-watch/targets/)
"""
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import typesafe_client as ts

QUESTION = {
    "security_relevant": {
        "type": "noul",
        "instructions": "Does this changed file plausibly contain security-relevant logic worth human review (auth, keys, validation, deposit/withdrawal/bridge state machines, signatures, thresholds)?",
        "criteria": {
            "true": "the file's role/path indicates security-sensitive logic",
            "false": "generated clients, docs, tests, styling, or plumbing"
        }
    },
}
PRIORITY_FLOOR = 0.50
ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*(modified|added|removed)\s*\|\s*([+-]\d+/[+-]\d+|\+[0-9]+|-[0-9]+)\s*\|\s*([^|]+)\|", re.I)


def parse_targets(report_dir):
    rows = []
    for md in sorted(glob.glob(os.path.join(report_dir, "targets", "*.md"))):
        target = os.path.basename(md)[:2]
        try:
            text = open(md, "rb").read().decode("utf-8", errors="ignore")
        except OSError as e:
            print(f"  cannot read {md}: {e} — skipping (OneDrive lock? retry later)", flush=True)
            continue
        for line in text.splitlines():
            m = ROW.match(line.strip())
            if m:
                path, status, churn, role = m.groups()
                rows.append({"target": target, "path": path, "status": status.lower(),
                             "churn": churn, "role": role.strip()})
    return rows


def churn_total(churn):
    return sum(int(x) for x in re.findall(r"\d+", churn)[:2])


def main():
    report_dir = sys.argv[1] if len(sys.argv) > 1 else sorted(glob.glob("reports/*-delta-watch"))[-1]
    rows = parse_targets(report_dir)
    print(f"{report_dir}: {len(rows)} changed files", flush=True)
    out_path = "artifacts/delta_triage/results.jsonl"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    done = set()
    if os.path.exists(out_path):
        for line in open(out_path):
            try:
                r = json.loads(line)
                done.add((r["target"], r["path"]))
            except Exception:
                pass
    outf = open(out_path, "a")
    results = []
    for i, r in enumerate(rows):
        if (r["target"], r["path"]) in done:
            continue
        state = {"changed_file": r["path"], "change_status": r["status"],
                 "churn_lines": churn_total(r["churn"]), "assigned_role": r["role"]}
        try:
            a = ts.ask(state, QUESTION)
        except Exception as e:
            print(f"  API error: {str(e)[:100]} — stopping (rerun resumes)", flush=True)
            break
        p = a.get("security_relevant", {}).get("noul", 0) or 0
        rec = dict(r, noul=p, review=("priority" if p >= PRIORITY_FLOOR else "deprioritize"))
        results.append(rec)
        outf.write(json.dumps(rec, default=str) + "\n")
        if (i + 1) % 10 == 0:
            print(f"  {i+1}/{len(rows)} triaged", flush=True)
    outf.close()
    ts._cache_save()
    results.sort(key=lambda r: (-r["noul"], -churn_total(r["churn"])))
    print("\npriority review order:")
    for r in results:
        if r["review"] == "priority":
            print(f"  {r['noul']:.2f}  {r['churn']:>10}  {r['role'][:14]:14} {r['path'][:80]}")
    pri = sum(1 for r in results if r["review"] == "priority")
    print(f"\n{pri} priority files of {len(results)} triaged -> {out_path}")


if __name__ == "__main__":
    main()
