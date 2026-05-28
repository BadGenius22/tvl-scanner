---
target_name: pacifica-perps
display_name: Pacifica Perps
protocol_type: Derivatives on solana
languages:
- rust
chains:
- solana
inferred_platform: private
inferred_mode: private
audit_density_score: 2
audit_sources_found:
- source: defillama
  url: https://docs.pacifica.fi/other/audits
  title: null
  published_at: null
- source: defillama
  url: null
  title: DefiLlama audit (no link)
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- Real money at stake ($30,012,724 TVL) — favor impact-driven finding scoping
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 30012724.032323938
first_seen: '2025-09-08'
age_days: 260
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: solana:defillama:pacifica-perps
priority_score: 5.63
why_interesting: Derivatives on solana • $30,012,724 TVL • 260d old • audit_density=2
scan_date: '2026-05-26'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 2
defillama_audit_note: null
---

# Pacifica Perps

> Derivatives on solana • $30,012,724 TVL • 260d old • audit_density=2

## Summary

- **Chain**: solana
- **Primary contract**: `solana:defillama:pacifica-perps`
- **TVL**: $30.0M (30,012,724)
- **Age**: 8mo (first seen 2025-09-08)
- **Languages**: rust

## Reproducible build (OtterSec)

- **Status**: — Not registered in OtterSec
  - This is the default for most Solana programs (<20% are registered). NOT a red flag — but you cannot trust that the github_repo matches the deployed bytecode byte-for-byte without running `solana-verify` yourself.

## Audit history

- **Audit density score**: 2 (already audited)
- **DefiLlama audit count**: 2 (from /protocol/pacifica-perps detail)
- Sources found:
  - `defillama` (1pt): https://docs.pacifica.fi/other/audits
  - `defillama` (1pt): DefiLlama audit (no link)

## Priority breakdown

- **Composite**: 5.63 / 10
  - tvl: 10.0 × 0.25
  - freshness: 2.9 × 0.20
  - audit_gap: 6.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Real money at stake ($30,012,724 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on pacifica-perps at ~/audit/2026-05-26-pacifica-perps/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
