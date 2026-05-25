---
target_name: aave-v4
display_name: Aave V4
protocol_type: Lending on ethereum
languages:
- solidity
chains:
- ethereum
inferred_platform: immunefi
inferred_mode: bug-bounty
audit_density_score: 10
audit_sources_found:
- source: defillama
  url: https://aave.com/security
  title: null
  published_at: null
- source: defillama
  url: null
  title: DefiLlama audit (no link)
  published_at: null
- source: bounty_trust
  url: https://immunefi.com/bounty/aave/
  title: Trusted via immunefi bounty (max $1,000,000) — bounty platforms vet protocols
    against audit reports during onboarding
  published_at: null
- source: factory_attribution
  url: null
  title: Name 'aave-v4' matches known audited protocol family — audit attribution
    by name
  published_at: null
under_audited: false
edge_match_keywords:
- aave
focus_areas_suggested:
- Check integration seams with external lending/yield primitive — cross-protocol trust
  boundary
- Brand-new contract (56d old) — check initialization racing, first-caller bootstrap
  invariants
- Real money at stake ($59,012,897 TVL) — favor impact-driven finding scoping
bounty_program: immunefi
bounty_url: https://immunefi.com/bounty/aave/
bounty_max_payout_usd: 1000000
tvl_usd: 59012897.94157951
first_seen: '2026-03-30'
age_days: 56
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: ethereum:defillama:aave-v4
priority_score: 6.44
why_interesting: 'Lending on ethereum • $59,012,897 TVL • 56d old • audit_density=10
  • edge-match: aave • bounty: immunefi'
scan_date: '2026-05-25'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 2
defillama_audit_note: null
---

# Aave V4

> Lending on ethereum • $59,012,897 TVL • 56d old • audit_density=10 • edge-match: aave • bounty: immunefi

## Summary

- **Chain**: ethereum
- **Primary contract**: `ethereum:defillama:aave-v4`
- **TVL**: $59.0M (59,012,897)
- **Age**: 1mo (first seen 2026-03-30)
- **Languages**: solidity

## Bounty program

- **Platform**: immunefi
- **URL**: https://immunefi.com/bounty/aave/
- **Max payout**: $1,000,000

## Audit history

- **Audit density score**: 10 (already audited)
- **DefiLlama audit count**: 2 (from /protocol/aave-v4 detail)
- Sources found:
  - `defillama` (1pt): https://aave.com/security
  - `defillama` (1pt): DefiLlama audit (no link)
  - `bounty_trust` (4pt): Trusted via immunefi bounty (max $1,000,000) — bounty platforms vet protocols against audit reports during onboarding
  - `factory_attribution` (4pt): Name 'aave-v4' matches known audited protocol family — audit attribution by name

## Priority breakdown

- **Composite**: 6.44 / 10
  - tvl: 10.0 × 0.25
  - freshness: 8.5 × 0.20
  - audit_gap: 0.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 5.0 × 0.10 (keywords: aave)
  - bounty: 10.0 × 0.10

## Suggested focus areas

- Check integration seams with external lending/yield primitive — cross-protocol trust boundary
- Brand-new contract (56d old) — check initialization racing, first-caller bootstrap invariants
- Real money at stake ($59,012,897 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on aave-v4 at ~/audit/2026-05-25-aave-v4/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
