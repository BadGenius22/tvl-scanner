---
target_name: kasu
display_name: Kasu
protocol_type: RWA Lending on base
languages:
- solidity
chains:
- base
inferred_platform: private
inferred_mode: private
audit_density_score: 2
audit_sources_found:
- source: defillama
  url: https://github.com/Kasu-Finance/security/tree/main/audits/Kasu_0xCommit.pdf
  title: null
  published_at: null
- source: defillama
  url: https://github.com/Kasu-Finance/security/tree/main/audits/Kasu_ChainSecurity.pdf
  title: null
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- Real money at stake ($10,295,171 TVL) — favor impact-driven finding scoping
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 10295171.088390192
first_seen: '2025-12-09'
age_days: 167
unique_users_30d: null
github_repo: https://github.com/Kasu-Finance/kasu-contracts
loc_estimate: 42805
docs_url: null
primary_contract: base:defillama:kasu
priority_score: 6.13
why_interesting: RWA Lending on base • $10,295,171 TVL • 167d old • ~42805 LOC • audit_density=2
scan_date: '2026-05-25'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 2
defillama_audit_note: null
---

# Kasu

> RWA Lending on base • $10,295,171 TVL • 167d old • ~42805 LOC • audit_density=2

## Summary

- **Chain**: base
- **Primary contract**: `base:defillama:kasu`
- **TVL**: $10.3M (10,295,171)
- **Age**: 5mo (first seen 2025-12-09)
- **LOC estimate**: ~42,805
- **GitHub**: https://github.com/Kasu-Finance/kasu-contracts
- **Languages**: solidity

## Audit history

- **Audit density score**: 2 (already audited)
- **DefiLlama audit count**: 2 (from /protocol/kasu detail)
- Sources found:
  - `defillama` (1pt): https://github.com/Kasu-Finance/security/tree/main/audits/Kasu_0xCommit.pdf
  - `defillama` (1pt): https://github.com/Kasu-Finance/security/tree/main/audits/Kasu_ChainSecurity.pdf

## Priority breakdown

- **Composite**: 6.13 / 10
  - tvl: 10.0 × 0.25
  - freshness: 5.4 × 0.20
  - audit_gap: 6.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Real money at stake ($10,295,171 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on kasu at ~/audit/2026-05-25-kasu/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
