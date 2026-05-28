---
target_name: sunx-bridge
display_name: SunX Bridge
protocol_type: Bridge on ethereum
languages:
- solidity
chains:
- ethereum
inferred_platform: private
inferred_mode: private
audit_density_score: 2
audit_sources_found:
- source: defillama
  url: https://github.com/slowmist/Knowledge-Base/blob/master/open-report-V2/smart-contract/Sunperp%20Dex%20-%20SlowMist%20Audit%20Report.pdf
  title: null
  published_at: null
- source: defillama
  url: null
  title: DefiLlama audit (no link)
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- Real money at stake ($36,218,493 TVL) — favor impact-driven finding scoping
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 36218493.34899336
first_seen: '2025-09-24'
age_days: 244
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: ethereum:defillama:sunx-bridge
priority_score: 5.71
why_interesting: Bridge on ethereum • $36,218,493 TVL • 244d old • audit_density=2
scan_date: '2026-05-26'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 2
defillama_audit_note: null
---

# SunX Bridge

> Bridge on ethereum • $36,218,493 TVL • 244d old • audit_density=2

## Summary

- **Chain**: ethereum
- **Primary contract**: `ethereum:defillama:sunx-bridge`
- **TVL**: $36.2M (36,218,493)
- **Age**: 8mo (first seen 2025-09-24)
- **Languages**: solidity

## Audit history

- **Audit density score**: 2 (already audited)
- **DefiLlama audit count**: 2 (from /protocol/sunx-bridge detail)
- Sources found:
  - `defillama` (1pt): https://github.com/slowmist/Knowledge-Base/blob/master/open-report-V2/smart-contract/Sunperp%20Dex%20-%20SlowMist%20Audit%20Report.pdf
  - `defillama` (1pt): DefiLlama audit (no link)

## Priority breakdown

- **Composite**: 5.71 / 10
  - tvl: 10.0 × 0.25
  - freshness: 3.3 × 0.20
  - audit_gap: 6.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Real money at stake ($36,218,493 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on sunx-bridge at ~/audit/2026-05-26-sunx-bridge/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
