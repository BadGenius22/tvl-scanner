---
target_name: aave-v2
display_name: Aave V2
protocol_type: Lending on ethereum
languages:
- solidity
chains:
- ethereum
inferred_platform: immunefi
inferred_mode: bug-bounty
audit_density_score: 11
audit_sources_found:
- source: defillama
  url: https://aave.com/security
  title: null
  published_at: null
- source: defillama
  url: null
  title: DefiLlama audit (no link)
  published_at: null
- source: github_audits_folder
  url: https://github.com/aave/protocol-v2/tree/HEAD/audits
  title: null
  published_at: null
- source: bounty_trust
  url: https://immunefi.com/bounty/aave/
  title: Trusted via immunefi bounty (max $1,000,000) — bounty platforms vet protocols
    against audit reports during onboarding
  published_at: null
- source: factory_attribution
  url: null
  title: Name 'aave-v2' matches known audited protocol family — audit attribution
    by name
  published_at: null
under_audited: false
edge_match_keywords:
- aave
focus_areas_suggested:
- Check integration seams with external lending/yield primitive — cross-protocol trust
  boundary
- Real money at stake ($123,754,132 TVL) — favor impact-driven finding scoping
bounty_program: immunefi
bounty_url: https://immunefi.com/bounty/aave/
bounty_max_payout_usd: 1000000
tvl_usd: 123754132.5396963
first_seen: '2025-11-26'
age_days: 180
unique_users_30d: null
github_repo: https://github.com/aave/protocol-v2
loc_estimate: 60191
docs_url: null
primary_contract: ethereum:defillama:aave-v2
priority_score: 5.76
why_interesting: 'Lending on ethereum • $123,754,132 TVL • 180d old • ~60191 LOC •
  audit_density=11 • edge-match: aave • bounty: immunefi'
scan_date: '2026-05-25'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 2
defillama_audit_note: null
---

# Aave V2

> Lending on ethereum • $123,754,132 TVL • 180d old • ~60191 LOC • audit_density=11 • edge-match: aave • bounty: immunefi

## Summary

- **Chain**: ethereum
- **Primary contract**: `ethereum:defillama:aave-v2`
- **TVL**: $123.8M (123,754,132)
- **Age**: 6mo (first seen 2025-11-26)
- **LOC estimate**: ~60,191
- **GitHub**: https://github.com/aave/protocol-v2
- **Languages**: solidity

## Bounty program

- **Platform**: immunefi
- **URL**: https://immunefi.com/bounty/aave/
- **Max payout**: $1,000,000

## Audit history

- **Audit density score**: 11 (already audited)
- **DefiLlama audit count**: 2 (from /protocol/aave-v2 detail)
- Sources found:
  - `defillama` (1pt): https://aave.com/security
  - `defillama` (1pt): DefiLlama audit (no link)
  - `github_audits_folder` (1pt): https://github.com/aave/protocol-v2/tree/HEAD/audits
  - `bounty_trust` (4pt): Trusted via immunefi bounty (max $1,000,000) — bounty platforms vet protocols against audit reports during onboarding
  - `factory_attribution` (4pt): Name 'aave-v2' matches known audited protocol family — audit attribution by name

## Priority breakdown

- **Composite**: 5.76 / 10
  - tvl: 10.0 × 0.25
  - freshness: 5.1 × 0.20
  - audit_gap: 0.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 5.0 × 0.10 (keywords: aave)
  - bounty: 10.0 × 0.10

## Suggested focus areas

- Check integration seams with external lending/yield primitive — cross-protocol trust boundary
- Real money at stake ($123,754,132 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on aave-v2 at ~/audit/2026-05-25-aave-v2/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
