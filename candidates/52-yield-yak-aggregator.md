---
target_name: yield-yak-aggregator
display_name: Yield Yak Aggregator
protocol_type: Yield Aggregator on arbitrum
languages:
- solidity
chains:
- arbitrum
inferred_platform: immunefi
inferred_mode: bug-bounty
audit_density_score: 46
audit_sources_found:
- source: bounty_trust
  url: https://immunefi.com/bounty/yieldyak/
  title: Trusted via immunefi bounty (max $100,000) — bounty platforms vet protocols
    against audit reports during onboarding
  published_at: null
- source: code4rena
  url: https://github.com/code-423n4/2022-06-yieldy
  title: code-423n4/2022-06-yieldy
  published_at: null
- source: code4rena
  url: https://github.com/code-423n4/2022-07-yield
  title: code-423n4/2022-07-yield
  published_at: null
- source: code4rena
  url: https://github.com/code-423n4/2021-05-yield
  title: code-423n4/2021-05-yield
  published_at: null
- source: code4rena
  url: https://github.com/code-423n4/2021-08-yield
  title: code-423n4/2021-08-yield
  published_at: null
- source: code4rena
  url: https://github.com/code-423n4/2022-01-yield
  title: code-423n4/2022-01-yield
  published_at: null
- source: code4rena
  url: https://github.com/code-423n4/2022-01-yield-findings
  title: code-423n4/2022-01-yield-findings
  published_at: null
- source: code4rena
  url: https://github.com/code-423n4/2021-05-yield-findings
  title: code-423n4/2021-05-yield-findings
  published_at: null
- source: code4rena
  url: https://github.com/code-423n4/2022-06-yieldy-findings
  title: code-423n4/2022-06-yieldy-findings
  published_at: null
- source: code4rena
  url: https://github.com/code-423n4/2021-08-yield-findings
  title: code-423n4/2021-08-yield-findings
  published_at: null
- source: code4rena
  url: https://github.com/code-423n4/2022-07-yield-findings
  title: code-423n4/2022-07-yield-findings
  published_at: null
- source: sherlock
  url: https://github.com/sherlock-audit/2025-02-yieldoor
  title: sherlock-audit/2025-02-yieldoor
  published_at: null
- source: sherlock
  url: https://github.com/sherlock-audit/2025-07-allbridge-core-yield
  title: sherlock-audit/2025-07-allbridge-core-yield
  published_at: null
- source: sherlock
  url: https://github.com/sherlock-audit/2025-02-yieldoor-judging
  title: sherlock-audit/2025-02-yieldoor-judging
  published_at: null
- source: sherlock
  url: https://github.com/sherlock-audit/2025-07-allbridge-core-yield-judging
  title: sherlock-audit/2025-07-allbridge-core-yield-judging
  published_at: null
under_audited: false
edge_match_keywords: []
focus_areas_suggested:
- Real money at stake ($15,651,333 TVL) — favor impact-driven finding scoping
bounty_program: immunefi
bounty_url: https://immunefi.com/bounty/yieldyak/
bounty_max_payout_usd: 100000
tvl_usd: 15651333.24270837
first_seen: '2025-11-27'
age_days: 180
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: arbitrum:defillama:yield-yak-aggregator
priority_score: 5.26
why_interesting: 'Yield Aggregator on arbitrum • $15,651,333 TVL • 180d old • audit_density=46
  • bounty: immunefi'
scan_date: '2026-05-26'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 0
defillama_audit_note: null
---

# Yield Yak Aggregator

> Yield Aggregator on arbitrum • $15,651,333 TVL • 180d old • audit_density=46 • bounty: immunefi

## Summary

- **Chain**: arbitrum
- **Primary contract**: `arbitrum:defillama:yield-yak-aggregator`
- **TVL**: $15.7M (15,651,333)
- **Age**: 6mo (first seen 2025-11-27)
- **Languages**: solidity

## Bounty program

- **Platform**: immunefi
- **URL**: https://immunefi.com/bounty/yieldyak/
- **Max payout**: $100,000

## Audit history

- **Audit density score**: 46 (already audited)
- **DefiLlama audit count**: 0 (from /protocol/yield-yak-aggregator detail)
- Sources found:
  - `bounty_trust` (4pt): Trusted via immunefi bounty (max $100,000) — bounty platforms vet protocols against audit reports during onboarding
  - `code4rena` (3pt): code-423n4/2022-06-yieldy
  - `code4rena` (3pt): code-423n4/2022-07-yield
  - `code4rena` (3pt): code-423n4/2021-05-yield
  - `code4rena` (3pt): code-423n4/2021-08-yield
  - `code4rena` (3pt): code-423n4/2022-01-yield
  - `code4rena` (3pt): code-423n4/2022-01-yield-findings
  - `code4rena` (3pt): code-423n4/2021-05-yield-findings
  - `code4rena` (3pt): code-423n4/2022-06-yieldy-findings
  - `code4rena` (3pt): code-423n4/2021-08-yield-findings
  - `code4rena` (3pt): code-423n4/2022-07-yield-findings
  - `sherlock` (3pt): sherlock-audit/2025-02-yieldoor
  - `sherlock` (3pt): sherlock-audit/2025-07-allbridge-core-yield
  - `sherlock` (3pt): sherlock-audit/2025-02-yieldoor-judging
  - `sherlock` (3pt): sherlock-audit/2025-07-allbridge-core-yield-judging

## Priority breakdown

- **Composite**: 5.26 / 10
  - tvl: 10.0 × 0.25
  - freshness: 5.1 × 0.20
  - audit_gap: 0.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 10.0 × 0.10

## Suggested focus areas

- Real money at stake ($15,651,333 TVL) — favor impact-driven finding scoping

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on yield-yak-aggregator at ~/audit/2026-05-26-yield-yak-aggregator/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
