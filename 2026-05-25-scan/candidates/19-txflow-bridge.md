---
target_name: txflow-bridge
display_name: TxFlow Bridge
protocol_type: Bridge on arbitrum
languages:
- solidity
chains:
- arbitrum
inferred_platform: private
inferred_mode: private
audit_density_score: 2
audit_sources_found:
- source: defillama
  url: null
  title: DefiLlama audit (no link)
  published_at: null
- source: defillama
  url: null
  title: DefiLlama audit (no link)
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- Brand-new contract (33d old) — check initialization racing, first-caller bootstrap
  invariants
- Real money at stake ($3,723,904 TVL) — favor impact-driven finding scoping
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 3723904.3448846065
first_seen: '2026-04-22'
age_days: 33
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: arbitrum:defillama:txflow-bridge
priority_score: 6.33
why_interesting: Bridge on arbitrum • $3,723,904 TVL • 33d old • audit_density=2
scan_date: '2026-05-25'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 2
defillama_audit_note: null
---

# TxFlow Bridge

> Bridge on arbitrum • $3,723,904 TVL • 33d old • audit_density=2

## Summary

- **Chain**: arbitrum
- **Primary contract**: `arbitrum:defillama:txflow-bridge`
- **TVL**: $3.7M (3,723,904)
- **Age**: 1mo (first seen 2026-04-22)
- **Languages**: solidity

## Audit history

- **Audit density score**: 2 (already audited)
- **DefiLlama audit count**: 2 (from /protocol/txflow-bridge detail)
- Sources found:
  - `defillama` (1pt): DefiLlama audit (no link)
  - `defillama` (1pt): DefiLlama audit (no link)

## Priority breakdown

- **Composite**: 6.33 / 10
  - tvl: 7.8 × 0.25
  - freshness: 9.1 × 0.20
  - audit_gap: 6.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Brand-new contract (33d old) — check initialization racing, first-caller bootstrap invariants
- Real money at stake ($3,723,904 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on txflow-bridge at ~/audit/2026-05-25-txflow-bridge/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
