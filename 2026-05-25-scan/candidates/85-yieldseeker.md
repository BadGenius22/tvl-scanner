---
target_name: yieldseeker
display_name: YieldSeeker
protocol_type: Yield Aggregator on base
languages:
- solidity
chains:
- base
inferred_platform: private
inferred_mode: private
audit_density_score: 2
audit_sources_found:
- source: defillama
  url: https://github.com/tokenpage/yieldseeker-contracts/tree/main/audits
  title: null
  published_at: null
- source: defillama
  url: null
  title: DefiLlama audit (no link)
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- Brand-new contract (54d old) — check initialization racing, first-caller bootstrap
  invariants
- Real money at stake ($1,247,946 TVL) — favor impact-driven finding scoping
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 1247946.949905968
first_seen: '2026-04-01'
age_days: 54
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: base:defillama:yieldseeker
priority_score: 5.62
why_interesting: Yield Aggregator on base • $1,247,946 TVL • 54d old • audit_density=2
scan_date: '2026-05-25'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 2
defillama_audit_note: null
---

# YieldSeeker

> Yield Aggregator on base • $1,247,946 TVL • 54d old • audit_density=2

## Summary

- **Chain**: base
- **Primary contract**: `base:defillama:yieldseeker`
- **TVL**: $1.2M (1,247,946)
- **Age**: 1mo (first seen 2026-04-01)
- **Languages**: solidity

## Audit history

- **Audit density score**: 2 (already audited)
- **DefiLlama audit count**: 2 (from /protocol/yieldseeker detail)
- Sources found:
  - `defillama` (1pt): https://github.com/tokenpage/yieldseeker-contracts/tree/main/audits
  - `defillama` (1pt): DefiLlama audit (no link)

## Priority breakdown

- **Composite**: 5.62 / 10
  - tvl: 5.5 × 0.25
  - freshness: 8.5 × 0.20
  - audit_gap: 6.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Brand-new contract (54d old) — check initialization racing, first-caller bootstrap invariants
- Real money at stake ($1,247,946 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on yieldseeker at ~/audit/2026-05-25-yieldseeker/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
