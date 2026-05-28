---
target_name: templar-protocol
display_name: Templar Protocol
protocol_type: Lending on ethereum
languages:
- solidity
- rust
chains:
- ethereum
inferred_platform: private
inferred_mode: private
audit_density_score: 3
audit_sources_found:
- source: defillama
  url: https://github.com/Templar-Protocol/contracts/blob/dev/audits/2025-07-01/guvenkaya/Templar-NEAR-Smart-Contract-Security-Review-Final-Report.pdf
  title: null
  published_at: null
- source: defillama
  url: https://github.com/Templar-Protocol/contracts/blob/dev/audits/2025-07-01/thesis_defense/250701_Defense_by_Thesis_Templar_Smart_Contracts_Final_Security.pdf
  title: null
  published_at: null
- source: github_audits_folder
  url: https://github.com/Templar-Protocol/contracts/tree/HEAD/audits
  title: null
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- Real money at stake ($21,411,209 TVL) — favor impact-driven finding scoping
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 21411209.608540032
first_seen: '2025-08-12'
age_days: 287
unique_users_30d: null
github_repo: https://github.com/Templar-Protocol/contracts
loc_estimate: 171096
docs_url: null
primary_contract: ethereum:defillama:templar-protocol
priority_score: 4.88
why_interesting: Lending on ethereum • $21,411,209 TVL • 287d old • ~171096 LOC •
  audit_density=3
scan_date: '2026-05-26'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 0
defillama_audit_note: null
---

# Templar Protocol

> Lending on ethereum • $21,411,209 TVL • 287d old • ~171096 LOC • audit_density=3

## Summary

- **Chain**: ethereum
- **Primary contract**: `ethereum:defillama:templar-protocol`
- **TVL**: $21.4M (21,411,209)
- **Age**: 9mo (first seen 2025-08-12)
- **LOC estimate**: ~171,096
- **GitHub**: https://github.com/Templar-Protocol/contracts
- **Languages**: solidity, rust

## Audit history

- **Audit density score**: 3 (already audited)
- **DefiLlama audit count**: 0 (from /protocol/templar-protocol detail)
- Sources found:
  - `defillama` (1pt): https://github.com/Templar-Protocol/contracts/blob/dev/audits/2025-07-01/guvenkaya/Templar-NEAR-Smart-Contract-Security-Review-Final-Report.pdf
  - `defillama` (1pt): https://github.com/Templar-Protocol/contracts/blob/dev/audits/2025-07-01/thesis_defense/250701_Defense_by_Thesis_Templar_Smart_Contracts_Final_Security.pdf
  - `github_audits_folder` (1pt): https://github.com/Templar-Protocol/contracts/tree/HEAD/audits

## Priority breakdown

- **Composite**: 4.88 / 10
  - tvl: 10.0 × 0.25
  - freshness: 2.1 × 0.20
  - audit_gap: 4.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Real money at stake ($21,411,209 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on templar-protocol at ~/audit/2026-05-26-templar-protocol/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
