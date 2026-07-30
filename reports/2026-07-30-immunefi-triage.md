# Immunefi Bounty Triage — 2026-07-30

**Method**: manual gate-check of the live Immunefi catalogue (`immunefi.com/public-api/bounties.json`), not the `immunefi-scan` priority formula.
**Universe**: 248 programs → 165 active smart-contract → 76 no-KYC → **29 no-KYC ≥ $250k**.
**Gate**: `fresh post-audit delta ∩ in-scope ∩ deployed ∩ payout-structure`.

> **Why this file exists separately from `2026-07-30-immunefi-scan.md`**: the scanner's own run
> ranked **0** candidates at `--min-bounty 250000` (30 enriched → 0 above the 5.0 cutoff). That is
> not a bug — the priority formula weights `audit_gap 0.30 + freshness 0.20`, which structurally
> excludes every high-bounty program (all mature and multi-audited). The scanner ranks
> *valuable / under-audited*; bounty hunting needs *fresh ∩ in-scope ∩ deployed*. This file holds
> the manual triage; the auto-generated scan file will be overwritten by the next run.

---

## Ranked result

| Rank | Program | Max | Crit floor | KYC | Scope model | Verdict | Record |
|------|---------|-----|-----------|-----|-------------|---------|--------|
| 1 | Olympus | $3.33M | — (`up_to`, 10%) | no | 71 addrs, no POI | **LEAD — unexplored, large post-audit oracle delta** | [→](./2026-07-30-immunefi-triage/candidates/01-olympus.md) |
| 2 | Lista DAO | $1.0M | **$100k** | no | 57 addrs, Primacy of **Rules** | **LEAD — best payout floor; scope question open** | [→](./2026-07-30-immunefi-triage/candidates/02-listadao.md) |
| 3 | Origin Protocol | $1.0M | — (`up_to`, 10%) | no | 27 assets + **POI** | Fresh unaudited deployed code, payout capped ~$10–66k | [→](./2026-07-30-immunefi-triage/candidates/03-originprotocol.md) |
| — | SparkLend | $5.0M | $50k | no | 355 assets + POI | **NO-GO** (3rd rejection) — deployed == audited | — |
| — | Beanstalk | $1.1M | $100k | no | 20 addrs | **NO-GO** — repo stale since 2026-05-13 |— |

---

## New ranking axis: payout *structure*, not headline bounty

The live `rewards[]` array distinguishes two critical models. This flips the ordering versus
`maxBounty` and is worth computing **before** spending gate-check effort:

- `rewardModel: "range"` + `minReward` → a **guaranteed critical floor**
- `rewardModel: "up_to"` + `tenPercentEconomicRule: true` → **10% of funds-at-risk, no floor**

A $1M `up_to`/10% program sitting on a $100k vault pays ~$10k. A $1M `range`/min-$100k program pays
$100k minimum for the same finding.

| Floor | Programs |
|-------|----------|
| **$100k** | Beanstalk, **Lista**, Stader, mETH |
| **$50k** | SparkLend (on a $5M cap), Lido, Gnosis Chain, CoW, Aevo |
| **$25k** | Flux, Instadapp, Nucleus |
| *none* (`up_to` + 10%) | Origin, Olympus, Benqi, Ankr, Orca, reffinance |

---

## Gate detail

### SparkLend — NO-GO (3rd rejection, close this lead permanently)

Best headline economics in the entire catalogue ($5M, POI, $50k floor, no-KYC) and dead on code:

- In-scope repo `sparkdotfi/spark-vaults-v2` is **3 source files** (`SparkVault.sol`,
  `ISparkVault.sol`, `Deploy.s.sol`) carrying **4 audit PDFs** — `v100-cantina`,
  `v100-chainsecurity`, `v101-cantina`, `v101-chainsecurity`.
- Repo last pushed **2026-06-24 — before** the 2026-07-13/15 multichain scope-add ⇒ **deployed ==
  audited**, zero post-audit delta.
- Mainnet SUSDC impl `0xf943Cb8D` (`UsdcVault`) created **2025-03-03** (17 months old), reached via
  proxy `0xBc65ad17` EIP-1967 slot.
- `spark-alm-controller` carries 10 audit PDFs; `spark-psm` 3 and frozen since 2025-06.

**Lesson confirmed 3×** (2026-07-08, 07-20, 07-30): a Spark/Sky scope-add is the *most*-audited
code, never the least. Stop re-triaging Spark on scope-recency.

### Beanstalk — NO-GO

`BeanstalkFarms/Beanstalk` last pushed 2026-05-13 (~2.5 months). No fresh delta despite a $100k
critical floor.

### Origin — real fresh code, weak economics

Your banked impl-slot tripwire is **still unfired**: LidoARM `0x85b78aca` impl is *still*
`0x850da2e2` (unchanged since 2026-05-29, two months). But the program moved elsewhere — see the
candidate record. Killed by `up_to` + 10% economics and a yAudit known-issue minefield, **not** by
freshness.

---

## Open items (not yet resolved — do these before any audit spend)

1. **Olympus deployed-vs-repo parity.** The large `OlympusPrice.v2.sol` delta is a *hypothesis*
   until the deployed impls are diffed. This exact gate killed Origin, Marinade and GMTrade in
   prior sessions.
2. **Lista scope membership.** `lista-v2` / `lista-v3` / `lista-new-contracts` are actively pushed,
   but Lista is **Primacy of Rules** with 57 enumerated addresses. Moolah's impl is confirmed
   unchanged (`0x9321587e`); whether the new repos sit behind *any* listed address is unverified.
   Under Rules they pay only if listed.

## Provenance of the on-chain claims

All impl slots read live via `cast storage <proxy> 0x360894…382bbc` against
`https://ethereum-rpc.publicnode.com` / `https://bsc-rpc.publicnode.com`; creation dates and
contract names via Etherscan V2 `getcontractcreation` + `getsourcecode` (chainid 1). BSC creation
dates unavailable on the free API tier. TVL via `api.llama.fi/protocol/<slug>` and direct
`totalAssets()` calls.

> **Note**: `llamarpc.com` returned HTTP 521 during this run and silently produced empty `cast code`
> output — which reads identically to "contract not deployed". Always sanity-check an RPC with a
> known-live address before concluding a contract does not exist.
