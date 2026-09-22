#!/usr/bin/env python3
"""Export a selected JSON scanner record without importing the scanner pipeline.

This is discovery metadata, not a verified audit scope. Repo URLs are explicit:
python scripts/export_audit_handoff.py --input artifacts/hunt_campaign/selection.json --target origin-arm --repo core=https://github.com/ORG/REPO --output artifacts/handoffs/origin-arm.json
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlparse


def export(source, target, repositories, refs=None, reason=None):
    source = Path(source).resolve()
    raw = source.read_bytes()
    data = json.loads(raw.decode("utf-8-sig"))
    rows = data if isinstance(data, list) else data.get("candidates", data.get("records", [data]))
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("Expected a JSON record, a list of records, or an object containing candidates/records.")
    matches = [r for r in rows if target in (r.get("slug"), r.get("target_name"), r.get("protocol_id"))]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one record for {target}; found {len(matches)}.")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,79}", target):
        raise ValueError("Target must be a lowercase filesystem-safe slug.")
    row = matches[0]
    refs = refs or {}
    repos = []
    for name, url in repositories.items():
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,79}", name):
            raise ValueError("Repository IDs must be lowercase filesystem-safe names.")
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Supply credential-free HTTPS repository URLs.")
        repos.append({"id": name, "url": url, "ref": refs.get(name, "HEAD")})
    if not repos or set(refs) - set(repositories):
        raise ValueError("Supply at least one --repo; --ref names must match repositories.")
    chains = row.get("chains") or ([row["chain"]] if row.get("chain") else [])
    addresses = []
    # Only explicit chain/address pairs become scope candidates. Never copy one
    # anchor to every chain in a protocol-level TVL record.
    if row.get("chain") and (row.get("address") or row.get("contract_address")):
        addresses.append({"chain": row["chain"], "address": row.get("address") or row["contract_address"], "status": "unverified"})
    for entry in row.get("walked_funded", []):
        if entry.get("chain") and entry.get("address"):
            addresses.append({"chain": entry["chain"], "address": entry["address"], "status": "unverified"})
    timestamp = datetime.now(timezone.utc).isoformat()
    tvl = row.get("tvl_usd", row.get("tvl", row.get("tvl_llama")))
    return {
        "schema_version": 1, "protocol_id": target,
        "name": row.get("display_name") or row.get("name") or target,
        "exported_at": timestamp, "repositories": repos,
        "discovery": {
            "source_file": str(source), "source_sha256": hashlib.sha256(raw).hexdigest(),
            "source_file_modified_at": datetime.fromtimestamp(source.stat().st_mtime, timezone.utc).isoformat(),
            "observation_time": row.get("observed_at") or row.get("timestamp"),
            "tvl_usd": tvl, "chains": chains, "category": row.get("category"),
            "anchor_unassigned": row.get("anchor"), "reason": reason or row.get("reason") or "Selected for manual audit review.",
        },
        "scope": {
            "contracts": addresses, "status": "requires-review",
            "bounty_url": row.get("bounty_url") or row.get("bounty_program_url"),
            "documentation_urls": row.get("documentation_urls", []),
            "exclusions": row.get("exclusions", []),
            "open_questions": [
                "Confirm repository commits match deployed implementations where deployment is in scope.",
                "Confirm contract addresses per chain, proxy targets, block numbers and current bounty scope.",
                "Scanner observations and inferred repository links are not authoritative audit facts.",
            ],
        },
    }


def pairs(values):
    result = {}
    for value in values:
        name, sep, text = value.partition("=")
        if not sep or not name or not text or name in result:
            raise ValueError("Expected unique name=value pairs.")
        result[name] = text
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--repo", action="append", required=True, metavar="NAME=HTTPS_URL")
    parser.add_argument("--ref", action="append", default=[], metavar="NAME=REF")
    parser.add_argument("--reason")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        result = export(args.input, args.target, pairs(args.repo), pairs(args.ref), args.reason)
        output = Path(args.output)
        if output.exists():
            raise ValueError("Output already exists. Choose a new handoff filename to preserve its provenance.")
        output.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation makes concurrent exporters fail instead of overwriting.
        with output.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(result, handle, indent=2)
            handle.write("\n")
        print(output.resolve())
    except (ValueError, OSError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
