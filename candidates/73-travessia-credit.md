---
target_name: travessia-credit
display_name: Travessia Credit
protocol_type: RWA Lending on ethereum
languages:
- solidity
chains:
- ethereum
inferred_platform: private
inferred_mode: private
audit_density_score: 2
audit_sources_found:
- source: defillama
  url: https://docs.travessiacredit.com/pages/security-audits-risk-controls.html
  title: null
  published_at: null
- source: defillama
  url: null
  title: DefiLlama audit (no link)
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- Brand-new contract (40d old) — check initialization racing, first-caller bootstrap
  invariants
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 340326.3039439939
first_seen: '2026-04-16'
age_days: 40
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: ethereum:defillama:travessia-credit
priority_score: 5.0
why_interesting: RWA Lending on ethereum • $340,326 TVL • 40d old • audit_density=2
scan_date: '2026-05-26'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 2
defillama_audit_note: null
---

# Travessia Credit

> RWA Lending on ethereum • $340,326 TVL • 40d old • audit_density=2

## Summary

- **Chain**: ethereum
- **Primary contract**: `ethereum:defillama:travessia-credit`
- **TVL**: $340K (340,326)
- **Age**: 1mo (first seen 2026-04-16)
- **Languages**: solidity

## Audit history

- **Audit density score**: 2 (already audited)
- **DefiLlama audit count**: 2 (from /protocol/travessia-credit detail)
- Sources found:
  - `defillama` (1pt): https://docs.travessiacredit.com/pages/security-audits-risk-controls.html
  - `defillama` (1pt): DefiLlama audit (no link)

## Priority breakdown

- **Composite**: 5.00 / 10
  - tvl: 2.7 × 0.25
  - freshness: 8.9 × 0.20
  - audit_gap: 6.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Brand-new contract (40d old) — check initialization racing, first-caller bootstrap invariants

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on travessia-credit at ~/audit/2026-05-26-travessia-credit/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
