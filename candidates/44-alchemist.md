---
target_name: alchemist
display_name: Alchemist
protocol_type: Yield on ethereum
languages:
- solidity
chains:
- ethereum
inferred_platform: private
inferred_mode: private
audit_density_score: 0
audit_sources_found: []
under_audited: true
audited_by_me: '2026-05-28'
audit_outcome: '1 Low + 4 Info. Alchemist is the Crucible NFT-vault + Aludel staking architecture (port of Ampleforth Geyser pattern). 23 Aludel instances deployed via factory 0xF016fa84D5f3a252409a63b5cb89B555A0d27Ccf. KEY FINDING: 1 of 23 Aludels is v1 (vulnerable) — 0xf0d415189949d913264a454f57f4279ad66cb24d. The v1 unstakeAndClaim(vault, recipient, amount, permission) has recipient as caller-supplied parameter NOT bound by the unlock signature (which only binds delegate/token/amount/nonce per UNLOCK_TYPEHASH). MEV bots front-running an unstake tx in the mempool can substitute recipient → steal accumulated rewards. Staking tokens are safe (unlock to Crucible owned by user via NFT) — only rewards leak. Vulnerable Aludel holds 2.887 WETH (~$10K) in reward pool with 2,095 UNI-V2 MIST/WETH LP locked. Active 2026-04-30. Alchemist team SILENTLY FIXED in v2 by removing recipient parameter (22 of 23 Aludels are v2 = fixed). Under user filter ($10K exposure → Low). M-29 DETECTOR FALSE NEGATIVE: Crucible uses Geyser naming (lock/unlock/getPermissionHash) not Squid naming (executeOnBehalf) — proposed v1.17 extension in I-01.'
real_onchain_tvl_usd: 240624
real_onchain_tvl_source: 'RewardPoolFactory.instanceCount() = 23. Per-instance getAludelData() decoded for staking + reward token + totalStake. Sample: vulnerable Aludel holds 2,095 UNI-V2 MIST/WETH LP. DefiLlama TVL $240,624 matches on-chain (multi-Aludel LP stakes priced by Uniswap reserves).'
github_repo_actual: 'github.com/alchemistcoin (org). Aludel/Crucible verified on Sourcify (full match).'
findings:
  - id: L-01
    severity: Low
    title: Aludel v1 unstakeAndClaim reward recipient not bound by signature → MEV redirect
    affected: '0xf0d415189949d913264a454f57f4279ad66cb24d (1 of 23)'
    exposure_usd: 10100
edge_match_keywords: []
focus_areas_suggested:
- No prior audits found in any source — start with standard sanity pass before specialized
  depth
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 257094.91602445985
first_seen: '2025-11-27'
age_days: 180
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: ethereum:defillama:alchemist
priority_score: 5.28
why_interesting: Yield on ethereum • $257,094 TVL • 180d old • no prior audits found
scan_date: '2026-05-26'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 0
defillama_audit_note: null
---

# Alchemist

> Yield on ethereum • $257,094 TVL • 180d old • no prior audits found

## Summary

- **Chain**: ethereum
- **Primary contract**: `ethereum:defillama:alchemist`
- **TVL**: $257K (257,094)
- **Age**: 6mo (first seen 2025-11-27)
- **Languages**: solidity

## Audit history

- **Audit density score**: 0 (under-audited)
- **DefiLlama audit count**: 0 (from /protocol/alchemist detail)
- **No audits found** in any checked source.

## Priority breakdown

- **Composite**: 5.28 / 10
  - tvl: 2.0 × 0.25
  - freshness: 5.1 × 0.20
  - audit_gap: 10.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- No prior audits found in any source — start with standard sanity pass before specialized depth

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on alchemist at ~/audit/2026-05-26-alchemist/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
