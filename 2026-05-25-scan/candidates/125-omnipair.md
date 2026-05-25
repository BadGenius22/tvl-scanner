---
target_name: omnipair
display_name: Omnipair
protocol_type: Lending on solana
languages:
- rust
chains:
- solana
inferred_platform: private
inferred_mode: private
audit_density_score: 2
audit_sources_found:
- source: defillama
  url: https://github.com/omnipair/omnipair-rs/tree/main/audits/offsidelabs
  title: null
  published_at: null
- source: defillama
  url: https://github.com/omnipair/omnipair-rs/tree/main/audits/ackee
  title: null
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- Standard breadth sweep on rust code; no edge-match tailwinds
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 596953.6385356518
first_seen: '2026-03-24'
age_days: 62
unique_users_30d: null
github_repo: https://github.com/omnipair/omnipair-indexer
loc_estimate: 32639
docs_url: null
primary_contract: solana:defillama:omnipair
priority_score: 5.18
why_interesting: Lending on solana • $596,953 TVL • 62d old • ~32639 LOC • audit_density=2
scan_date: '2026-05-25'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 2
defillama_audit_note: null
---

# Omnipair

> Lending on solana • $596,953 TVL • 62d old • ~32639 LOC • audit_density=2

## Summary

- **Chain**: solana
- **Primary contract**: `solana:defillama:omnipair`
- **TVL**: $597K (596,953)
- **Age**: 2mo (first seen 2026-03-24)
- **LOC estimate**: ~32,639
- **GitHub**: https://github.com/omnipair/omnipair-indexer
- **Languages**: rust

## Reproducible build (OtterSec)

- **Status**: — Not registered in OtterSec
  - This is the default for most Solana programs (<20% are registered). NOT a red flag — but you cannot trust that the github_repo matches the deployed bytecode byte-for-byte without running `solana-verify` yourself.

## Audit history

- **Audit density score**: 2 (already audited)
- **DefiLlama audit count**: 2 (from /protocol/omnipair detail)
- Sources found:
  - `defillama` (1pt): https://github.com/omnipair/omnipair-rs/tree/main/audits/offsidelabs
  - `defillama` (1pt): https://github.com/omnipair/omnipair-rs/tree/main/audits/ackee

## Priority breakdown

- **Composite**: 5.18 / 10
  - tvl: 3.9 × 0.25
  - freshness: 8.3 × 0.20
  - audit_gap: 6.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Standard breadth sweep on rust code; no edge-match tailwinds

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on omnipair at ~/audit/2026-05-25-omnipair/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
