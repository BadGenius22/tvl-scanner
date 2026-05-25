---
target_name: silo-v3
display_name: Silo V3
protocol_type: Lending on ethereum
languages:
- solidity
chains:
- ethereum
inferred_platform: private
inferred_mode: private
audit_density_score: 6
audit_sources_found:
- source: defillama
  url: https://docs.silo.finance/audits-and-tests
  title: null
  published_at: null
- source: defillama
  url: null
  title: DefiLlama audit (no link)
  published_at: null
- source: factory_attribution
  url: null
  title: Name 'silo-v3' matches known audited protocol family — audit attribution
    by name
  published_at: null
under_audited: false
edge_match_keywords:
- silo
focus_areas_suggested:
- Check integration seams with external lending/yield primitive — cross-protocol trust
  boundary
- Brand-new contract (6d old) — check initialization racing, first-caller bootstrap
  invariants
- Real money at stake ($3,243,577 TVL) — favor impact-driven finding scoping
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 3243577.4303336437
first_seen: '2026-05-19'
age_days: 6
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: ethereum:defillama:silo-v3
priority_score: 5.11
why_interesting: 'Lending on ethereum • $3,243,577 TVL • 6d old • audit_density=6
  • edge-match: silo'
scan_date: '2026-05-25'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 2
defillama_audit_note: null
---

# Silo V3

> Lending on ethereum • $3,243,577 TVL • 6d old • audit_density=6 • edge-match: silo

## Summary

- **Chain**: ethereum
- **Primary contract**: `ethereum:defillama:silo-v3`
- **TVL**: $3.2M (3,243,577)
- **Age**: 6d (first seen 2026-05-19)
- **Languages**: solidity

## Audit history

- **Audit density score**: 6 (already audited)
- **DefiLlama audit count**: 2 (from /protocol/silo-v3 detail)
- Sources found:
  - `defillama` (1pt): https://docs.silo.finance/audits-and-tests
  - `defillama` (1pt): DefiLlama audit (no link)
  - `factory_attribution` (4pt): Name 'silo-v3' matches known audited protocol family — audit attribution by name

## Priority breakdown

- **Composite**: 5.11 / 10
  - tvl: 7.6 × 0.25
  - freshness: 9.8 × 0.20
  - audit_gap: 0.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 5.0 × 0.10 (keywords: silo)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Check integration seams with external lending/yield primitive — cross-protocol trust boundary
- Brand-new contract (6d old) — check initialization racing, first-caller bootstrap invariants
- Real money at stake ($3,243,577 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on silo-v3 at ~/audit/2026-05-25-silo-v3/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
