---
target_name: tangent-finance
display_name: Tangent Finance
protocol_type: Lending on ethereum
languages:
- solidity
chains:
- ethereum
inferred_platform: private
inferred_mode: private
audit_density_score: 2
audit_sources_found:
- source: defillama
  url: https://docs.tangent.finance/docs/faq/audits
  title: null
  published_at: null
- source: defillama
  url: null
  title: DefiLlama audit (no link)
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- Brand-new contract (0d old) — check initialization racing, first-caller bootstrap
  invariants
- Real money at stake ($1,737,850 TVL) — favor impact-driven finding scoping
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 1737850.5815923773
first_seen: '2026-05-26'
age_days: 0
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: ethereum:defillama:tangent-finance
priority_score: 6.1
why_interesting: Lending on ethereum • $1,737,850 TVL • 0d old • audit_density=2
scan_date: '2026-05-26'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 2
defillama_audit_note: null
---

# Tangent Finance

> Lending on ethereum • $1,737,850 TVL • 0d old • audit_density=2

## Summary

- **Chain**: ethereum
- **Primary contract**: `ethereum:defillama:tangent-finance`
- **TVL**: $1.7M (1,737,850)
- **Age**: 0d (first seen 2026-05-26)
- **Languages**: solidity

## Audit history

- **Audit density score**: 2 (already audited)
- **DefiLlama audit count**: 2 (from /protocol/tangent-finance detail)
- Sources found:
  - `defillama` (1pt): https://docs.tangent.finance/docs/faq/audits
  - `defillama` (1pt): DefiLlama audit (no link)

## Priority breakdown

- **Composite**: 6.10 / 10
  - tvl: 6.2 × 0.25
  - freshness: 10.0 × 0.20
  - audit_gap: 6.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Brand-new contract (0d old) — check initialization racing, first-caller bootstrap invariants
- Real money at stake ($1,737,850 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on tangent-finance at ~/audit/2026-05-26-tangent-finance/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
