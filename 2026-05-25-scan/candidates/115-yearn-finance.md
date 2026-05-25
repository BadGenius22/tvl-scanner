---
target_name: yearn-finance
display_name: Yearn Finance
protocol_type: Yield Aggregator on ethereum
languages:
- solidity
chains:
- ethereum
inferred_platform: immunefi
inferred_mode: bug-bounty
audit_density_score: 11
audit_sources_found:
- source: defillama
  url: https://github.com/yearn/yearn-security/tree/master/audits
  title: null
  published_at: null
- source: defillama
  url: null
  title: DefiLlama audit (no link)
  published_at: null
- source: github_audits_folder
  url: https://github.com/yearn/yearn-vaults-v3/tree/HEAD/audits
  title: null
  published_at: null
- source: bounty_trust
  url: https://immunefi.com/bounty/yearnfinance/
  title: Trusted via immunefi bounty (max $200,000) — bounty platforms vet protocols
    against audit reports during onboarding
  published_at: null
- source: factory_attribution
  url: null
  title: Name 'yearn-finance' matches known audited protocol family — audit attribution
    by name
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- Real money at stake ($175,188,957 TVL) — favor impact-driven finding scoping
bounty_program: immunefi
bounty_url: https://immunefi.com/bounty/yearnfinance/
bounty_max_payout_usd: 200000
tvl_usd: 175188957.61128443
first_seen: '2025-11-26'
age_days: 180
unique_users_30d: null
github_repo: https://github.com/yearn/yearn-vaults-v3
loc_estimate: 5768
docs_url: null
primary_contract: ethereum:defillama:yearn-finance
priority_score: 5.26
why_interesting: 'Yield Aggregator on ethereum • $175,188,957 TVL • 180d old • ~5768
  LOC • audit_density=11 • bounty: immunefi'
scan_date: '2026-05-25'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 2
defillama_audit_note: null
---

# Yearn Finance

> Yield Aggregator on ethereum • $175,188,957 TVL • 180d old • ~5768 LOC • audit_density=11 • bounty: immunefi

## Summary

- **Chain**: ethereum
- **Primary contract**: `ethereum:defillama:yearn-finance`
- **TVL**: $175.2M (175,188,957)
- **Age**: 6mo (first seen 2025-11-26)
- **LOC estimate**: ~5,768
- **GitHub**: https://github.com/yearn/yearn-vaults-v3
- **Languages**: solidity

## Bounty program

- **Platform**: immunefi
- **URL**: https://immunefi.com/bounty/yearnfinance/
- **Max payout**: $200,000

## Audit history

- **Audit density score**: 11 (already audited)
- **DefiLlama audit count**: 2 (from /protocol/yearn-finance detail)
- Sources found:
  - `defillama` (1pt): https://github.com/yearn/yearn-security/tree/master/audits
  - `defillama` (1pt): DefiLlama audit (no link)
  - `github_audits_folder` (1pt): https://github.com/yearn/yearn-vaults-v3/tree/HEAD/audits
  - `bounty_trust` (4pt): Trusted via immunefi bounty (max $200,000) — bounty platforms vet protocols against audit reports during onboarding
  - `factory_attribution` (4pt): Name 'yearn-finance' matches known audited protocol family — audit attribution by name

## Priority breakdown

- **Composite**: 5.26 / 10
  - tvl: 10.0 × 0.25
  - freshness: 5.1 × 0.20
  - audit_gap: 0.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 10.0 × 0.10

## Suggested focus areas

- Real money at stake ($175,188,957 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on yearn-finance at ~/audit/2026-05-25-yearn-finance/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
