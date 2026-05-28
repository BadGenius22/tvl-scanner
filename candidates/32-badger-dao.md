---
target_name: badger-dao
display_name: Badger DAO
protocol_type: Yield Aggregator on ethereum
languages:
- solidity
chains:
- ethereum
inferred_platform: private
inferred_mode: private
audit_density_score: 3
audit_sources_found:
- source: defillama
  url: https://badger.finance/wp-content/uploads/2021/01/HAECHI-AUDIT-BadgerDAO-Smart-Contract-Audit-Report-1.pdf
  title: null
  published_at: null
- source: defillama
  url: https://code4rena.com/contests/2022-06-badger-vested-aura-contest/
  title: null
  published_at: null
- source: defillama
  url: https://github.com/Badger-Finance/badger-vaults-1.5/blob/main/security/audits/Badger%20Vaults%201.5%20-%20Quantstamp%20-%20Jan%202022.pdf
  title: null
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- Real money at stake ($9,775,895 TVL) — favor impact-driven finding scoping
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 9775895.126276793
first_seen: '2025-11-27'
age_days: 180
unique_users_30d: null
github_repo: https://github.com/Badger-Finance/badger-legacy-sunset
loc_estimate: 0
docs_url: null
primary_contract: ethereum:defillama:badger-dao
priority_score: 5.45
why_interesting: Yield Aggregator on ethereum • $9,775,895 TVL • 180d old • audit_density=3
scan_date: '2026-05-26'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 2
defillama_audit_note: null
---

# Badger DAO

> Yield Aggregator on ethereum • $9,775,895 TVL • 180d old • audit_density=3

## Summary

- **Chain**: ethereum
- **Primary contract**: `ethereum:defillama:badger-dao`
- **TVL**: $9.8M (9,775,895)
- **Age**: 6mo (first seen 2025-11-27)
- **GitHub**: https://github.com/Badger-Finance/badger-legacy-sunset
- **Languages**: solidity

## Audit history

- **Audit density score**: 3 (already audited)
- **DefiLlama audit count**: 2 (from /protocol/badger-dao detail)
- Sources found:
  - `defillama` (1pt): https://badger.finance/wp-content/uploads/2021/01/HAECHI-AUDIT-BadgerDAO-Smart-Contract-Audit-Report-1.pdf
  - `defillama` (1pt): https://code4rena.com/contests/2022-06-badger-vested-aura-contest/
  - `defillama` (1pt): https://github.com/Badger-Finance/badger-vaults-1.5/blob/main/security/audits/Badger%20Vaults%201.5%20-%20Quantstamp%20-%20Jan%202022.pdf

## Priority breakdown

- **Composite**: 5.45 / 10
  - tvl: 9.9 × 0.25
  - freshness: 5.1 × 0.20
  - audit_gap: 4.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Real money at stake ($9,775,895 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on badger-dao at ~/audit/2026-05-26-badger-dao/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
