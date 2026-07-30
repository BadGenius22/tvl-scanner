---
target_name: alchemix-1
display_name: Alchemix V3
protocol_type: CDP / self-repaying loans on ethereum + arbitrum + optimism
languages:
- solidity
chains:
- ethereum
- arbitrum
- optimism
inferred_platform: immunefi
inferred_mode: bug-bounty
audit_density_score: 11
audit_sources_found:
- yAudit 2026-03-15 (latest, per Immunefi)
- Nethermind 2026-02-02
- Aleph V 2025-12-15
- Spearbit + Cantina 2025-05-15
under_audited: false
audit_record_resolved: true
edge_match_keywords:
- vault
- leverage
focus_areas_suggested:
- 'PRIMARY: 131 commits landed in src/ after the last listed audit (yAudit 2026-03-15)
  and the live implementation deployed 2026-07-25 CONTAINS them. Verified in the
  deployed verified source: performanceFee (7 hits) and forceDeallocate (4 hits).'
- 'src/strategies/TokeAutoStrategy.sol (+269) is the largest new production file.
  Note src/test/poc/TokeAutoForceDeallocateUpdatedRun.t.sol (+888) — the team was
  itself chasing something around forceDeallocate; read that PoC before starting.'
- 'Commit "adjusted nav based withdrawal" (2026-06-29) changed withdrawal accounting
  in the strategy/vault-v2 layer (the `nav` marker is absent from AlchemistV3 itself).'
- 'AlchemistV3PerformanceFee (+466 test churn) implies fee-accounting changes; fee
  math on a CDP with self-repaying loans is a classic rounding/accrual surface.'
- 'Both mainnet alchemists share ONE implementation (0xd5f26c90), so a bug in it hits
  the alUSD and alETH markets simultaneously — impact scales across both.'
- 'Scope is the repo DIRECTORY github.com/alchemix-finance/v3/tree/master/src, so all
  of src/ counts, new strategies included. Primacy of Impact applies via alchemix.fi.'
bounty_program: immunefi
bounty_url: https://immunefi.com/bug-bounty/alchemix
bounty_max_payout_usd: 150000
bounty_critical_model: range
bounty_critical_min_usd: 20000
bounty_ten_percent_rule: true
bounty_kyc: false
scope_model: repo-directory asset + explicit Primacy of Impact
tvl_usd: 30500000
tvl_resolved: true
first_seen: '2026-02-20'
age_days: null
unique_users_30d: null
github_repo: https://github.com/alchemix-finance/v3
loc_estimate: null
docs_url: null
onchain_address: ethereum:0xeb83112d925268bede86654c13d423a987587e3e
primary_contract: ethereum:0xeb83112d925268bede86654c13d423a987587e3e
priority_score: null
why_interesting: 'Only target in many sessions to clear EVERY gate — fresh (131 commits
  since the last audit), DEPLOYED (live impl 2026-07-25, five days before scan, and
  membership-tested to contain the delta), IN SCOPE (repo-directory asset + POI),
  with real debt outstanding and a $20k guaranteed critical floor, no KYC'
scan_date: '2026-07-30'
is_verified: true
contract_name: AlchemistV3
is_proxy: true
proxy_impl_address: '0xd5f26c90ead033554bf36227d0bbe993f6f76570'
compiler_version: v0.8.28+commit.7893614a
defillama_audit_count: 5
defillama_audit_note: null
gate_fresh_delta: PASS — 131 commits to src/ since yAudit 2026-03-15
gate_deployed: PASS — live impl deployed 2026-07-25, contains the delta (verified in source)
gate_in_scope: PASS — repo-directory asset covers all of src/, plus POI
gate_tvl: PASS — ~4.56M alUSD + ~6,626 alETH debt outstanding on mainnet
gate_payout: PARTIAL — $20k floor is real, but 10% economic rule caps realised payout
---

# Alchemix V3

> The strongest target found. Clears fresh ∩ deployed ∩ in-scope ∩ TVL — the exact
> conjunction that killed Origin ARM, Marinade, GMTrade and 1inch Aqua in prior sessions.

## Bounty program

- **Platform**: immunefi — https://immunefi.com/bug-bounty/alchemix
- **Critical**: `range`, max **$150,000**, **minReward $20,000** (a real floor)
- **10% economic rule**: **true** — realised payout is 10% of funds at risk, floored at $20k
- **KYC**: no
- **Scope**: only two assets — `https://alchemix.fi/` (**Primacy of Impact**) and
  `https://github.com/alchemix-finance/v3/tree/master/src` (**directory-level**, added
  2026-04-06). All of `src/` is therefore in scope, new strategies included.

## Verified on-chain state (2026-07-30)

| Contract | Proxy | Live impl | Impl deployed |
|----------|-------|-----------|---------------|
| AlchemistV3 (alUSD) | `0xeb83112d…` | `0xd5f26c90…` | **2026-07-25** |
| AlchemistV3 (alETH) | `0xfa995b6a…` | `0xd5f26c90…` (shared) | **2026-07-25** |
| AlchemistV3 (Arbitrum ×2) | `0x930750a3…` / `0xded3a046…` | `0x40ba0d16…` | **2026-07-25** |

Debt outstanding: **~4,558,527 alUSD** (`totalSyntheticsIssued` 4.634e24) and
**~6,626 alETH** on mainnet, plus ~15,649 + ~59.5 on Arbitrum.

The April deployment was commit `22dade8` (2026-04-14, impls `0xf700c7e4` / `0x763f5d56`).
Those proxies were **upgraded past it** — the live implementations are five days old.

## Why it clears the deployed gate

The delta is not repo-only. Membership-testing the deployed *verified* source of
`0xd5f26c90`:

| Marker | Hits | Maps to |
|--------|------|---------|
| `performanceFee` | 7 | `AlchemistV3PerformanceFee` (+466 test churn) |
| `forceDeallocate` | 4 | #06-30 "emit event on security-relevant forcedeallocate change" |
| `earmark` | 310 | core redemption accounting |

## Measured delta since the last audit

131 commits to `src/` since **yAudit 2026-03-15**. Production churn:
`src/strategies/TokeAutoStrategy.sol` (+269), a new FluidLite USDC strategy
(2026-07-02, test + deploy script only — no `src/strategies/FluidLiteUSDCStrategy.sol`
exists), `EtherfiEETHStrategy`, plus "adjusted nav based withdrawal" (06-29).

**Trap avoided**: the repo's own audit PDFs (`lib/vault-v2/audits/`, latest 2025-09-15)
belong to a **dependency**, not to V3. The real last-audit date comes from Immunefi's list.

## Caveats — read before committing time

1. **Five prior audits** (yAudit, Nethermind, Aleph V, Spearbit+Cantina) and a prior
   session tagged Alchemix V3 "comp-saturated". This is a well-reviewed codebase.
2. **Unknown**: whether the 2026-07-25 implementation received an audit not listed on
   Immunefi. Unknowable from outside; no *listed* audit covers it.
3. **10% economic rule** caps realised payout at 10% of funds at risk. The $20k floor
   holds regardless.

Hunter saturation on five-day-old code is low, which is the core of the thesis.

## Vault handoff (Phase 2a)

> `new audit on alchemix-1 at ~/audit/2026-07-30-alchemix/`
