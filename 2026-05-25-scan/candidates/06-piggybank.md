---
target_name: piggybank
display_name: PiggyBank
protocol_type: Yield on solana
languages:
- rust
chains:
- solana
inferred_platform: private
inferred_mode: private
audit_density_score: 2
audit_sources_found:
- source: defillama
  url: https://cdn.prod.website-files.com/68e7628180c5b014e78a46cc/6900fa6f3a2659fab4c7b728_piggy_bank.pdf
  title: null
  published_at: null
- source: defillama
  url: null
  title: DefiLlama audit (no link)
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- Brand-new contract (5d old) — check initialization racing, first-caller bootstrap
  invariants
- Real money at stake ($5,352,131 TVL) — favor impact-driven finding scoping
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 5352131.180306718
first_seen: '2026-05-20'
age_days: 5
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: solana:defillama:piggybank
priority_score: 6.68
why_interesting: Yield on solana • $5,352,131 TVL • 5d old • audit_density=2
scan_date: '2026-05-25'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 2
defillama_audit_note: null
---

# PiggyBank

> Yield on solana • $5,352,131 TVL • 5d old • audit_density=2

## Summary

- **Chain**: solana
- **Primary contract**: `solana:defillama:piggybank`
- **TVL**: $5.4M (5,352,131)
- **Age**: 5d (first seen 2026-05-20)
- **Languages**: rust

## Reproducible build (OtterSec)

- **Status**: — Not registered in OtterSec
  - This is the default for most Solana programs (<20% are registered). NOT a red flag — but you cannot trust that the github_repo matches the deployed bytecode byte-for-byte without running `solana-verify` yourself.

## Audit history

- **Audit density score**: 2 (already audited)
- **DefiLlama audit count**: 2 (from /protocol/piggybank detail)
- Sources found:
  - `defillama` (1pt): https://cdn.prod.website-files.com/68e7628180c5b014e78a46cc/6900fa6f3a2659fab4c7b728_piggy_bank.pdf
  - `defillama` (1pt): DefiLlama audit (no link)

## Priority breakdown

- **Composite**: 6.68 / 10
  - tvl: 8.6 × 0.25
  - freshness: 9.9 × 0.20
  - audit_gap: 6.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Brand-new contract (5d old) — check initialization racing, first-caller bootstrap invariants
- Real money at stake ($5,352,131 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on piggybank at ~/audit/2026-05-25-piggybank/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
