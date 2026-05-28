---
target_name: odyssey-finance
display_name: Odyssey Finance
protocol_type: Yield Aggregator on ethereum
languages:
- solidity
chains:
- ethereum
inferred_platform: private
inferred_mode: private
audit_density_score: 3
audit_sources_found:
- source: defillama
  url: https://docs.odyssey.finance/resources/audits
  title: null
  published_at: null
- source: defillama
  url: null
  title: DefiLlama audit (no link)
  published_at: null
- source: github_audits_folder
  url: https://github.com/odyssey-finance/odyssey-contracts-public/tree/HEAD/audits
  title: null
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- Real money at stake ($9,445,164 TVL) — favor impact-driven finding scoping
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 9445164.75584113
first_seen: '2025-08-06'
age_days: 293
unique_users_30d: null
github_repo: https://github.com/odyssey-finance/odyssey-contracts-public
loc_estimate: 765459
docs_url: null
primary_contract: ethereum:defillama:odyssey-finance
priority_score: 4.81
why_interesting: Yield Aggregator on ethereum • $9,445,164 TVL • 293d old • ~765459
  LOC • audit_density=3
scan_date: '2026-05-26'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 2
defillama_audit_note: null
---

# Odyssey Finance

> Yield Aggregator on ethereum • $9,445,164 TVL • 293d old • ~765459 LOC • audit_density=3

## Summary

- **Chain**: ethereum
- **Primary contract**: `ethereum:defillama:odyssey-finance`
- **TVL**: $9.4M (9,445,164)
- **Age**: 9mo (first seen 2025-08-06)
- **LOC estimate**: ~765,459
- **GitHub**: https://github.com/odyssey-finance/odyssey-contracts-public
- **Languages**: solidity

## Audit history

- **Audit density score**: 3 (already audited)
- **DefiLlama audit count**: 2 (from /protocol/odyssey-finance detail)
- Sources found:
  - `defillama` (1pt): https://docs.odyssey.finance/resources/audits
  - `defillama` (1pt): DefiLlama audit (no link)
  - `github_audits_folder` (1pt): https://github.com/odyssey-finance/odyssey-contracts-public/tree/HEAD/audits

## Priority breakdown

- **Composite**: 4.81 / 10
  - tvl: 9.9 × 0.25
  - freshness: 2.0 × 0.20
  - audit_gap: 4.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Real money at stake ($9,445,164 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on odyssey-finance at ~/audit/2026-05-26-odyssey-finance/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
