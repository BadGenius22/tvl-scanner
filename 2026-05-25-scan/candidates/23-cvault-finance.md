---
target_name: cvault-finance
display_name: cVault Finance
protocol_type: Yield on ethereum
languages:
- solidity
chains:
- ethereum
inferred_platform: private
inferred_mode: private
audit_density_score: 2
audit_sources_found:
- source: defillama
  url: https://arcadiamgroup.com/audits/CoreFinal.pdf
  title: null
  published_at: null
- source: defillama
  url: null
  title: DefiLlama audit (no link)
  published_at: null
under_audited: false
edge_match_keywords:
- vault
focus_areas_suggested:
- Audit share/asset conversion math carefully; first-depositor share inflation is
  common in vault patterns
- Real money at stake ($5,630,401 TVL) — favor impact-driven finding scoping
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 5630401.84616998
first_seen: '2025-11-26'
age_days: 180
unique_users_30d: null
github_repo: https://github.com/cVault-finance/CORE-periphery
loc_estimate: 5490
docs_url: null
primary_contract: ethereum:defillama:cvault-finance
priority_score: 6.25
why_interesting: 'Yield on ethereum • $5,630,401 TVL • 180d old • ~5490 LOC • audit_density=2
  • edge-match: vault'
scan_date: '2026-05-25'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 2
defillama_audit_note: null
---

# cVault Finance

> Yield on ethereum • $5,630,401 TVL • 180d old • ~5490 LOC • audit_density=2 • edge-match: vault

## Summary

- **Chain**: ethereum
- **Primary contract**: `ethereum:defillama:cvault-finance`
- **TVL**: $5.6M (5,630,401)
- **Age**: 6mo (first seen 2025-11-26)
- **LOC estimate**: ~5,490
- **GitHub**: https://github.com/cVault-finance/CORE-periphery
- **Languages**: solidity

## Audit history

- **Audit density score**: 2 (already audited)
- **DefiLlama audit count**: 2 (from /protocol/cvault-finance detail)
- Sources found:
  - `defillama` (1pt): https://arcadiamgroup.com/audits/CoreFinal.pdf
  - `defillama` (1pt): DefiLlama audit (no link)

## Priority breakdown

- **Composite**: 6.25 / 10
  - tvl: 8.8 × 0.25
  - freshness: 5.1 × 0.20
  - audit_gap: 6.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 5.0 × 0.10 (keywords: vault)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Audit share/asset conversion math carefully; first-depositor share inflation is common in vault patterns
- Real money at stake ($5,630,401 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on cvault-finance at ~/audit/2026-05-25-cvault-finance/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
