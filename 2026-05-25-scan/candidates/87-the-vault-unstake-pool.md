---
target_name: the-vault-unstake-pool
display_name: The Vault Unstake Pool
protocol_type: Yield on solana
languages:
- rust
chains:
- solana
inferred_platform: private
inferred_mode: private
audit_density_score: 0
audit_sources_found: []
under_audited: true
edge_match_keywords:
- vault
focus_areas_suggested:
- Audit share/asset conversion math carefully; first-depositor share inflation is
  common in vault patterns
- No prior audits found in any source — start with standard sanity pass before specialized
  depth
- Real money at stake ($1,020,243 TVL) — favor impact-driven finding scoping
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 1020243.1689730539
first_seen: '2025-06-11'
age_days: 348
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: solana:defillama:the-vault-unstake-pool
priority_score: 5.6
why_interesting: 'Yield on solana • $1,020,243 TVL • 348d old • no prior audits found
  • edge-match: vault'
scan_date: '2026-05-25'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 0
defillama_audit_note: null
---

# The Vault Unstake Pool

> Yield on solana • $1,020,243 TVL • 348d old • no prior audits found • edge-match: vault

## Summary

- **Chain**: solana
- **Primary contract**: `solana:defillama:the-vault-unstake-pool`
- **TVL**: $1.0M (1,020,243)
- **Age**: 11mo (first seen 2025-06-11)
- **Languages**: rust

## Reproducible build (OtterSec)

- **Status**: — Not registered in OtterSec
  - This is the default for most Solana programs (<20% are registered). NOT a red flag — but you cannot trust that the github_repo matches the deployed bytecode byte-for-byte without running `solana-verify` yourself.

## Audit history

- **Audit density score**: 0 (under-audited)
- **DefiLlama audit count**: 0 (from /protocol/the-vault-unstake-pool detail)
- **No audits found** in any checked source.

## Priority breakdown

- **Composite**: 5.60 / 10
  - tvl: 5.0 × 0.25
  - freshness: 0.5 × 0.20
  - audit_gap: 10.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 5.0 × 0.10 (keywords: vault)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Audit share/asset conversion math carefully; first-depositor share inflation is common in vault patterns
- No prior audits found in any source — start with standard sanity pass before specialized depth
- Real money at stake ($1,020,243 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on the-vault-unstake-pool at ~/audit/2026-05-25-the-vault-unstake-pool/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
