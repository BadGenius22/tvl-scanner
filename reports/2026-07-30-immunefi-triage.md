# Immunefi Bounty Triage — 2026-07-30

**Method**: manual gate-check of the live Immunefi catalogue (`immunefi.com/public-api/bounties.json`).
**Universe**: 248 programs → 165 active smart-contract → 76 no-KYC → **29 no-KYC ≥ $250k**.
**Gate**: `fresh post-audit delta ∩ in-scope ∩ deployed ∩ real TVL ∩ payout structure`.

> **Revised 17:40** after fixing four scanner defects found during this triage (see
> *Scanner corrections* below). The earlier 14:51 version of this file ranked Pareto
> Credit second on a wrong audit count; that entry is now a NO-GO. Conclusions reached by
> direct on-chain verification were unaffected.

> Lives beside the auto-generated `2026-07-30-immunefi-scan.md`, which is regenerated on
> every run and gitignored. This file is hand-written analysis and is tracked.

---

## Ranked leads

| # | Target | Max / floor | KYC | Gate status | Record |
|---|--------|-------------|-----|-------------|--------|
| 1 | **Alchemix V3** | $150k / **$20k** | no | **CLEARS EVERY GATE** | [→](./2026-07-30-immunefi-triage/candidates/01-alchemix.md) |
| 2 | **Yearn stYFI** | $200k / **$20k** | no | Fresh + deployed + in-scope; audit record open | [→](./2026-07-30-immunefi-triage/candidates/02-yearn-styfi.md) |
| 3 | Lista DAO | $1M / **$100k** | no | Best floor; scope membership open | [→](./2026-07-30-immunefi-triage/candidates/03-listadao.md) |
| 4 | Olympus | $3.33M / — | no | Large oracle delta; deployed parity **not** checked | [→](./2026-07-30-immunefi-triage/candidates/04-olympus.md) |
| 5 | Origin ARM | $1M / — | no | Freshest code, payout capped ~$10–66k → **WATCH** | [→](./2026-07-30-immunefi-triage/candidates/05-originprotocol.md) |

### Ruled out

| Target | Reason |
|--------|--------|
| **SparkLend** ($5M) | `spark-vaults-v2` is 3 source files with **4 audit PDFs** (Cantina + ChainSecurity, v1.0.0/v1.0.1), last pushed 2026-06-24 *before* the July deploy ⇒ deployed == audited. Mainnet sUSDC impl dates to 2025-03-03. **Third rejection** — stop re-triaging Spark on scope-recency. |
| **Pareto Credit** ($50k) | 14 audits, six Sherlock reviews in the last 12 months, most recent **one month before this scan**. TVL is real ($224.3M on-chain, 77% in FalconX alone) but critical is `up_to` **$50k** ⇒ **0.022%** bounty/TVL. |
| **Beanstalk** ($1.1M) | Repo last pushed 2026-05-13. No fresh delta despite a $100k floor. |
| **KAST** ($50k) | Already audited by us. Permanently excluded. |
| **Livepeer** ($40.9M, scan rank 1) | Audit record **unresolved**, not confirmed absent — no firm names on `livepeer.org` or `docs.livepeer.org`. A long-established protocol reading "no audits found" is unverified, not under-audited. **Check manually before spending time.** |

---

## Why payout *structure* outranks headline bounty

The live `rewards[]` array distinguishes two critical models, and this reorders everything:

- `rewardModel: "range"` + `minReward` → a **guaranteed floor**
- `rewardModel: "up_to"` + `tenPercentEconomicRule: true` → **10% of funds at risk, no floor**

A $1M `up_to`/10% program sitting on a $100k vault pays ~$10k. A $1M `range`/min-$100k
program pays $100k minimum for the same finding. Compute this **before** spending
gate-check effort.

| Floor | Programs |
|-------|----------|
| **$100k** | Beanstalk, **Lista**, Stader, mETH |
| **$50k** | SparkLend (on a $5M cap), Lido, Gnosis Chain, CoW, Aevo |
| **$25k** | Flux, Instadapp, Nucleus |
| **$20k** | **Alchemix**, **Yearn** |
| *none* (`up_to` + 10%) | Origin, Olympus, Pareto, Benqi, Ankr, Orca |

---

## Lead 1 — Alchemix V3: clears every gate

The first target in many sessions to pass the full conjunction. Detail in the record; the
short version:

- **Fresh**: 131 commits to `src/` since the last listed audit (yAudit **2026-03-15**).
- **Deployed, and it is the fresh code**: the proxies were upgraded past the April
  deployment. Live impls `0xd5f26c90…` (mainnet, shared by both alchemists) and
  `0x40ba0d16…` (Arbitrum) were both created **2026-07-25 — five days before this scan**.
  Membership-tested the deployed verified source: `performanceFee` ×7, `forceDeallocate`
  ×4, `earmark` ×310. The delta is live, not repo-only.
- **In scope**: the only two assets are `alchemix.fi` (**Primacy of Impact**) and
  `github.com/alchemix-finance/v3/tree/master/src` — **directory-level**, so all of
  `src/` counts.
- **Real value**: ~4.56M alUSD + ~6,626 alETH debt outstanding on mainnet.

**Caveats**: five prior audits exist and a prior session tagged this "comp-saturated";
the 10% rule caps realised payout; and it is unknowable from outside whether the 07-25
implementation got an unlisted audit. What is certain: no *listed* audit covers it, and
hunter saturation on five-day-old code is low.

**Trap worth remembering**: the repo's own audit PDFs sit in `lib/vault-v2/audits/` and
belong to a **dependency**, not to V3. Dating the code from them would have been wrong by
four months.

---

## Lead 2 — Yearn stYFI: breaks the scope-add pattern

Prior sessions established that a recent scope-add is usually the *most*-audited code
(Sky, Balancer, Pyth, Spark all died on that). stYFI is the counter-example: 12 contracts
deployed **2026-06-02/06-04**, added to scope **2026-07-01**, and **no audit found** —
Immunefi's `audits` array is empty and `yearn/stYFI` has **zero** audit paths across 45
Vyper sources.

Best payout structure of any lead: **$200k max, $20k floor, no 10% dilution, no KYC**.

**Close first**: absence of an `audits/` folder is not proof of no audit. The whole thesis
rests on that one assumption.

---

## Open items

1. **Yearn stYFI audit record** — resolve whether Yearn published a stYFI audit elsewhere.
2. **Lista scope membership** — `lista-v2` / `lista-v3` / `lista-new-contracts` are pushed
   weekly, but Lista is **Primacy of Rules** with 57 enumerated addresses. Moolah's impl
   is confirmed unchanged (`0x9321587e`). Whether the new repos sit behind *any* listed
   address is unverified; under Rules, unlisted code pays nothing.
3. **Olympus deployed-vs-repo parity** — the `OlympusPrice.v2.sol` delta (+1196 lines
   against 2023-era audits) is a *hypothesis* until the deployed impls are diffed. This
   exact gate killed Origin ARM, Marinade and GMTrade.
4. **Livepeer audit history** — resolve manually.

---

## Scanner corrections made during this triage

The audit and TVL columns were both reporting *unknown* as a confident *zero*. Four
chained defects, all now fixed and committed with regression tests:

1. `AUDIT_CONTEXT_PATTERN` gated on `\b(audit|audited|…)\b`, and **`\baudit\b` does not
   match `audits`**. A page *titled* "Audits" that never used the singular failed the gate
   and every firm name on it was discarded. Pareto's page uses the word 33 times, all
   plural, naming Sherlock 18 times. This suppressed recall across every protocol.
2. The docs scrape was gated on `bool(defillama_audit_count)`, so DefiLlama's wrong "2"
   counted as evidence and **skipped the pass that would have corrected it**.
3. The link-crawl was **depth-1**; Pareto's reports sit two hops down
   (`docs.pareto.credit` → `/developers/security` → `/developers/security/audits`).
4. Candidate URLs were built from the **display-name slug**, so "Pareto Credit" probed
   `pareto.com/...` while the real `docs.pareto.credit` landed at index 24 — with callers
   passing `max_attempts=4`.

Plus: `audit_record_resolved` and `tvl_resolved` now distinguish "checked, none found"
from "could not check" (rendered `—` vs `?`, scored neutral rather than extreme), and
`enrich/onchain_tvl.py` measures TVL directly from in-scope contracts when DefiLlama has
no figure — validated at $181.45M for Spark sUSDC, $225.4M for Pareto's five vaults.

A follow-up fix tightened `AUDIT_FIRM_PHRASES`: the firm 0xMacro was matched as bare
`\bmacro\b`, so once the plural gate worked, any docs page mentioning "audits" and
"macro" would have reported a **fabricated** audit — worse than a missed one, since it
silently removes a candidate.

---

## Provenance

Impl slots read live via `cast storage <proxy> 0x360894…382bbc` against
`ethereum-rpc.publicnode.com`, `arbitrum-one-rpc.publicnode.com` and
`bsc-rpc.publicnode.com`. Creation dates and contract names via Etherscan V2
`getcontractcreation` + `getsourcecode`. TVL via `getContractValue()` / `totalAssets()`
and `api.llama.fi`. Commit deltas via the GitHub API. BSC creation dates are unavailable
on the free Etherscan tier.

> `llamarpc.com` returned HTTP 521 during this session and produced empty `cast code`
> output — indistinguishable from "contract not deployed". Always sanity-check an RPC
> against a known-live address before concluding a contract does not exist.
