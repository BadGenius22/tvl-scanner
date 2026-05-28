---
target_name: tramplin.io
display_name: tramplin.io
protocol_type: Staking Pool on solana
languages:
- rust
chains:
- solana
inferred_platform: private
inferred_mode: private
audit_density_score: 2
audit_sources_found:
- source: defillama
  url: https://github.com/mixbytes/audits_public/tree/master/Tramplin/Tramplin
  title: null
  published_at: null
- source: defillama
  url: null
  title: DefiLlama audit (no link)
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- Real money at stake ($13,731,784 TVL) — favor impact-driven finding scoping
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 13731784.671891676
first_seen: '2026-02-17'
age_days: 98
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: solana:defillama:tramplin.io
priority_score: 6.51
why_interesting: Staking Pool on solana • $13,731,784 TVL • 98d old • audit_density=2
scan_date: '2026-05-26'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 2
defillama_audit_note: null
---

# tramplin.io

> Staking Pool on solana • $13,731,784 TVL • 98d old • audit_density=2

## Summary

- **Chain**: solana
- **Primary contract**: `solana:defillama:tramplin.io`
- **TVL**: $13.7M (13,731,784)
- **Age**: 3mo (first seen 2026-02-17)
- **Languages**: rust

## Reproducible build (OtterSec)

- **Status**: — Not registered in OtterSec
  - This is the default for most Solana programs (<20% are registered). NOT a red flag — but you cannot trust that the github_repo matches the deployed bytecode byte-for-byte without running `solana-verify` yourself.

## Audit history

- **Audit density score**: 2 (already audited)
- **DefiLlama audit count**: 2 (from /protocol/tramplin.io detail)
- Sources found:
  - `defillama` (1pt): https://github.com/mixbytes/audits_public/tree/master/Tramplin/Tramplin
  - `defillama` (1pt): DefiLlama audit (no link)

## Priority breakdown

- **Composite**: 6.51 / 10
  - tvl: 10.0 × 0.25
  - freshness: 7.3 × 0.20
  - audit_gap: 6.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Real money at stake ($13,731,784 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on tramplin.io at ~/audit/2026-05-26-tramplin.io/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
