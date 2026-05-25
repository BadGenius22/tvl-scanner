---
target_name: zama
display_name: Zama
protocol_type: Privacy on ethereum
languages:
- solidity
chains:
- ethereum
inferred_platform: private
inferred_mode: private
audit_density_score: 4
audit_sources_found:
- source: factory_attribution
  url: null
  title: Name 'zama' matches known audited protocol family — audit attribution by
    name
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- Brand-new contract (20d old) — check initialization racing, first-caller bootstrap
  invariants
- Real money at stake ($32,350,783 TVL) — favor impact-driven finding scoping
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 32350783.50884099
first_seen: '2026-05-05'
age_days: 20
unique_users_30d: null
github_repo: https://github.com/zama-ai/fhevm
loc_estimate: 1192255
docs_url: null
primary_contract: ethereum:defillama:zama
priority_score: 5.74
why_interesting: Privacy on ethereum • $32,350,783 TVL • 20d old • ~1192255 LOC •
  audit_density=4
scan_date: '2026-05-25'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 0
defillama_audit_note: null
---

# Zama

> Privacy on ethereum • $32,350,783 TVL • 20d old • ~1192255 LOC • audit_density=4

## Summary

- **Chain**: ethereum
- **Primary contract**: `ethereum:defillama:zama`
- **TVL**: $32.4M (32,350,783)
- **Age**: 20d (first seen 2026-05-05)
- **LOC estimate**: ~1,192,255
- **GitHub**: https://github.com/zama-ai/fhevm
- **Languages**: solidity

## Audit history

- **Audit density score**: 4 (already audited)
- **DefiLlama audit count**: 0 (from /protocol/zama detail)
- Sources found:
  - `factory_attribution` (4pt): Name 'zama' matches known audited protocol family — audit attribution by name

## Priority breakdown

- **Composite**: 5.74 / 10
  - tvl: 10.0 × 0.25
  - freshness: 9.4 × 0.20
  - audit_gap: 2.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Brand-new contract (20d old) — check initialization racing, first-caller bootstrap invariants
- Real money at stake ($32,350,783 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on zama at ~/audit/2026-05-25-zama/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
