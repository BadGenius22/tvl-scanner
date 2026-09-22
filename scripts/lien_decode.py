#!/usr/bin/env python3
"""Decode the 2026-07-24 Lien exploit tx logs against verified ABIs.

Fetches ABIs for the BondMaker + GeneralizedDotc from Etherscan, matches receipt
log topics to event signatures, and writes a human-readable decode to
artifacts/lien/exploit_decoded.json.
"""
import json
import time
import urllib.request

from Crypto.Hash import keccak

RECEIPT = "artifacts/lien/receipt_b96d572b.json"
ABIS = {
    "0xda6fc5625e617bb92f5359921d43321cebc6bef0": "BondMakerCollateralizedEth",
    "0x843225cf6e663e4454732d6b551a737ac7b47de0": "BondMakerCollateralizedEth(2)",
    "0x656e5e976d523a427f05b0c212a22a89ccd9ef18": "GeneralizedDotc",
    "0x814a4cb84a0a1bb69126e4ac871a7f09fc417b49": "IMT10160000",
    "0x793ec4a2b6da9995b959ef73cd10fdc41a4a25a5": "LBT10164000",
}


def key_of():
    for line in open(".env"):
        if line.startswith("ETHERSCAN_API_KEY") and "=" in line:
            return line.split("=", 1)[1].strip()


def get_abi(addr):
    q = f"chainid=1&module=contract&action=getabi&address={addr}&apikey={key_of()}"
    url = f"https://api.etherscan.io/v2/api?{q}"
    for i in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "tvl-scanner"}), timeout=30) as r:
                d = json.load(r)
            if d.get("status") == "1" and d.get("result", "").startswith("["):
                return json.loads(d["result"])
            return []
        except Exception:
            time.sleep(1.5 * (i + 1))
    return []


def topic_of(abi_event):
    types = ",".join(_canon(i["type"], i) for i in abi_event.get("inputs", []))
    sig = f"{abi_event['name']}({types})"
    k = keccak.new(digest_bits=256)
    k.update(sig.encode())
    return "0x" + k.hexdigest(), sig


def _canon(t, comp):
    if t == "tuple":
        inner = ",".join(_canon(c["type"], c) for c in comp["components"])
        return f"({inner})"
    if t.endswith("[]"):
        base = _canon(t[:-2], comp)
        return f"{base}[]"
    return t


def decode_word(w):
    v = int(w, 16)
    # print as signed too when high bit set
    if v >= 2**255:
        return v - 2**256, v
    return v


def main():
    receipt = json.load(open(RECEIPT))
    topics = {}
    for addr, label in ABIS.items():
        abi = get_abi(addr)
        for item in abi:
            if item.get("type") == "event":
                h, sig = topic_of(item)
                topics.setdefault(h, (label, item))
        time.sleep(0.3)
    print(f"built topic map: {len(topics)} events from {len(ABIS)} ABIs")

    out = []
    for lg in receipt["logs"]:
        emitter = "0x" + lg["address"].lower()
        t0 = lg["topics"][0] if lg["topics"] else ""
        label, ev = topics.get(t0, ("unknown", None))
        entry = {"emitter": emitter, "label": label}
        if ev:
            entry["event"] = ev["name"]
            ins = ev.get("inputs", [])
            for i, comp in enumerate(ins):
                if comp.get("indexed") and i + 1 < len(lg["topics"]):
                    entry[comp["name"] or f"topic{i}"] = "0x" + lg["topics"][i + 1][-40:] if comp["type"] == "address" else str(int(lg["topics"][i + 1], 16))
            data = lg["data"][2:]
            words = [data[j:j + 64] for j in range(0, len(data), 64)]
            dyn = [c for c in ins if not c.get("indexed")]
            wi = 0
            for comp in dyn:
                if comp["type"] in ("uint256", "uint64", "uint128", "int256", "int16"):
                    entry[comp["name"] or "arg"] = str(int(words[wi], 16))
                    wi += 1
                elif comp["type"] == "address":
                    entry[comp["name"] or "arg"] = "0x" + words[wi][-40:]
                    wi += 1
                elif comp["type"] == "bytes32[]":
                    off = int(words[wi], 16) // 32
                    n = int(words[off], 16)
                    arr = [words[off + 1 + j] for j in range(n)]
                    entry[comp["name"] or "arg"] = ["0x" + a for a in arr]
                    wi += 1
                elif comp["type"] == "address[]":
                    off = int(words[wi], 16) // 32
                    n = int(words[off], 16)
                    arr = ["0x" + words[off + 1 + j][-40:] for j in range(n)]
                    entry[comp["name"] or "arg"] = arr
                    wi += 1
                elif comp["type"] == "bytes":
                    entry[comp["name"] or "arg"] = "0x" + words[wi + 1][: min(64, int(words[wi + 1 + 0], 0) if False else 64)]
                    wi += 2
                else:
                    entry[comp["name"] or "arg"] = words[wi]
                    wi += 1
        else:
            entry["topic0"] = t0
            entry["data"] = lg["data"][:100]
        out.append(entry)

    json.dump(out, open("artifacts/lien/exploit_decoded.json", "w"), indent=1)
    for e in out:
        ev = e.get("event", "?")
        compact = {k: v for k, v in e.items() if k not in ("emitter", "label", "event")}
        print(f"{e['label'][:28]:28} {ev:30} {json.dumps(compact, default=str)[:220]}")


if __name__ == "__main__":
    main()
