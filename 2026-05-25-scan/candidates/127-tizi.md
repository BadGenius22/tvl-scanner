---
target_name: tizi
display_name: Tizi
protocol_type: Yield Aggregator on base
languages:
- solidity
chains:
- base
inferred_platform: private
inferred_mode: private
audit_density_score: 1
audit_sources_found:
- source: defillama
  url: https://2781107368-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FlxAaGBCj8m8RA8EcZ25F%2Fuploads%2FEJb3Xu5zhoktjv1DRmti%2FTizi%20audit%20by%20Beosin.pdf?alt=media&token=738f8007-4817-4b9d-9709-697fcc6bd6a4
  title: null
  published_at: null
under_audited: true
edge_match_keywords: []
focus_areas_suggested:
- Brand-new contract (21d old) — check initialization racing, first-caller bootstrap
  invariants
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 121537.56011749642
first_seen: '2026-05-04'
age_days: 21
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: base:defillama:tizi
priority_score: 5.14
why_interesting: Yield Aggregator on base • $121,537 TVL • 21d old • audit_density=1
scan_date: '2026-05-25'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 0
defillama_audit_note: null
---

# Tizi

> Yield Aggregator on base • $121,537 TVL • 21d old • audit_density=1

## Summary

- **Chain**: base
- **Primary contract**: `base:defillama:tizi`
- **TVL**: $122K (121,537)
- **Age**: 21d (first seen 2026-05-04)
- **Languages**: solidity

## Audit history

- **Audit density score**: 1 (under-audited)
- **DefiLlama audit count**: 0 (from /protocol/tizi detail)
- Sources found:
  - `defillama` (1pt): https://2781107368-files.gitbook.io/~/files/v0/b/gitbook-x-prod.appspot.com/o/spaces%2FlxAaGBCj8m8RA8EcZ25F%2Fuploads%2FEJb3Xu5zhoktjv1DRmti%2FTizi%20audit%20by%20Beosin.pdf?alt=media&token=738f8007-4817-4b9d-9709-697fcc6bd6a4

## Priority breakdown

- **Composite**: 5.14 / 10
  - tvl: 0.4 × 0.25
  - freshness: 9.4 × 0.20
  - audit_gap: 8.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Brand-new contract (21d old) — check initialization racing, first-caller bootstrap invariants

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on tizi at ~/audit/2026-05-25-tizi/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
