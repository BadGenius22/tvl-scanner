---
target_name: yearnfinance
display_name: Yearn Finance (stYFI)
protocol_type: Governance / staking / revenue distribution on ethereum
languages:
- vyper
chains:
- ethereum
inferred_platform: immunefi
inferred_mode: bug-bounty
audit_density_score: 26
audit_sources_found:
- 'in-repo yearn-vaults-v3/audits: yAcademy 06-2023, Statemind, ChainSecurity'
- 'in-repo tokenized-strategy/audits: ChainSecurity'
- 'NOTE: none of these cover stYFI — yearn/stYFI has ZERO audit paths'
under_audited: false
audit_record_resolved: true
edge_match_keywords:
- vault
- staking
focus_areas_suggested:
- 'PRIMARY: the 12 stYFI contracts were added to scope 2026-07-01 and deployed
  2026-06-02/06-04, and NO audit for them could be found — Immunefi''s audits array is
  empty and yearn/stYFI has 0 audit paths across 45 Vyper sources. This breaks the
  usual "recent scope-add = freshly AUDITED code" pattern (Sky/Balancer/Pyth/Spark).'
- 'Surface is a new governance + revenue product: LiquidLockerDepositor,
  LiquidLockerRedemption, LiquidLockerMiddleware, RevenueRecipient, BonusDistributor,
  FundingDistributor, SnapshotMeasure, DelegatedStakedYFI, RewardClaimer.'
- 'Two price oracles in scope (RevenuePriceOracle, BonusPriceOracle) — oracle
  manipulation is the most-exploited DeFi bug class; check staleness and source.'
- 'SnapshotMeasure + Election suggests vote-weight accounting; snapshot/measure timing
  against stake movement is a classic governance double-count surface.'
- 'Written in Vyper, not Solidity — different overflow/reentrancy defaults; verify the
  compiler version against known Vyper advisories before trusting language-level safety.'
- 'CLOSE FIRST: absence of an audits/ folder is NOT proof of no audit. Yearn may publish
  elsewhere. Resolve before spending effort.'
bounty_program: immunefi
bounty_url: https://immunefi.com/bug-bounty/yearnfinance
bounty_max_payout_usd: 200000
bounty_critical_model: range
bounty_critical_min_usd: 20000
bounty_ten_percent_rule: false
bounty_kyc: false
scope_model: enumerated addresses (47 total, no Primacy of Impact)
tvl_usd: 180500000
tvl_resolved: true
first_seen: '2025-12-02'
age_days: null
unique_users_30d: null
github_repo: https://github.com/yearn/stYFI
loc_estimate: null
docs_url: null
onchain_address: ethereum:0xe16608758c11322d407745927d2D033f1BFB206C
primary_contract: ethereum:0xe16608758c11322d407745927d2D033f1BFB206C
priority_score: null
why_interesting: 'Best payout structure of any lead — $200k max with a $20k GUARANTEED
  floor and NO 10% dilution, no KYC — against a 12-contract governance/revenue product
  deployed 2026-06-02 for which no audit can be found'
scan_date: '2026-07-30'
is_verified: true
contract_name: YBC Membership Election
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 2
defillama_audit_note: null
gate_fresh_delta: PASS — deployed 2026-06-02/04, no audit found for any of it
gate_deployed: PASS — all four sampled contracts verified live on mainnet
gate_in_scope: PASS — 12 stYFI contracts explicitly listed 2026-07-01
gate_tvl: PARTIAL — Yearn-wide TVL is $180.5M; stYFI's own share NOT measured
gate_payout: STRONG — $20k floor, $200k max, no 10% dilution
---

# Yearn Finance — stYFI

> Best payout structure of any lead: **$200k max, $20k guaranteed floor, no 10%
> dilution, no KYC** — on a product that appears to be genuinely unaudited.

## Bounty program

- **Platform**: immunefi — https://immunefi.com/bug-bounty/yearnfinance
- **Critical**: `range`, max **$200,000**, **minReward $20,000**
- **10% economic rule**: **false** — payout is not diluted by funds-at-risk arguments
- **KYC**: no
- **Scope**: 47 enumerated addresses, **no Primacy of Impact** → Primacy of Rules

## Why this one breaks the usual pattern

Prior sessions established that a recent Immunefi scope-add is usually the *most*-audited
code, not the least — Sky, Balancer, Pyth and Spark were all rejected on exactly that
basis. stYFI is the counter-example:

| Contract | Address | Deployed |
|----------|---------|----------|
| YBC Membership Election | `0xe1660875…` | **2026-06-02** |
| Staking Middleware | `0x24b267AA…` | **2026-06-02** |
| YBC Reward Distributor | `0x53100f89…` | **2026-06-02** |
| Team Registry | `0x9da431b8…` | **2026-06-04** |

Added to scope **2026-07-01**, a month after deployment. All verified on-chain.

**No audit found**: Immunefi's `audits` array is empty, and `yearn/stYFI` (created
2025-12-02, pushed 2026-07-14) has **0 audit paths** across 45 Vyper sources. The audit
PDFs that do exist in the Yearn org (`yearn-vaults-v3/audits`, `tokenized-strategy/audits`)
are from **06-2023** and cover the vault core, not this product. `yearn/governance-apps`
audit hits are documentation files, not security reports.

## The surface

`LiquidLockerDepositor`, `LiquidLockerRedemption`, `LiquidLockerMiddleware`,
`RevenueRecipient`, `RevenuePriceOracle`, `BonusDistributor`, `BonusPriceOracle`,
`FundingDistributor`, `SnapshotMeasure`, `DelegatedStakedYFI`,
`DelegatedStakingRewardDistributor`, `RewardClaimer`.

## Open questions

1. **Absence of an `audits/` folder is not proof of no audit.** Yearn may publish
   elsewhere. Close this before spending real effort — it is the single assumption the
   whole thesis rests on.
2. **stYFI's own TVL is unmeasured.** The $180.5M is Yearn-wide. Payout does not depend
   on it (no 10% rule), but exploitability does.

## Dead deltas elsewhere in Yearn's scope

- `vault-periphery` — 0 commits to `contracts/` since 2026-01-01. No audits folder, but frozen.
- `yearn-vaults-v3` — exactly one commit, `build: v3.1.0` (2026-06-19, `VaultV3.vy` +185)
  against 06-2023 audits. Notable, but the most battle-tested vault core in DeFi.

## Vault handoff (Phase 2a)

> `new audit on yearnfinance at ~/audit/2026-07-30-yearn-styfi/`
