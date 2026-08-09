# Immunefi Bounty Triage — 2026-08-09

**Method**: `tvl-scanner immunefi-scan` on the 12-criteria bounty formula
(`rank/bounty_priority.py`), then hand-filtered for data artifacts and prior kills.

```
tvl-scanner immunefi-scan --cutoff 0 --cap 60 \
    --exclude-invite-only --exclude-pay-to-submit --exclude-level-gated \
    --exclude-slugs-file reports/excluded-slugs.txt
```

**Funnel** (247 programs fetched):

| Drop | Reason |
|------|--------|
| −86 | no in-scope contract on a supported chain |
| −18 | program closed (competition ended) |
| −1 | invite-only |
| −4 | on the exclusion list (KAST, SparkLend, Pareto, Beanstalk) |
| −16 | Pay to Submit — charges a fee per report |
| **122** | **kept for enrichment and ranking; top 60 written** |

Lives beside the auto-generated `2026-08-09-immunefi-scan.md`, which is regenerated on
every run and gitignored. This file is hand-written analysis and is tracked.

---

## Ranked leads

| # | Target | Floor / cap | %TVL | TVL | Scope | New 90d | Last audit | Density | KYC |
|---|--------|-------------|------|-----|-------|---------|-----------|---------|-----|
| 1 | **Strata** | $10k / $250k | 0.33% | $75.7M | 11 | **11 (100%)** | 145d | 7 | yes |
| 2 | **GMTrade** | **$25k** / $100k | 0.30% | $32.8M | **6** | **6 (100%)** | 145d | 8 | no |
| 3 | **Enzyme Onyx** | $20k / $200k | ? | ? | 49 | 27 | **342d** | 7 | no |
| 4 | **Twyne** | $20k / $50k | 0.34% | $14.5M | 16 | 3 | 205d | **3** | no |
| 5 | Katana | $20k / $80k | **5.49%** | $1.5M | 23 | 10 | 179d | 9 | yes |
| 6 | ZKsync Era | **$100k** / $300k | ? | ? | 110 | **91** | none listed | 6 | yes |
| 7 | Balancer | **$100k** / $1M | 3.71% | $27.0M | 24 | 14 | **613d** | 16 | no |
| 8 | Immutable | $50k / $1M | 4.47% | $22.4M | 10 | 0 | 426d | 5 | yes |
| 9 | CapyFi | $50k / $1M | **13.6%** | $7.4M | 10 | 0 | 381d | 10 | yes |
| 10 | Hashflow | $5k / $50k | **20.8%** | $241k | 4 | 4 | none listed | 0 (unverified) | no |

### The three worth a week

**Strata** — all 11 in-scope contracts entered the bounty *after* the 145-day-old
Guardian/Cyfrin/Quantstamp audit, on $75.7M of real TVL, with a scope small enough to
read end to end. Already on the delta-watch list as `strata-markets`, so a baseline
commit exists. Read its 3 published known issues first.

**GMTrade** — same 100%-fresh-scope shape on the tightest real scope in the catalogue
(6 contracts), $32.8M TVL, no KYC, $25k guaranteed critical floor, 33-day-old program
so saturation is low. Rust / Solana.

**Enzyme Onyx** — widest audit-to-scope gap in the set: one ChainSecurity audit **342
days** ago with 27 contracts added since, newest 9 days old. No KYC, 0 known issues.
Also on the delta-watch list.

No-KYC posture: GMTrade → Enzyme Onyx → Twyne, with Balancer as the high-floor swing
($100k floor and a 613-day-old audit against 14 newly-added contracts; its audit
density of 16 is the only thing holding it at #7).

---

## Ruled out

| Target | Reason |
|--------|--------|
| **Alchemix V3** | Lead #1 on 2026-07-30, now **excluded**: `Pay to Submit` **and** a researcher-level gate — *"focusing our review bandwidth on reports from researchers at the Intermediate level or higher."* Both barriers land before any code work. |
| **TruYields** (raw rank 4) | DefiLlama name-match resolves TVL to **$7**, producing a 406,000% payout ratio that floats it into the top five. Artifact, not a lead. |
| Lombard, Royco, Ostium, Kamino, Ethena, NUVA, Intuition, Stargate, EtherFi, LayerZero, Avalanche, Optimism, The Graph, Cosmos, Babylon | `Pay to Submit` — a per-report fee, win or lose. |
| **KAST** | Already audited by us. Permanently excluded (carried from 2026-07-30). |
| **SparkLend** | Fourth appearance, third rejection. Deployed == audited. |
| **Pareto Credit** | 14 audits; critical is `up_to` $50k ⇒ 0.022% of TVL. |
| **Beanstalk** | No fresh delta. |

---

## Run caveats

Three limits of the environment this scan ran in. All of them bias *toward* making
candidates look more attractive, so they matter:

1. **GitHub search returned 403** — the Sherlock/Cantina contest search found nothing.
   Per the Batch H skip this only affected candidates with zero DefiLlama audits, which
   means the **density-0 rows are the least verified numbers here** (Hashflow, and
   Livepeer/mtpelerin/galagames further down). Unresolved, *not* confirmed absent —
   the same trap flagged for Livepeer on 2026-07-30.
2. **No Etherscan / Alchemy keys** — 0/96 deploy dates resolved and 0/53 on-chain TVL
   fallbacks ran, so 53 candidates carry `?` TVL and score criterion 1 neutrally.
3. **DefiLlama name-match artifacts** — beyond TruYields, distrust Stargate (252%),
   Notional Exponent ($1,615), Intuition ($0) and Synthetix ($879k).

## Verification before committing the week

Criterion 9 reads `assets[].addedAt`, which is **when Immunefi listed a contract, not
when it was deployed**. A team can add year-old code to scope. It is a strong lead
signal, not proof of unaudited code.

Do what the Alchemix check did on 2026-07-30: pull deploy/upgrade dates for Strata's 11
and GMTrade's 6 on-chain and confirm the delta is live rather than a listing artifact.
~20 minutes, and it is what separates these from a wasted week.
