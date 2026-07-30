---
target_name: listadao
display_name: Lista DAO
protocol_type: Lending / stablecoin / liquid staking on BSC (57 in-scope contracts)
languages:
- solidity
- javascript
chains:
- bsc
inferred_platform: immunefi
inferred_mode: bug-bounty
audit_density_score: 3
audit_sources_found:
- prior-session finding — Moolah/Lista Lending is the most-audited component
under_audited: false
edge_match_keywords:
- lending
- vault
focus_areas_suggested:
- 'RESOLVE FIRST: Lista is Primacy of RULES with 57 enumerated addresses. The org ships
  actively from lista-v2 (pushed 2026-07-16), lista-new-contracts (2026-07-27) and
  lista-v3 (2026-06-25), but it is UNVERIFIED whether any of that code sits behind
  a listed address. Under Rules, unlisted code pays nothing.'
- 'PublicLiquidator 0x882475d6 (impl 0xc73f5885) is in scope and is a permissionless
  fund-path contract — liquidation entry points are the highest-yield surface on a
  lending protocol'
- 'Moolah (Morpho-Blue fork) impl is UNCHANGED at 0x9321587e since the 2026-07-09 look
  — it is the freshest deploy but also the most-audited component; prefer the newer
  peripheral modules (credit-loan, broker, StableSwap, MoolahVault) per the prior session'
- Critical is a range model with a $100k guaranteed floor and no 10% dilution — the
  best payout structure found in the no-KYC pool
bounty_program: immunefi
bounty_url: https://immunefi.com/bug-bounty/listadao
bounty_max_payout_usd: 1000000
bounty_critical_model: range
bounty_critical_min_usd: 100000
bounty_ten_percent_rule: false
bounty_kyc: false
scope_model: enumerated-addresses (Primacy of RULES, no POI)
tvl_usd: 1099804895.6
first_seen: null
age_days: null
unique_users_30d: null
github_repo: https://github.com/lista-dao
loc_estimate: null
docs_url: null
onchain_address: bsc:0x8F73b65B4caAf64FBA2aF91cC5D4a2A1318E5D8C
primary_contract: bsc:0x8F73b65B4caAf64FBA2aF91cC5D4a2A1318E5D8C
priority_score: null
why_interesting: 'Best payout structure in the no-KYC pool — $100k GUARANTEED critical
  floor, $1M max, no 10% dilution • ~$1.1B BSC TVL • org shipping new code weekly •
  blocked on one unresolved scope-membership question'
scan_date: '2026-07-30'
is_verified: true
contract_name: Moolah
is_proxy: true
proxy_impl_address: '0x9321587ea0dc8247f8f03e8696c047b2713bb79a'
compiler_version: null
defillama_audit_count: null
defillama_audit_note: null
gate_deployed: PASS — Moolah + PublicLiquidator both live and verified on BSC
gate_in_scope: PASS for listed addrs / OPEN for the new lista-v2 & lista-v3 repos
gate_fresh_delta: OPEN — org repos active, but link to a listed address unverified
gate_payout: STRONG — range model, $100k floor, no 10% dilution
---

# Lista DAO

> The best payout structure in the entire no-KYC pool: **$100k guaranteed critical floor**, $1M max,
> no 10% dilution, on ~$1.1B of BSC TVL. Blocked on one unresolved scope question.

## Summary

- **Chain**: BSC
- **Primary contract**: `bsc:0x8F73b65B4caAf64FBA2aF91cC5D4a2A1318E5D8C` (`Moolah`, proxy →
  impl `0x9321587ea0dc8247f8f03e8696c047b2713bb79a`)
- **Also in scope**: `bsc:0x882475d622c687b079f149B69a15683FCbeCC6D9` (`PublicLiquidator`, proxy →
  impl `0xc73f588511086095cbbc1ba24260df5a2b3b0053`)
- **TVL**: ~$1.1B (DefiLlama, BSC)

## Bounty program

- **Platform**: immunefi — https://immunefi.com/bug-bounty/listadao
- **Max payout**: $1,000,000
- **Critical model**: `range`, **minReward $100,000** — a guaranteed floor
- **10% economic rule**: **false** — payout is not diluted by funds-at-risk arguments
- **KYC**: no
- **Scope**: 57 enumerated addresses, **no Primacy of Impact** → Primacy of Rules

## Why the payout structure matters

Most $1M programs (Origin, Olympus, Benqi, Ankr) use `up_to` + `tenPercentEconomicRule`, so the
realised payout is 10% of whatever funds a specific finding puts at risk. Lista pays a **$100k
minimum** for any accepted critical. For solo hunting that difference dominates the headline number.

## Verified on-chain state (2026-07-30)

| Contract | Proxy | Impl | Note |
|----------|-------|------|------|
| Moolah | `0x8F73b65B…` | `0x9321587e…` | **Unchanged** since the 2026-07-09 session |
| PublicLiquidator | `0x882475d6…` | `0xc73f5885…` | In scope, permissionless fund path |

BSC contract-creation dates are unavailable on the free Etherscan V2 tier, so impl deploy dates were
not established.

## The blocking question

`lista-dao` ships actively: `lista-token` (pushed 2026-07-29), `lista-new-contracts` (2026-07-27),
`lista-v2` (2026-07-16), `lista-v3` (2026-06-25). The `v2`/`v3` repos have 0 stars, which usually
indicates genuinely new code.

**But Lista is Primacy of Rules.** Unlisted code pays nothing regardless of impact. Before any audit
spend, confirm whether `lista-v2` / `lista-v3` / `lista-new-contracts` code sits behind any of the
57 enumerated addresses. If it does not, the fresh surface is worth $0 and the only payable surface
is the already-audited Moolah core.

## Prior-session context

Picked 2026-07-09 as the then-current target. Moolah (Morpho-Blue fork) was assessed as the freshest
deploy but the most-audited component; the audit-light surface was judged to be the newer peripheral
modules (credit-loan, broker, StableSwap, MoolahVault) plus the broader CDP. Nothing was audited to
completion, so this lead is **open, not exhausted**.

## Vault handoff (Phase 2a)

> `new audit on listadao at ~/audit/2026-07-30-listadao/`
