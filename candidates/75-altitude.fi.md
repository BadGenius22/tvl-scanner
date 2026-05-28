---
target_name: altitude.fi
display_name: Altitude.Fi
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
  url: https://docs.altitude.fi/smart-contracts/audits#completed-audits
  title: null
  published_at: null
- source: defillama
  url: null
  title: DefiLlama audit (no link)
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- Real money at stake ($6,967,781 TVL) — favor impact-driven finding scoping
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 6967781.342309313
first_seen: '2025-06-20'
age_days: 340
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: ethereum:defillama:altitude.fi
priority_score: 4.99
why_interesting: Lending on ethereum • $6,967,781 TVL • 340d old • audit_density=2
scan_date: '2026-05-26'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 2
defillama_audit_note: null
---

# Altitude.Fi

> Lending on ethereum • $6,967,781 TVL • 340d old • audit_density=2

## Summary

- **Chain**: ethereum
- **Primary contract**: `ethereum:defillama:altitude.fi`
- **TVL**: $7.0M (6,967,781)
- **Age**: 11mo (first seen 2025-06-20)
- **Languages**: solidity

## Audit history

- **Audit density score**: 2 (already audited)
- **DefiLlama audit count**: 2 (from /protocol/altitude.fi detail)
- Sources found:
  - `defillama` (1pt): https://docs.altitude.fi/smart-contracts/audits#completed-audits
  - `defillama` (1pt): DefiLlama audit (no link)

## Priority breakdown

- **Composite**: 4.99 / 10
  - tvl: 9.2 × 0.25
  - freshness: 0.7 × 0.20
  - audit_gap: 6.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Real money at stake ($6,967,781 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on altitude.fi at ~/audit/2026-05-26-altitude.fi/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
