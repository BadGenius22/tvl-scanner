---
target_name: strata-markets
display_name: Strata Markets
protocol_type: Yield on ethereum
languages:
- solidity
chains:
- ethereum
inferred_platform: private
inferred_mode: private
audit_density_score: 2
audit_sources_found:
- source: defillama
  url: https://docs.strata.money/security/audits
  title: null
  published_at: null
- source: defillama
  url: null
  title: DefiLlama audit (no link)
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- Real money at stake ($97,798,949 TVL) — favor impact-driven finding scoping
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 97798949.39082928
first_seen: '2025-10-16'
age_days: 221
unique_users_30d: null
github_repo: https://github.com/Strata-Markets/contracts-tranches-release-reports
loc_estimate: 170298
docs_url: null
primary_contract: ethereum:defillama:strata-markets
priority_score: 5.84
why_interesting: Yield on ethereum • $97,798,949 TVL • 221d old • ~170298 LOC • audit_density=2
scan_date: '2026-05-25'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 2
defillama_audit_note: null
---

# Strata Markets

> Yield on ethereum • $97,798,949 TVL • 221d old • ~170298 LOC • audit_density=2

## Summary

- **Chain**: ethereum
- **Primary contract**: `ethereum:defillama:strata-markets`
- **TVL**: $97.8M (97,798,949)
- **Age**: 7mo (first seen 2025-10-16)
- **LOC estimate**: ~170,298
- **GitHub**: https://github.com/Strata-Markets/contracts-tranches-release-reports
- **Languages**: solidity

## Audit history

- **Audit density score**: 2 (already audited)
- **DefiLlama audit count**: 2 (from /protocol/strata-markets detail)
- Sources found:
  - `defillama` (1pt): https://docs.strata.money/security/audits
  - `defillama` (1pt): DefiLlama audit (no link)

## Priority breakdown

- **Composite**: 5.84 / 10
  - tvl: 10.0 × 0.25
  - freshness: 4.0 × 0.20
  - audit_gap: 6.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Real money at stake ($97,798,949 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on strata-markets at ~/audit/2026-05-25-strata-markets/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
