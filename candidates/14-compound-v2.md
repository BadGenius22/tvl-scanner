---
target_name: compound-v2
display_name: Compound V2
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
  url: https://compound.finance/docs/security
  title: null
  published_at: null
- source: defillama
  url: null
  title: DefiLlama audit (no link)
  published_at: null
- source: bounty_trust
  url: https://immunefi.com/bounty/compoundfinance/
  title: Trusted via immunefi bounty (max $500,000) — bounty platforms vet protocols
    against audit reports during onboarding
  published_at: null
- source: factory_attribution
  url: null
  title: Name 'compound-v2' matches known audited protocol family — audit attribution
    by name
  published_at: null
under_audited: false
edge_match_keywords:
- compound
focus_areas_suggested:
- Check integration seams with external lending/yield primitive — cross-protocol trust
  boundary
- Real money at stake ($116,260,255 TVL) — favor impact-driven finding scoping
bounty_program: immunefi
bounty_url: https://immunefi.com/bounty/compoundfinance/
bounty_max_payout_usd: 500000
tvl_usd: 116260255.30914745
first_seen: '2025-11-27'
age_days: 180
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: ethereum:defillama:compound-v2
priority_score: 5.76
why_interesting: 'Lending on ethereum • $116,260,255 TVL • 180d old • audit_density=10
  • edge-match: compound • bounty: immunefi'
scan_date: '2026-05-26'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 2
defillama_audit_note: null
---

# Compound V2

> Lending on ethereum • $116,260,255 TVL • 180d old • audit_density=10 • edge-match: compound • bounty: immunefi

## Summary

- **Chain**: ethereum
- **Primary contract**: `ethereum:defillama:compound-v2`
- **TVL**: $116.3M (116,260,255)
- **Age**: 6mo (first seen 2025-11-27)
- **Languages**: solidity

## Bounty program

- **Platform**: immunefi
- **URL**: https://immunefi.com/bounty/compoundfinance/
- **Max payout**: $500,000

## Audit history

- **Audit density score**: 10 (already audited)
- **DefiLlama audit count**: 2 (from /protocol/compound-v2 detail)
- Sources found:
  - `defillama` (1pt): https://compound.finance/docs/security
  - `defillama` (1pt): DefiLlama audit (no link)
  - `bounty_trust` (4pt): Trusted via immunefi bounty (max $500,000) — bounty platforms vet protocols against audit reports during onboarding
  - `factory_attribution` (4pt): Name 'compound-v2' matches known audited protocol family — audit attribution by name

## Priority breakdown

- **Composite**: 5.76 / 10
  - tvl: 10.0 × 0.25
  - freshness: 5.1 × 0.20
  - audit_gap: 0.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 5.0 × 0.10 (keywords: compound)
  - bounty: 10.0 × 0.10

## Suggested focus areas

- Check integration seams with external lending/yield primitive — cross-protocol trust boundary
- Real money at stake ($116,260,255 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on compound-v2 at ~/audit/2026-05-26-compound-v2/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
