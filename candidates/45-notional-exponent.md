---
target_name: notional-exponent
display_name: Notional Exponent
protocol_type: Leveraged Farming on ethereum
languages:
- solidity
chains:
- ethereum
inferred_platform: private
inferred_mode: private
audit_density_score: 2
audit_sources_found:
- source: defillama
  url: https://docs.notional.finance/exponent/smart-contracts/security
  title: null
  published_at: null
- source: defillama
  url: null
  title: DefiLlama audit (no link)
  published_at: null
under_audited: false
edge_match_keywords:
- leverage
focus_areas_suggested:
- Prioritize leverage-loop and flash-loan entry points — brand match signals leverage
  logic
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 488840.9803997482
first_seen: '2026-01-29'
age_days: 117
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: ethereum:defillama:notional-exponent
priority_score: 5.27
why_interesting: 'Leveraged Farming on ethereum • $488,840 TVL • 117d old • audit_density=2
  • edge-match: leverage'
scan_date: '2026-05-26'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 2
defillama_audit_note: null
---

# Notional Exponent

> Leveraged Farming on ethereum • $488,840 TVL • 117d old • audit_density=2 • edge-match: leverage

## Summary

- **Chain**: ethereum
- **Primary contract**: `ethereum:defillama:notional-exponent`
- **TVL**: $489K (488,840)
- **Age**: 3mo (first seen 2026-01-29)
- **Languages**: solidity

## Audit history

- **Audit density score**: 2 (already audited)
- **DefiLlama audit count**: 2 (from /protocol/notional-exponent detail)
- Sources found:
  - `defillama` (1pt): https://docs.notional.finance/exponent/smart-contracts/security
  - `defillama` (1pt): DefiLlama audit (no link)

## Priority breakdown

- **Composite**: 5.27 / 10
  - tvl: 3.5 × 0.25
  - freshness: 6.8 × 0.20
  - audit_gap: 6.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 5.0 × 0.10 (keywords: leverage)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Prioritize leverage-loop and flash-loan entry points — brand match signals leverage logic

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on notional-exponent at ~/audit/2026-05-26-notional-exponent/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
