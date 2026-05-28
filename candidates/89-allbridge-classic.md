---
target_name: allbridge-classic
display_name: Allbridge Classic
protocol_type: Bridge on ethereum
languages:
- solidity
chains:
- ethereum
inferred_platform: private
inferred_mode: private
audit_density_score: 3
audit_sources_found:
- source: defillama
  url: https://hacken.io/audits/allbridge
  title: null
  published_at: null
- source: defillama
  url: https://drive.google.com/file/d/1geBAoT0iuLy3s7EnlUBDKfXr-BwZWpHZ/view
  title: null
  published_at: null
- source: defillama
  url: https://drive.google.com/file/d/1PV5MN6L5FGCLYEUnLa8D5LI4Ev5157EX/view
  title: null
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- Real money at stake ($3,303,725 TVL) — favor impact-driven finding scoping
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 3303725.4107043827
first_seen: '2025-11-27'
age_days: 180
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: ethereum:defillama:allbridge-classic
priority_score: 4.86
why_interesting: Bridge on ethereum • $3,303,725 TVL • 180d old • audit_density=3
scan_date: '2026-05-26'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 2
defillama_audit_note: null
---

# Allbridge Classic

> Bridge on ethereum • $3,303,725 TVL • 180d old • audit_density=3

## Summary

- **Chain**: ethereum
- **Primary contract**: `ethereum:defillama:allbridge-classic`
- **TVL**: $3.3M (3,303,725)
- **Age**: 6mo (first seen 2025-11-27)
- **Languages**: solidity

## Audit history

- **Audit density score**: 3 (already audited)
- **DefiLlama audit count**: 2 (from /protocol/allbridge-classic detail)
- Sources found:
  - `defillama` (1pt): https://hacken.io/audits/allbridge
  - `defillama` (1pt): https://drive.google.com/file/d/1geBAoT0iuLy3s7EnlUBDKfXr-BwZWpHZ/view
  - `defillama` (1pt): https://drive.google.com/file/d/1PV5MN6L5FGCLYEUnLa8D5LI4Ev5157EX/view

## Priority breakdown

- **Composite**: 4.86 / 10
  - tvl: 7.6 × 0.25
  - freshness: 5.1 × 0.20
  - audit_gap: 4.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Real money at stake ($3,303,725 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on allbridge-classic at ~/audit/2026-05-26-allbridge-classic/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
