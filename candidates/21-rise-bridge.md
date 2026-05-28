---
target_name: rise-bridge
display_name: RISE Bridge
protocol_type: Bridge on ethereum
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
audit_outcome: 'CLEAN under filter (0 Critical/High/Med, 1 Low, 6 Informational). Bridge is OptimismPortal2 v5.1.1 (canonical, audited) + RISE-specific OPSuccinctFaultDisputeGame (GameType 42) using Succinct SP1 ZK proofs + AccessManager (130 LOC). Novel first-party code is only ~808 LOC. SP1 proof binding correctly includes all claim parameters in public inputs. L-01: asymmetric permissionless fallback — proposing becomes permissionless after 14d silence; challenging never does. Combined with Unchallenged→DEFENDER_WINS (no proof for unchallenged claims), creates multi-precondition attack window IF both operator and whitelisted challengers go offline. Stage 0 permissioned bridge by design. Live state probed: maxChallenge=24h, maxProve=7d, finality=3.5d, FALLBACK_TIMEOUT=14d, challengerBond=250 Gwei (~$0.0009). Real TVL: 54.23 ETH = $109K-$190K depending on ETH price.'
real_onchain_tvl_usd: 109787
real_onchain_tvl_source: 'RPC eth_getBalance on 0xad92Fa18EB74E46Db844240623124BF46589db4C = 54.229504 ETH. ETH-only bridge (no ERC-20 holdings). At $2025/ETH (DefiLlama assumption) = $109,787. At $3500/ETH = $189,803. Matches DefiLlama precisely with their ETH price.'
proxy_impl_address: '0x7cf803296662e8c72a6c1d6450572209acf7f202'
contract_name: 'OptimismPortal2'
compiler_version: 'v0.8.15+commit.e14f2714'
github_repo_actual: 'Canonical Optimism: github.com/ethereum-optimism/optimism. RISE-specific OPSuccinctFaultDisputeGame: github.com/succinctlabs/op-succinct'
edge_match_keywords: []
focus_areas_suggested:
- Brand-new contract (34d old) — check initialization racing, first-caller bootstrap
  invariants
- No prior audits found in any source — start with standard sanity pass before specialized
  depth
bounty_program: none
bounty_url: null
bounty_max_payout_usd: null
tvl_usd: 115055.38692837936
first_seen: '2026-04-22'
age_days: 34
unique_users_30d: null
github_repo: null
loc_estimate: null
docs_url: null
primary_contract: ethereum:defillama:rise-bridge
priority_score: 5.64
why_interesting: Bridge on ethereum • $115,055 TVL • 34d old • no prior audits found
scan_date: '2026-05-26'
is_verified: null
contract_name: null
is_proxy: false
proxy_impl_address: null
compiler_version: null
defillama_audit_count: 0
defillama_audit_note: null
---

# RISE Bridge

> Bridge on ethereum • $115,055 TVL • 34d old • no prior audits found

## Summary

- **Chain**: ethereum
- **Primary contract**: `ethereum:defillama:rise-bridge`
- **TVL**: $115K (115,055)
- **Age**: 1mo (first seen 2026-04-22)
- **Languages**: solidity

## Audit history

- **Audit density score**: 0 (under-audited)
- **DefiLlama audit count**: 0 (from /protocol/rise-bridge detail)
- **No audits found** in any checked source.

## Priority breakdown

- **Composite**: 5.64 / 10
  - tvl: 0.3 × 0.25
  - freshness: 9.1 × 0.20
  - audit_gap: 10.0 × 0.30
  - activity: 5.0 × 0.15
  - edge_match: 0.0 × 0.10 (keywords: none)
  - bounty: 0.0 × 0.10

## Suggested focus areas

- Brand-new contract (34d old) — check initialization racing, first-caller bootstrap invariants
- No prior audits found in any source — start with standard sanity pass before specialized depth

## Vault handoff (Phase 2a)

To audit this candidate, say to Claude Code:

> `new audit on rise-bridge at ~/audit/2026-05-26-rise-bridge/`

Stage A will read this file, lift the YAML frontmatter fields into VAULT_CONTEXT.md (sections 1/2/6/7), grep the vault for applicable patterns and case studies (sections 3/4), and propose the full file per Phase 2a safety gates.
