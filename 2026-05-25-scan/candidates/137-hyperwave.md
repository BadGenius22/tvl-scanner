---
target_name: hyperwave
display_name: HyperWave
protocol_type: Yield on arbitrum
languages:
- solidity
chains:
- arbitrum
inferred_platform: private
inferred_mode: private
audit_density_score: 2
audit_sources_found:
- source: defillama
  url: https://docs.hyperwavefi.xyz/references/audits
  title: null
  published_at: null
- source: defillama
  url: null
  title: DefiLlama audit (no link)
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- Real money at stake ($6,680,485 TVL) — favor impact-driven finding scoping
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 6680485.606596524
first_seen: '2025-07-09'
age_days: 320
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: arbitrum:defillama:hyperwave
priority_score: 5.08
why_interesting: Yield on arbitrum • $6,680,485 TVL • 320d old • audit_density=2
scan_date: '2026-05-25'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 2
defillama_audit_note: null
---

# HyperWave

> Yield on arbitrum • $6,680,485 TVL • 320d old • audit_density=2

## Summary

- **Chain**: arbitrum
- **Primary contract**: `arbitrum:defillama:hyperwave`
- **TVL**: $6.7M (6,680,485)
- **Age**: 10mo (first seen 2025-07-09)
- **Languages**: solidity

## Audit history

- **Audit density score**: 2 (already audited)
- **DefiLlama audit count**: 2 (from /protocol/hyperwave detail)
- Sources found:
  - `defillama` (1pt): https://docs.hyperwavefi.xyz/references/audits
  - `defillama` (1pt): DefiLlama audit (no link)

## Priority breakdown

- **Composite**: 5.08 / 10
  - tvl: 9.1 × 0.25
  - freshness: 1.2 × 0.20
  - audit_gap: 6.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Real money at stake ($6,680,485 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on hyperwave at ~/audit/2026-05-25-hyperwave/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
