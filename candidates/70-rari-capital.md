---
target_name: rari-capital
display_name: Rari Capital
protocol_type: Yield Aggregator on ethereum
languages:
- solidity
chains:
- ethereum
inferred_platform: private
inferred_mode: private
audit_density_score: 2
audit_sources_found:
- source: defillama
  url: https://www.notion.so/Rari-Capital-Audit-Quantstamp-December-2020-24a1d1df94894d6881ee190686f47bc7
  title: null
  published_at: null
- source: defillama
  url: null
  title: DefiLlama audit (no link)
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- Real money at stake ($1,464,866 TVL) — favor impact-driven finding scoping
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 1464866.0267797362
first_seen: '2025-11-27'
age_days: 180
unique_users_30d: null
github_repo: https://github.com/Rari-Capital/fuse-v1
loc_estimate: 37056
docs_url: null
primary_contract: ethereum:defillama:rari-capital
priority_score: 5.02
why_interesting: Yield Aggregator on ethereum • $1,464,866 TVL • 180d old • ~37056
  LOC • audit_density=2
scan_date: '2026-05-26'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 2
defillama_audit_note: null
---

# Rari Capital

> Yield Aggregator on ethereum • $1,464,866 TVL • 180d old • ~37056 LOC • audit_density=2

## Summary

- **Chain**: ethereum
- **Primary contract**: `ethereum:defillama:rari-capital`
- **TVL**: $1.5M (1,464,866)
- **Age**: 6mo (first seen 2025-11-27)
- **LOC estimate**: ~37,056
- **GitHub**: https://github.com/Rari-Capital/fuse-v1
- **Languages**: solidity

## Audit history

- **Audit density score**: 2 (already audited)
- **DefiLlama audit count**: 2 (from /protocol/rari-capital detail)
- Sources found:
  - `defillama` (1pt): https://www.notion.so/Rari-Capital-Audit-Quantstamp-December-2020-24a1d1df94894d6881ee190686f47bc7
  - `defillama` (1pt): DefiLlama audit (no link)

## Priority breakdown

- **Composite**: 5.02 / 10
  - tvl: 5.8 × 0.25
  - freshness: 5.1 × 0.20
  - audit_gap: 6.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Real money at stake ($1,464,866 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on rari-capital at ~/audit/2026-05-26-rari-capital/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
