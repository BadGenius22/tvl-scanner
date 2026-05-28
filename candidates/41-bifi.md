---
target_name: bifi
display_name: BiFi
protocol_type: Lending on ethereum
languages:
- solidity
chains:
- ethereum
inferred_platform: private
inferred_mode: private
audit_density_score: 3
audit_sources_found:
- source: defillama
  url: https://github.com/bifrost-platform/BiFi-X/blob/main/docs/bifrost_bifix_audit.pdf
  title: null
  published_at: null
- source: defillama
  url: https://github.com/bifrost-platform/BIFI/blob/master/docs/ENG/(ENG)_BiFi_BIFROST_Extension_Theori.pdf
  title: null
  published_at: null
- source: defillama
  url: https://github.com/bifrost-platform/BIFI/blob/master/docs/ENG/(ENG)_BiFi_Lending_Sooho_EN_Public.pdf
  title: null
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- Real money at stake ($7,418,998 TVL) — favor impact-driven finding scoping
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 7418998.174752742
first_seen: '2025-11-27'
age_days: 180
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: ethereum:defillama:bifi
priority_score: 5.3
why_interesting: Lending on ethereum • $7,418,998 TVL • 180d old • audit_density=3
scan_date: '2026-05-26'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 2
defillama_audit_note: null
---

# BiFi

> Lending on ethereum • $7,418,998 TVL • 180d old • audit_density=3

## Summary

- **Chain**: ethereum
- **Primary contract**: `ethereum:defillama:bifi`
- **TVL**: $7.4M (7,418,998)
- **Age**: 6mo (first seen 2025-11-27)
- **Languages**: solidity

## Audit history

- **Audit density score**: 3 (already audited)
- **DefiLlama audit count**: 2 (from /protocol/bifi detail)
- Sources found:
  - `defillama` (1pt): https://github.com/bifrost-platform/BiFi-X/blob/main/docs/bifrost_bifix_audit.pdf
  - `defillama` (1pt): https://github.com/bifrost-platform/BIFI/blob/master/docs/ENG/(ENG)_BiFi_BIFROST_Extension_Theori.pdf
  - `defillama` (1pt): https://github.com/bifrost-platform/BIFI/blob/master/docs/ENG/(ENG)_BiFi_Lending_Sooho_EN_Public.pdf

## Priority breakdown

- **Composite**: 5.30 / 10
  - tvl: 9.3 × 0.25
  - freshness: 5.1 × 0.20
  - audit_gap: 4.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Real money at stake ($7,418,998 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on bifi at ~/audit/2026-05-26-bifi/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
