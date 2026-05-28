---
target_name: set.wtf
display_name: set.wtf
protocol_type: Yield on ethereum
languages:
- solidity
chains:
- ethereum
inferred_platform: private
inferred_mode: private
audit_density_score: 0
audit_sources_found: []
under_audited: true
audited_by_me: '2026-05-28'
audit_outcome: 'CLEAN under filter (0 Critical/High/Med/Low, 5 Informational). 519 LOC single contract (LiquidityPool.sol). Fully custodial — admin-processed withdrawals via onlyOwner, signature-authorized rewards via secondOwner. 14 external functions; only 3 take non-owner callers (deposit, requestWithdrawal, requestRewardClaim — all correctly gated). Signature scheme audited end-to-end (10 hunt + 4 extra checks, all REFUTED): OZ v4.x ECDSA enforces low-s, abi.encodePacked uses only fixed-width types, nonce monotonicity correct, batch method-string differentiation via abi.encode is collision-free. CRITICAL FINDING: real on-chain TVL is $13,347.76 USDT — only 2.0% of DefiLlama nominal $675,940. Admin has swept ~$662K (98%) to off-chain wallets via adminWithdraw. DefiLlama TVL is event-derived and excludes admin sweeps — misleading. By design, not a code bug. Architecture is structurally identical to AnubisDAO/OlympusDAO copycat pattern; "20% APY" is admin-signed off-chain with zero on-chain enforcement.'
real_onchain_tvl_usd: 13348
real_onchain_tvl_source: 'RPC eth_call USDT.balanceOf(0x2506CB864df6336d93A87C4af2b644fd61cF4d81) = 13,347.76 USDT (raw 13347764679). DefiLlama nominal TVL is $675,940 derived from sum(user Deposited events) - sum(user WithdrawalProcessed events), explicitly EXCLUDING AdminDeposited/AdminWithdrawn flows per adapter methodology. Admin has swept ~$662,593 (98%) of nominal TVL to off-chain wallets. Real on-chain redeemable liquidity is 2.0% of advertised TVL.'
contract_name: 'LiquidityPool'
compiler_version: 'v0.8.19'
is_verified: true
edge_match_keywords: []
focus_areas_suggested:
- No prior audits found in any source — start with standard sanity pass before specialized
  depth
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 676095.680426941
first_seen: '2025-09-25'
age_days: 243
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: ethereum:defillama:set.wtf
priority_score: 5.46
why_interesting: Yield on ethereum • $676,095 TVL • 243d old • no prior audits found
scan_date: '2026-05-26'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 0
defillama_audit_note: null
---

# set.wtf

> Yield on ethereum • $676,095 TVL • 243d old • no prior audits found

## Summary

- **Chain**: ethereum
- **Primary contract**: `ethereum:defillama:set.wtf`
- **TVL**: $676K (676,095)
- **Age**: 8mo (first seen 2025-09-25)
- **Languages**: solidity

## Audit history

- **Audit density score**: 0 (under-audited)
- **DefiLlama audit count**: 0 (from /protocol/set.wtf detail)
- **No audits found** in any checked source.

## Priority breakdown

- **Composite**: 5.46 / 10
  - tvl: 4.2 × 0.25
  - freshness: 3.3 × 0.20
  - audit_gap: 10.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- No prior audits found in any source — start with standard sanity pass before specialized depth

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on set.wtf at ~/audit/2026-05-26-set.wtf/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
