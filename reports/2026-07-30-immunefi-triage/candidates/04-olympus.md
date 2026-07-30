---
target_name: olympus
display_name: Olympus DAO
protocol_type: DAO / reserve-backed token on ethereum (71 in-scope contracts, 4 chains)
languages:
- solidity
chains:
- ethereum
- arbitrum
- base
- berachain
inferred_platform: immunefi
inferred_mode: bug-bounty
audit_density_score: 3
audit_sources_found:
- in-repo audit/2023-06_price-v2
- in-repo audit/2023-11_price-v2
- in-repo audit/2024-10_loan-consolidator
under_audited: false
edge_match_keywords:
- oracle
- bridge
focus_areas_suggested:
- 'PRICE v2 oracle module is the primary surface: in-repo audits are 2023-06 and 2023-11,
  but src/modules/PRICE/OlympusPrice.v2.sol shows +1196 lines of churn since 2026-04
  along with its Pyth / Chainlink / Balancer / UniswapV3 feed submodules — a large
  post-audit delta on price-derivation code'
- 'Cross-chain surface: CCIP rate-limit (#286, 2026-07-15) and LayerZero bridge upgrade
  (2026-07-20) against in-scope CrossChainBridge deployed on Arbitrum / Base / Berachain'
- 'Mint authority: MINTR module is in scope on all four chains; V1Migrator work through
  2026-06-30 includes "set migration mint approval cap" — trace the mint-approval path
  end to end'
- Reward model is up_to + tenPercentEconomicRule (10% of funds at risk); with ~$266M
  staking TVL the $3.33M cap is reachable, unlike low-TVL 10%-rule programs
bounty_program: immunefi
bounty_url: https://immunefi.com/bug-bounty/olympus
bounty_max_payout_usd: 3333333
bounty_critical_model: up_to
bounty_critical_min_usd: null
bounty_ten_percent_rule: true
bounty_kyc: false
scope_model: enumerated-addresses (no Primacy of Impact)
tvl_usd: 266190042.7
first_seen: null
age_days: null
unique_users_30d: null
github_repo: https://github.com/OlympusDAO/olympus-v3
loc_estimate: null
docs_url: null
onchain_address: ethereum:0x5131654eFCd63f7b797e00118792e0d0dD90B8B0
primary_contract: ethereum:0x5131654eFCd63f7b797e00118792e0d0dD90B8B0
priority_score: null
why_interesting: 'Only high-bounty no-KYC program never gate-checked in any prior session
  • $3.33M max • ~$266M staking TVL • large post-2023-audit delta on the PRICE v2 oracle
  module + CCIP/LayerZero bridge work + in-scope MINTR mint authority'
scan_date: '2026-07-30'
is_verified: true
contract_name: V1Migrator
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: null
defillama_audit_note: null
gate_deployed: PARTIAL — V1Migrator verified live, deployed-vs-repo parity NOT yet diffed
gate_in_scope: PASS — 71 enumerated addresses, Primacy of Rules
gate_fresh_delta: PASS — olympus-v3 pushed 2026-07-30, 100 commits to src/ since 2026-04-01
gate_payout: WEAK MODEL, STRONG BASE — up_to + 10% rule, but on ~$266M TVL
---

# Olympus DAO

> The one genuinely unexplored high-bounty program. $3.33M, no-KYC, ~$266M staking TVL, and a large
> post-audit delta on oracle + cross-chain + mint-authority code.

## Summary

- **Chains**: ethereum, arbitrum, base, berachain
- **Reference contract**: `ethereum:0x5131654eFCd63f7b797e00118792e0d0dD90B8B0` (`V1Migrator`,
  verified, non-proxy, deployed **2026-02-12**, added to scope 2026-03-02)
- **TVL**: ~$266.2M (DefiLlama `Ethereum-staking`)
- **Repo**: `OlympusDAO/olympus-v3` — pushed **2026-07-30** (today)

## Bounty program

- **Platform**: immunefi — https://immunefi.com/bug-bounty/olympus
- **Max payout**: $3,333,333
- **Critical model**: `up_to` + `tenPercentEconomicRule: true` → 10% of funds at risk, **no floor**
- **KYC**: no
- **Scope**: 71 enumerated smart-contract addresses, **no Primacy of Impact** → Primacy of Rules,
  only listed addresses pay

## Why this ranks first

Prior sessions exhaustively gate-checked LayerZero, Chainlink, Compound, Aave, Axelar, Lido, Sky,
Balancer, Pyth, Spark, GMX, Raydium, DeFi Saver, Marinade, Parallel and others. **Olympus was never
checked.** It is the last unexamined program in the no-KYC ≥$250k pool with both real TVL and an
active repo.

## Measured delta

100 commits touched `src/` since 2026-04-01. Churn concentrated on the price stack:

| Lines changed | File |
|---------------|------|
| 1196 | `src/modules/PRICE/OlympusPrice.v2.sol` |
| 887 | `src/modules/PRICE/submodules/feeds/BalancerPoolTokenPrice.sol` |
| — | Pyth / Chainlink / UniswapV3 feed submodules (heavy test churn alongside) |

In-repo audit artifacts are `audit/2023-06_price-v2`, `audit/2023-11_price-v2` and
`audit/2024-10_loan-consolidator` — so the **PRICE v2 module was audited in 2023 and is being
rewritten in 2026**. That is the post-audit-delta shape the method hunts.

Recent themes visible in the log: `feat(price): add OHM WETH 100 bps feed` (07-09),
`fix(price): adjust OHM deployment bounds` (07-13), `Merge PR #286 ccip-rate-limit` (07-15),
`lz-bridge-upgrade` (07-20), `feat(v1-migrator): set migration mint approval cap` (06-30).

## Gate status

| Gate | Status |
|------|--------|
| Fresh post-audit delta | **PASS** — 2023 audit vs 2026 oracle rewrite |
| In-scope | **PASS** — MINTR, CrossChainBridge, Kernel, RolesAdmin, Treasury Custodian, V1Migrator all listed |
| Deployed | **PARTIAL** — V1Migrator confirmed verified + live; the PRICE v2 impls have **not** been diffed against repo HEAD |
| Payout | Weak *model*, strong *base* — 10% of $266M is not the $10k trap that low-TVL 10% programs are |

## Next step (required before audit spend)

Run the deployed-vs-repo parity gate on the PRICE v2 module and the CrossChainBridge deployments.
This exact gate killed Origin ARM, Marinade and GMTrade in prior sessions — a large repo delta means
nothing until it is proven live at an in-scope address.

## Vault handoff (Phase 2a)

> `new audit on olympus at ~/audit/2026-07-30-olympus/`
