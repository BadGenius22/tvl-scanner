# tvl-scanner roadmap

Improvements planned after the v0.4.1 + post-fix scans surfaced two
classes of false positives:

1. **JagPool Staked SOL** ranked #1 with $63M claimed TVL. Deep-dive
   verification showed it's a thin deployment of the `spl-stake-pool`
   program (3 prior audits, no custom code) with **0.109 jagSOL** in
   actual on-chain supply (~$0.15 USD). DefiLlama TVL was off by
   ~400,000x.
2. **SushiSwap (Arbitrum)** ranked #9 with `$244K, 0d old`. It's a
   brand-new SushiSwap pair — i.e. a deployment of the standard
   Uniswap-V2-fork pair contract — not a fresh protocol.

Both protocols passed every check the scanner does. Both should not have
been in the top 20. The fundamental gap is that the scanner reads
**secondary aggregators** (DefiLlama, GitHub, Etherscan, OtterSec) and
never **cross-checks against ground truth** (on-chain account state,
deployed bytecode, the protocol's own homepage statements).

The roadmap below ranks four batches by ROI. Recommended order is J → K,
then optionally L and M.

---

## Batch J — On-chain ground truth checks ★ MUST DO

**Three deterministic, mechanical filters with zero ongoing API cost.**
Catches both v0.4.1 false positives.

### J1 — Known-wrapper Solana program registry

For each Solana candidate, query `getAccountInfo` on the primary contract
and check the `owner` field against a curated registry of known wrapper
programs.

**Files**:
- New: `src/tvl_scanner/data/solana_wrapper_programs.yaml`
- New: `src/tvl_scanner/enrich/solana_wrapper_check.py`
- Modify: `src/tvl_scanner/audit_check/score.py` (add wrapper source)
- Modify: `src/tvl_scanner/enrich/defillama_protocols.py` (call check)

**Curated registry seed** (`data/solana_wrapper_programs.yaml`):
```yaml
- program_id: SPoo1Ku8WFXoNDMHPsrGSTSG1Y47rzgn41SLUNakuHy
  name: SPL Stake Pool
  audit_count: 3
  audit_url: https://spl.solana.com/stake-pool#security-audits
  description: Solana Foundation native stake pool program
- program_id: MarBmsSgKXdrN1egZf5sqe1TMThczhMLJhrhdwbsxLQ
  name: Marinade Liquid Staking
  audit_count: 5
  audit_url: https://marinade.finance/security
- program_id: Stake11111111111111111111111111111111111111
  name: Native Solana Stake
  audit_count: 99
  audit_url: https://github.com/solana-labs/solana
# ... etc
```

**Behavior on match**:
1. Add a synthetic `AuditSource` of kind `WRAPPER_PROGRAM` with the
   wrapper's audit count and URL as evidence
2. Force `audit_density_score` to at least the wrapper's audit count
3. Force `under_audited = false`
4. Add a focus area: *"Wrapper deployment of {wrapper_name} — no novel
   smart-contract attack surface. Audit value (if any) is in their
   fee/admin config and validator selection logic, not the on-chain
   code."*
5. Demote priority via the audit_gap_score path (~2.4 point drop)

**Cost**: ~50 lines of Python + ~30 entries in the YAML seed file +
1 RPC call per Solana candidate per scan. Zero ongoing API cost beyond
existing Alchemy quota.

**Catches**: JagPool, JPool, BlazeStake, Cogent, Edgevana, every other
SPL stake pool deployment. Marinade derivatives. Native staking pools.

### J2 — On-chain TVL sanity check for LSTs

For each Solana candidate with category `Liquid Staking` /
`Liquid Restaking` / `Staking Pool`, fetch the LST token mint supply
via `getTokenSupply` and compute:

```python
on_chain_tvl_usd = lst_supply * native_token_price_usd
if defillama_tvl > 10 * on_chain_tvl_usd:
    log.warning(
        f"{candidate.display_name}: DefiLlama TVL ${defillama_tvl:,} "
        f"contradicts on-chain ${on_chain_tvl_usd:,}, overriding"
    )
    candidate.tvl_usd = on_chain_tvl_usd
    # Add a note to focus_areas_suggested
```

**LST mint resolution**: needs a mapping from protocol slug → mint
address. Two options:
- (a) Curated `data/solana_lst_mints.yaml` similar to bounty_registry
- (b) Heuristic: query the stake pool account, decode the SPL stake
  pool layout, extract `pool_mint` field at known offset

Start with (a) for the top ~20 known LSTs, expand later if needed.

**Files**:
- New: `src/tvl_scanner/data/solana_lst_mints.yaml`
- Modify: `src/tvl_scanner/enrich/defillama_protocols.py`

**Cost**: ~20 lines + 1 RPC call per LST + small YAML registry.

**Catches**: JagPool's $63M phantom TVL → $0.15 actual. Any other
DefiLlama LST mis-listings.

### J3 — EVM factory pattern detection via bytecode hash

For each EVM pool-based candidate (those discovered via GeckoTerminal /
Birdeye), query `eth_getCode` on the contract address, hash the bytecode
with keccak256, and check against a registry of known factory output
hashes:

```yaml
- bytecode_hash: 0xa9a4...   # Uniswap V2 Pair
  name: Uniswap V2 Pair
  upstream_protocol: uniswap-v2
  audit_count: 3
- bytecode_hash: 0xe21f...   # Uniswap V3 Pool (immutable singleton init)
  name: Uniswap V3 Pool
  upstream_protocol: uniswap-v3
  audit_count: 5
- bytecode_hash: 0x...        # Curve metapool
  ...
```

Note: V3-style pool bytecode is identical across all pool instances
because the factory deploys with `CREATE2` from a fixed init code. V2
pairs are also identical. So a single hash per protocol covers all
pools.

**Files**:
- New: `src/tvl_scanner/data/evm_pool_bytecode_hashes.yaml`
- New: `src/tvl_scanner/enrich/evm_bytecode_check.py`
- Modify: `src/tvl_scanner/discover/merge.py` (call check at dedup time)

**Cost**: ~50 lines + 1 RPC call per EVM pool candidate + a small
bytecode hash registry.

**Catches**: SushiSwap pair pools (the v0.4.1 #9 false positive), all
Uniswap V2/V3/V4 pools, Curve gauges, Balancer pools, Aave aTokens,
Compound cTokens.

**Total Batch J cost**: ~120 lines of Python + 3 small YAML data files +
~30 extra RPC calls per scan + zero ongoing API cost. Catches both
classes of false positives in the v0.4.1 top 20.

---

## Batch K — Protocol homepage scraping ★ medium ROI

For top-N candidates after Batch J/K filtering (default N=30), fetch the
protocol's homepage URL (DefiLlama provides it as `url` in the detail
endpoint) and run regex/keyword extraction on the rendered HTML.

**Files**:
- New: `src/tvl_scanner/enrich/homepage_scrape.py`
- Modify: `src/tvl_scanner/enrich/defillama_protocols.py` (top-N
  post-process step)

**Pattern catalog**:
```python
WRAPPER_PHRASES = {
    r"native stake pool program": "spl_stake_pool",
    r"fork of (Aave|aave)": "aave_fork",
    r"based on (Uniswap V[34]|uniswap-v[34])": "uniswap_v3_fork",
    r"powered by (Compound|compound)": "compound_fork",
    r"built on (Morpho|morpho)": "morpho_layer",
    r"fork of (GMX|gmx)": "gmx_fork",
}
AUDIT_PHRASES = {
    r"audited by (Trail of Bits|TOB)": "trail_of_bits",
    r"audited by (Halborn)": "halborn",
    r"audited by (Zellic)": "zellic",
    r"audited by (ChainSecurity)": "chain_security",
    r"audited by (OpenZeppelin|OZ)": "openzeppelin",
    r"audited by (Cyfrin)": "cyfrin",
    r"audited by (Hexens)": "hexens",
    r"audited by (Spearbit)": "spearbit",
    r"audited by (Quantstamp)": "quantstamp",
}
```

Each match has a known meaning that affects scoring:
- Wrapper phrase match → demote, attribute audits to upstream
- Audit phrase match → add `AuditSource(BOUNTY_TRUST | DOCS_MENTION)`
  with weight 4 each, push above under_audited threshold

**Cost**: 1 HTTPS fetch per top-N candidate (~30 fetches per scan),
regex matching, ~80 lines of code. Adds 5-10 seconds to scan time.

**Catches**: Hyperlane (their docs site says "audited by Trail of Bits,
Halborn, Zellic"). Most fork protocols. Every protocol that explicitly
cites architecture or auditors in their marketing copy.

**Doesn't catch**: protocols whose website doesn't make architectural
claims, or whose audit info is on a separate page or PDF.

---

## Batch L — LLM-augmented candidate briefs ★ highest quality, API cost

For top-10 candidates after Batch J/K filtering, send a Haiku-class LLM
call with:
- The protocol's homepage HTML (truncated to ~10K chars)
- The protocol's docs index page
- The github README if available

Ask for a structured JSON brief:

```json
{
  "is_custom_code": false,
  "underlying_protocol_or_program": "spl-stake-pool",
  "real_tvl_estimate_usd": 0,
  "real_tvl_evidence": "on-chain jagSOL supply is 0.109",
  "audit_history_summary": "underlying SPL program has 3 audits; team has shipped no novel code",
  "audit_value_for_solo_hunter": "skip",
  "reasoning": "JagPool is a thin deployment of Solana Foundation's spl-stake-pool program. No novel smart-contract attack surface. Their innovation is off-chain validator scoring, not auditable code.",
  "specific_focus_if_audited": null
}
```

Replace the per-candidate file's "Suggested focus areas" section with
this LLM-generated brief.

**Files**:
- New: `src/tvl_scanner/enrich/llm_brief.py`
- Modify: `src/tvl_scanner/rank/report.py` (use LLM brief if present)

**Cost**:
- Haiku call: ~$0.001-0.005 per candidate via Anthropic API
- 10 candidates × 6 scans/month = ~$0.30/month
- Adds ~5-10 seconds per scan
- Requires ANTHROPIC_API_KEY in pass

**Catches**: everything J and K catch, plus subtle architectural insights
that regex can't capture. Example: *"this vault has user funds deposited
into Pendle Principal Tokens with auto-rollover at maturity, so the real
attack surface is at the Pendle PT integration boundary, not in the
vault's own Solidity"* — an LLM understands that. A regex doesn't.

---

## Batch M — Solodit integration ★ closes the private-audit gap

The original Batch D rescope. Try to scrape Solodit's actual public
search by reverse-engineering their frontend API or scraping the search
results page.

**Why this matters**: Solodit aggregates findings from 100+ audit firms
including all the private ones (Trail of Bits, Halborn, Zellic,
ChainSecurity, OpenZeppelin, Hexens, Cyfrin) — exactly the gap that
hides Hyperlane-class protocols from our current sources.

**Risk**: Solodit doesn't have a documented public API. Any scraper is
fragile and may break when they change their frontend. Potentially needs
maintenance every few months.

**Files**:
- New: `src/tvl_scanner/audit_check/solodit.py`
- Modify: `src/tvl_scanner/audit_check/checker.py` (call solodit.search)

**Cost**: 1-2 days of investigation + ~80 lines of code + ongoing
maintenance.

**Catches**: Hyperlane's actual audit history. Same for any other
protocol whose audits are private but whose findings made it into
Solodit.

---

## Recommended order

| Order | Batch | Rationale |
|---|---|---|
| 1 | **J** | Mechanical, deterministic, zero ongoing cost. Catches both v0.4.1 false positives. The obvious must-do. |
| 2 | **K** | Cheap (single HTTP fetch per top candidate), uses existing httpx stack, catches Hyperlane-class private-audit signal that J misses. |
| 3 | **L** | High-quality but has API cost and complexity. Defer until you've used the scanner on a few real audits and want polished briefs. |
| 4 | **M** | Highest-effort, most fragile. Defer unless you specifically want the private-audit gap closed and J/K aren't catching enough. |

## Success criteria for "the scanner produces deep-dive quality output"

After J + K + L, the per-candidate file for JagPool should look like:

```markdown
# JagPool Staked SOL

> SPL Stake Pool wrapper deployment — SKIP. No novel attack surface,
> on-chain TVL is $0.15 (DefiLlama is reporting wrong by 400,000x).

## Architecture
- Custom code: NO
- Underlying program: spl-stake-pool (`SPoo1Ku8...`)
- Audit history: 3 prior audits via Solana Foundation
- Real TVL: $0.15 (on-chain verified, DefiLlama claims $63M)

## Verdict for solo hunter: SKIP
Wrapper of audited SPL program. No code attack surface. No real money.
```

That's the bar.
