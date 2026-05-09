"""Probe Alchemy fresh-deployment yield at varying sample rates.

Usage:
    .venv/bin/python scripts/probe_alchemy.py [SAMPLE_BLOCKS] [RECEIPT_CONCURRENCY]

Reads tvl-scanner/alchemy from `pass`, calls
discover.alchemy.fetch_fresh_deployments per EVM chain at the given knob
values, prints per-chain creation count, candidates above MIN_TVL_USD,
wall time, and any 429 events. Logs at DEBUG so rate-limit failures
surface as "alchemy rpc ... failed" lines.

This is a development tool, not part of the production pipeline.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time
from io import StringIO

from tvl_scanner.config import settings
from tvl_scanner.discover import alchemy as alchemy_mod
from tvl_scanner.enrich.prices import PriceCache
from tvl_scanner.http import make_client
from tvl_scanner.models import Chain


EVM_CHAINS = [
    Chain.ETHEREUM,
    Chain.ARBITRUM,
    Chain.BASE,
    Chain.OPTIMISM,
    Chain.POLYGON,
    Chain.BSC,
]


async def probe(sample_blocks: int, receipt_concurrency: int) -> None:
    # Monkey-patch module constants. fetch_fresh_deployments takes
    # sample_blocks as a kwarg; receipt_concurrency is read from the
    # module-level constant inside the function, so we mutate that.
    alchemy_mod.RECEIPT_CONCURRENCY = receipt_concurrency

    # Capture DEBUG logs from the alchemy module to count 429s.
    log_buf = StringIO()
    handler = logging.StreamHandler(log_buf)
    handler.setLevel(logging.DEBUG)
    alchemy_mod.log.addHandler(handler)
    alchemy_mod.log.setLevel(logging.DEBUG)
    # Also surface to console at INFO.
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    alchemy_mod.log.addHandler(console_handler)

    s = settings()
    threshold = s.MIN_TVL_USD

    print(f"\n=== Probe: SAMPLE_BLOCKS={sample_blocks}, "
          f"RECEIPT_CONCURRENCY={receipt_concurrency}, "
          f"MIN_TVL=${threshold:,} ===")

    async with make_client() as client:
        cache = PriceCache()

        async def run_one(chain: Chain) -> tuple[Chain, list, float]:
            t0 = time.monotonic()
            kept = await alchemy_mod.fetch_fresh_deployments(
                chain,
                price_cache=cache,
                client=client,
                sample_blocks=sample_blocks,
            )
            return chain, kept, time.monotonic() - t0

        results = await asyncio.gather(
            *(run_one(c) for c in EVM_CHAINS), return_exceptions=False
        )

    print("\n--- Yield per chain ---")
    print(f"{'chain':<10} {'kept':>5} {'time_s':>8}")
    for chain, kept, dt in results:
        print(f"{chain.value:<10} {len(kept):>5} {dt:>8.1f}")

    # Top survivors (if any) so we can eyeball quality.
    all_kept = [(c, k) for c, ks, _ in results for k in ks]
    if all_kept:
        print(f"\n--- {len(all_kept)} candidates above ${threshold:,} ---")
        for chain, k in sorted(all_kept, key=lambda x: -x[1].tvl_usd)[:10]:
            print(f"  {chain.value:<10} {k.address}  TVL=${k.tvl_usd:>14,.0f}  age={(s.scan_date if hasattr(s,'scan_date') else None)} first_seen={k.first_seen}")

    # 429 / failure detection from the captured buffer.
    log_text = log_buf.getvalue()
    rate_limit_hits = log_text.count("429") + log_text.lower().count("rate limit")
    rpc_failures = log_text.count("alchemy rpc")
    print(f"\n--- RPC health ---")
    print(f"  rpc failures (any): {rpc_failures}")
    print(f"  '429'/'rate limit' mentions: {rate_limit_hits}")
    if rate_limit_hits > 0:
        print("  WARNING: rate-limited. Dial back concurrency or sample size.")


def main() -> None:
    sample_blocks = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    receipt_concurrency = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    asyncio.run(probe(sample_blocks, receipt_concurrency))


if __name__ == "__main__":
    main()
