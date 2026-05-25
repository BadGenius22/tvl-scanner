---
target_name: hypersurface
display_name: Hypersurface
protocol_type: Options on base
languages:
- solidity
chains:
- base
inferred_platform: private
inferred_mode: private
audit_density_score: 2
audit_sources_found:
- source: defillama
  url: https://github.com/AuditOne/audits/blob/main/Hypersurface/Hypersurface_A1_Audit.pdf
  title: null
  published_at: null
- source: defillama
  url: null
  title: DefiLlama audit (no link)
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- Real money at stake ($4,282,923 TVL) — favor impact-driven finding scoping
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 4282923.852502403
first_seen: '2026-01-29'
age_days: 116
unique_users_30d: null
github_repo: https://github.com/hypersurface-protocol/hyperclaim
loc_estimate: 59621
docs_url: null
primary_contract: base:defillama:hypersurface
priority_score: 5.95
why_interesting: Options on base • $4,282,923 TVL • 116d old • ~59621 LOC • audit_density=2
scan_date: '2026-05-25'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 2
defillama_audit_note: null
---

# Hypersurface

> Options on base • $4,282,923 TVL • 116d old • ~59621 LOC • audit_density=2

## Summary

- **Chain**: base
- **Primary contract**: `base:defillama:hypersurface`
- **TVL**: $4.3M (4,282,923)
- **Age**: 3mo (first seen 2026-01-29)
- **LOC estimate**: ~59,621
- **GitHub**: https://github.com/hypersurface-protocol/hyperclaim
- **Languages**: solidity

## Audit history

- **Audit density score**: 2 (already audited)
- **DefiLlama audit count**: 2 (from /protocol/hypersurface detail)
- Sources found:
  - `defillama` (1pt): https://github.com/AuditOne/audits/blob/main/Hypersurface/Hypersurface_A1_Audit.pdf
  - `defillama` (1pt): DefiLlama audit (no link)

## Priority breakdown

- **Composite**: 5.95 / 10
  - tvl: 8.2 × 0.25
  - freshness: 6.8 × 0.20
  - audit_gap: 6.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Real money at stake ($4,282,923 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on hypersurface at ~/audit/2026-05-25-hypersurface/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
