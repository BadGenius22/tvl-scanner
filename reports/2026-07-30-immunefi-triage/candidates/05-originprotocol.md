---
target_name: originprotocol
display_name: Origin Protocol (ARM)
protocol_type: Stablecoin / LST automated redemption manager on ethereum (27 in-scope assets)
languages:
- solidity
- javascript
chains:
- ethereum
- base
inferred_platform: immunefi
inferred_mode: bug-bounty
audit_density_score: 2
audit_sources_found:
- yAudit (inferred from commit "[yAudit-03] Fix swap fee accrual on realized gain (#306)")
- docs.originprotocol.com/security-and-risk/audits (published set, excluded as known issues)
under_audited: true
edge_match_keywords:
- vault
- arm
focus_areas_suggested:
- 'AbstractARM.sol is the shared core inherited by every ARM: 313 lines changed across
  12 commits since 2026-06-19 (#282 6-or-18 decimals, #288 insolvency guard, #306 yAudit
  swap-fee accrual, #307 minimum-liquidity from decimals, #308 deposits at exact solvency,
  #311 deposit block at asset floor, #320 EtherFi withdrawal gate, #324 WETH Morpho market)'
- 'DEPLOYED-CODE TRAP: none of that delta is in the two highest-TVL ARMs. Ethena ARM
  impl is from 2026-06-19 and LidoARM impl from 2026-05-29 — both predate the changes.
  Only MultiAssetARM / "USDC ARM" (impl deployed 2026-07-22) runs the new AbstractARM.'
- 'KNOWN-ISSUE MINEFIELD: rewardsBody excludes "all issues found in their past audits".
  Commit #306 is explicitly a yAudit finding, so that bug class is already excluded —
  same pattern that killed the Parallel V3 audit.'
- 'Payout is up_to + tenPercentEconomicRule (10% of funds at risk): Ethena ARM ~$660k
  → ~$66k; USDC ARM ~$100k → ~$10k. Freshness is real, economics are not.'
bounty_program: immunefi
bounty_url: https://immunefi.com/bug-bounty/originprotocol
bounty_max_payout_usd: 1000000
bounty_critical_model: up_to
bounty_critical_min_usd: null
bounty_ten_percent_rule: true
bounty_kyc: false
scope_model: enumerated-addresses + explicit Primacy of Impact entry
tvl_usd: 37841981.0
first_seen: null
age_days: null
unique_users_30d: null
github_repo: https://github.com/OriginProtocol/arm-oeth
loc_estimate: null
docs_url: https://docs.originprotocol.com/security-and-risk/audits
onchain_address: ethereum:0xCEDa2d856238aA0D12f6329de20B9115f07C366d
primary_contract: ethereum:0xCEDa2d856238aA0D12f6329de20B9115f07C366d
priority_score: null
why_interesting: 'Genuinely fresh unaudited code that IS deployed and in scope (repo has
  no audits/ folder) — but payout is capped at ~$10-66k by the 10% economic rule, and
  the freshest AbstractARM changes are absent from the two highest-TVL ARMs'
scan_date: '2026-07-30'
is_verified: true
contract_name: EthenaARM
is_proxy: true
proxy_impl_address: '0xebb2b66759b593ea50eb8c306e2e13464cdb99fe'
compiler_version: v0.8.23+commit.f704f362
defillama_audit_count: null
defillama_audit_note: null
gate_deployed: PASS — Ethena ARM, USDC ARM and LidoARM all live and verified
gate_in_scope: PASS — Ethena ARM listed 2026-07-23; USDC ARM covered by the POI entry
gate_fresh_delta: PASS — repo has NO audits/ folder, 313 lines of AbstractARM churn
gate_payout: FAIL — up_to + 10% rule on $660k/$100k vaults → ~$66k/$10k ceiling
---

# Origin Protocol (ARM)

> The freshest deployed unaudited code found in this scan — and the clearest example of why
> **payout structure gates a target as hard as code freshness does**.

## Summary

- **Chain**: ethereum (plus Base assets)
- **Primary contract**: `ethereum:0xCEDa2d856238aA0D12f6329de20B9115f07C366d` (`EthenaARM` proxy →
  impl `0xebb2b667…`, deployed **2026-06-19**, added to scope **2026-07-23**)
- **Repo**: `OriginProtocol/arm-oeth` — pushed 2026-07-30, **no `audits/` folder**

## Bounty program

- **Platform**: immunefi — https://immunefi.com/bug-bounty/originprotocol
- **Max payout**: $1,000,000
- **Critical model**: `up_to` + `tenPercentEconomicRule: true` → 10% of funds at risk
- **KYC**: no
- **Scope**: 27 enumerated assets **plus an explicit Primacy of Impact entry** — so unlisted Origin
  contracts still pay if the impact is live

## Verified on-chain state (2026-07-30)

| Contract | Proxy | Impl | Impl deployed | Live TVL |
|----------|-------|------|---------------|----------|
| **Ethena ARM** (listed 07-23) | `0xCEDa2d85…` | `0xebb2b667…` | 2026-06-19 | ~660,725 units (`totalAssets` 6.607e23) |
| **LidoARM** (listed 2024-11) | `0x85B78AcA…` | `0x850da2e2…` | 2026-05-29 | ~3,126 WETH |
| **USDC ARM** (`MultiAssetARM`, POI) | `0x9e3a7026…` | `0xef40f354…` | **2026-07-22** | ~100,000 USDC |
| Ethena ARM Aave Strategy | `0x0DC20109…` | `0x7396f87f…` | 2025-11-27 | — |

## The banked tripwire did not fire — but the program moved

The standing watch was "LidoARM impl slot flips away from `0x850da2e2`". **It has not** — unchanged
for two months. That specific trigger should stop being re-checked weekly.

What actually happened instead: Origin shipped **new ARM products**. `MultiAssetARM` impl
`0xef40f354` went live on mainnet **2026-07-22** — the same day PRs #307 / #308 / #311 landed — and
`Ethena ARM` was added to the bounty scope on **2026-07-23**.

## Measured delta

12 commits / 313 changed lines in `src/contracts/AbstractARM.sol` since 2026-06-19:

| Date | PR |
|------|-----|
| 2026-07-28 | #324 Deploy WETH ARM Morpho market |
| 2026-07-27 | #320 EtherFi withdrawal request gate |
| 2026-07-22 | #311 Block deposits at the asset floor when live LPs exist |
| 2026-07-22 | #308 Allow deposits at exact solvency |
| 2026-07-22 | #307 Derive minimum liquidity from decimals |
| 2026-07-22 | #306 **[yAudit-03]** Fix swap fee accrual on realized gain |
| 2026-07-06 | #288 Protect against deposits to an insolvent ARM with accrued fees |
| 2026-07-06 | #282 Support 6 or 18 decimal liquidity and base assets |

## Why it is ranked third despite the best code freshness

1. **Economics.** `up_to` + 10% rule. Ethena ARM ~$660k → ~$66k ceiling. USDC ARM ~$100k → ~$10k.
   The $1M headline is unreachable at current ARM TVL.
2. **Known-issue minefield.** `rewardsBody` excludes "all issues found in their past audits", and
   #306 is explicitly a yAudit finding — that class is pre-excluded. Same shape that killed Parallel V3.
3. **The delta is not where the money is.** LidoARM holds the most value but runs 2026-05-29 code
   that predates every change above.

## Recommended handling

**WATCH, not audit.** Re-check when ARM TVL grows materially or when the LidoARM/Ethena impls are
upgraded to carry the new `AbstractARM` — at that point the same bug would pay against a much larger
funds-at-risk base.

## Vault handoff (Phase 2a)

> `new audit on originprotocol at ~/audit/2026-07-30-originprotocol/`
