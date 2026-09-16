# DeFi Attack Landscape Deep-Dive: June–August 2026

Root-cause and PoC analysis of the two dominant attack classes in the last quarter,
from the [DeFiHackLabs explorer](https://defihacklabs.io/explorer/index.html) incident
feed (917 records; 52 unique incidents in the Jun 16 – Aug 9 window) cross-referenced
against the actual Foundry PoCs in the
[DeFiHackLabs GitHub repo](https://github.com/SunWeb3Sec/DeFiHackLabs) (copied under
[`poc/`](./poc/)) and published post-mortems (Halborn, BlockSec, VeriChains, Asymmetric
Research, Aztec Labs, Bonzo Finance, Summer.fi, Olympix, SlowMist/PeckShield alerts).

**Window totals:** 52 deduplicated incidents, ~$110M USD-denominated losses. Attack
frequency ~6–7/week, peaking in July (33 of 57 raw listings). Ethereum (23) and
BSC/BNB Chain (17) dominate by count.

**Headline:** the two most frequent classes are (1) price/oracle/reserve manipulation
and (2) business-logic/accounting flaws — together ~65% of incidents. The single most
common concrete defect is *a protocol valuing assets at a price the attacker can move
in the same transaction*, amplified by zero-fee Morpho flash loans.

> Note on the PoC copies: the `.sol` files under `poc/` are verbatim from
> DeFiHackLabs `src/test/` and import `../basetest.sol` + forge-std — they will not
> compile standalone in this repo. Run them from a full DeFiHackLabs clone, e.g.
> `forge test --contracts ./src/test/2026-07/SummerFi_exp.sol -vvv`.

---

## 1. Corrections to the explorer's own labels

Deep-dive analysis reclassified several incidents; the tracker's category counts
shift accordingly.

| Explorer entry | Reality |
|---|---|
| Ostium "Price Manipulation" ($11.9M) | **Compromised oracle-signer key**, not price manipulation. Post-mortem puts the drain at **$23.75M** USDC. PriceUpKeep infra was outside bug-bounty scope. |
| "Hedera Protocol Exploitation" ($5.25M) + "BonzoLend Oracle Exploit" ($9.05M) | **Same incident**: Bonzo Lend on Hedera. $5.25M is the portion PeckShield saw bridged to Ethereum. |
| Lumi ($264k) + Sodium ($21k), both Arbitrum | **Same event family**: victims were Sodium ERC-4337 smart accounts. |
| AtlantisLoan, 2026-07-07, $931k | **Does not exist as a 2026 event.** Name/amount match the June 2023 BSC Atlantis Loans governance takeover. Excluded. |
| USM "Flash Loan + Pricing Logic Flaw" | Pure math bug — no price moved anywhere; flash loan only supplied capital. |
| Across ($3.6M) | No on-chain bug: the Risk Labs relayer's Solana indexer decoded events **without checking tx status**. |

Explorer dates are disclosure dates, not attack dates (Hinkal attacked Jul 2,
disclosed Jul 9; Across attacked Jul 17, listed Jul 28).

Also: the explorer JSON feed is stale at Aug 9 while the repo has PoCs through
Aug 31 — including the **Sandbox (SAND) LayerZero OFT campaign on Base** minting
~$49B face value of unbacked SAND across 400+ txs, absent from the explorer entirely.

---

## 2. Class A — Price / Oracle / Reserve Manipulation

### A1. "Read a price the attacker can move" (dominant family)

State-changing valuation paths (deposit/mint/borrow/redeem/claim) price assets from a
source an unprivileged caller can shift in-transaction. Manipulation guards, where
they exist, wrap only the *privileged* path.

**SummerFi FleetCommander — $6.02M** (`poc/2026-07/SummerFi_exp.sol`)
- Root cause: NAV = live sum of every Ark's `totalAssets()`, no manipulation guard;
  a paused/capped-for-removal Silo ark was still counted (incomplete offboarding);
  that ark's vgUSDC counted depegged Stream USD (xUSD) collateral **at par**.
- Flow: buy vgUSDC for pennies (USDT→xUSD on Uniswap V4, xUSD→vgUSDC on Balancer V3)
  → deposit ~$64.8M flash-loaned USDC at honest NAV → **donate** cheap vgUSDC into
  the near-empty ark → NAV inflates → redeem, draining all other LPs.
  `forceDeallocate` was used against four Morpho markets so the inflated redeem could
  be served; nested Morpho flash loans ($1M USDT outer, $65.4M USDC inner).
- Tx `0x0db528c44f23fc7fa4544684a2fab81096450a14aae8bc89f42cd0592d43da12`;
  setup tx `0x5d874634…067e0c`; attacker contract `0x0514f827…2fc61`.

**edel-xstock — $204k profit / $403k bad debt** (`poc/2026-07/edel-xstock_exp.sol`)
- Root cause: collateral priced via the wrapper's **mutable ERC-4626
  `convertToAssets()` rate** (Chainlink itself was fine — the pricing-source choice
  was the bug).
- Flow: $180k Morpho flash loan → ~40-deep recursive borrow/supply loop → donate
  underlying GOOGLx to the wrapper → rate inflates ~78x → borrow all remaining USDC
  + wSPYx/wQQQx/wMSTRx/wNVDAx/wTSLAx reserves.
- Tx `0xe2320086b2815d21b0927839bd0e306466c29a68d38d5361e99dd21ec5472612`.

**LpdFi — $693.5k**: `LPD.price()` read Pancake `getReserves()` live; interest claims
sized off it. Block 1: flash-swap to inflate LPD price, `buy()` ($140M paper
principal). Block 2: cross the "issue boundary", donate 3,440 USDC + `sync()`,
`claimInterest()` paid $693,529 against a 97%-of-supply LP burn.

**DLMC — $222.6k**: protocol `livePrice` derived from pair reserves; two buys through
a referral tree inflated it; sold max amount backed by protocol USDT (Pancake flash
swap financed).

**42DAO / Balance — $912k**: Maker-fork plumbing with zero sanity checks: manipulated
Median Oracle BTCB price → `Spotter.poke()` → VAT (no deviation check, no floor, no
liquidation delay) → `Dog` liquidated multiple BTCB vaults in-tx; BLC stablecoin
collapsed 99%+.

**Arrakis G-UNI (~2.9 ETH) + Float Protocol (~10.7 ETH)** (`poc/2026-08/ArrakisGUNI_exp.sol`,
`poc/2026-08/FloatProtocol_exp.sol`): LP shares valued at Uniswap V3 `slot0`
instantaneous price; TWAP/deviation guard existed **only on the manager `rebalance()`
path**, leaving permissionless mint/burn/deposit/withdraw naked. Push tick → mint at
skewed valuation → restore tick → burn for richer mix.

### A2. Token-behavior reserve corruption (BSC skim/sync family)

Small tickets, high frequency. Shared mechanic: quirky token + V2 pair; attacker moves
real balances while `sync()`/`skim()` launders the mismatch into official reserves.

- **OLPC — $1.1M** (`poc/2026-06/OLPC_exp.sol`): owner set mutable `decimalsValue` to
  `7326680472586200649`; dust transfers decayed pair balances massively; sync/skim
  loops + Pancake supporting-fee swap with `amountIn = 0` (input inferred from
  balance-over-reserve) released the pool's other side.
- **DIP — $111k** (`poc/2026-06/DIP_exp.sol`): fee-on-transfer + double
  router-transfer shrank the pair's DIP reserve via skim/sync.
- **LULA — $578k**: nastiest variant — privileged `recycle()` **pulled LULA directly
  out of the live Pancake pair then `sync()`**. 12 days of pre-accrued referral
  rewards bought authorization; ~$237M flash loan amplified; net $578k.
  Tx `0xa219ab9d…0411d7c`.
- **AIDC — 220 WBNB / AIC — $21.5k / RWT — $118k**: deflationary/FoT tokens that burn
  or tax **from the pair's reserves** on ordinary transfers; fresh helper contracts
  each cycle bypass per-address cooldowns.

### A3. Oracle-input corruption via broken signature verification

No price "manipulated" — the price *input* was forged:

- **Bonzo Lend (Hedera) — $9.05M**: Supra pull-oracle verifier accepted a BLS
  aggregate signature of **all-zero G1/G2 points** (pairing precompile truthfully
  returns `true` for identity-element pairings; no degenerate-input check). Deposit
  of 250 SAUCE (~$4.62) → price inflated ~12 orders of magnitude → borrowed 6.63M
  USDC + 34.5M WHBAR 8 seconds later. **No flash loan needed.**
- **Ostium — $23.75M**: compromised signer key; falsified future-dated prices
  (BTC ~$5k vs ~$60k); ~10 open/close loops at ~9x each.

---

## 3. Class B — Business-Logic / Accounting Bugs

### B1. ZK / proof-system invariant breaks (biggest single-ticket logic losses)

**Aztec V1 escape hatch — $2.2M** (`poc/2026-06/AztecEscapeHatch_exp.sol`, `_exp2.sol`)
- Soundness bug in the **verification key**: circuit hashed the Merkle root twice
  (membership root vs settlement root) and never checked they agree → attacker proved
  ownership against a *fabricated ledger* while settling against the real one
  (`deposit 0, withdraw 1,158 ETH` verified clean).
- Whitehat `exp2` documents a second flaw: **unconstrained `proof_id` witness**
  (`public_witness_ct` publishes but doesn't constrain) → publishing `proof_id = 1`
  skips Solidity deposit validation while the note is still minted.
- A third issue: a **default Anvil/Hardhat dev key left as authorized operator** on
  the decommissioned rollup — a copycat swept the remainder through the normal path.

**Hinkal — $800k**: legacy spend circuit nullifier `Poseidon2(commitment,
Poseidon2(nk, commitment))` did **not bind `nk` to the commitment** → different
`(e, nk')` pairs with the same product mint fresh nullifiers for the same note
(contract checked proofs/replay correctly; the one-note-one-nullifier rule lived
only in the circuit). Entry: `prooflessDeposit()` accepted legacy-format notes
unvalidated. $100 in → ~$800k out.

### B2. "One missing check" accounting breaks

- **Drips — $24.9k**: `give(uint128)` cast to `int128` unchecked → crafted amount
  goes negative → transfer direction inverts ("reserve pays the user").
  Tx `0xc38a6e22…34130`.
- **RoyalRoyalties — $261k** (`poc/2026-06/RoyalRoyalties_exp.sol`): ERC-1155 batch
  transfers with `amounts[i] == 0` still incremented per-tier balances → apparent
  100x ownership of a supply-1 tier → 100x royalty claim.
- **Ajna — $775k across 7 pools** (`poc/2026-08/AjnaFinance_exp.sol`): oracle-free by
  design; attacker controlled **both sides of a liquidation** (own borrower position
  + own bucket funding the take) → `bucketTake`→`removeCollateral`→`take`→`repayDebt`
  ordering walked out ~48 cbETH richer for ~3.5 WETH paid.
- **USM — 70.8 ETH** (`poc/2026-08/USM_exp.sol`): redemption curve averaged current +
  post-redemption prices and contracted state per call → **not split-invariant**:
  64 small `defund()` calls pay strictly more than one big one. Flash-loan
  11,580 WETH → `fund()` → 64 slices → repay, keep 70.8 ETH.
  Tx `0xfae5e751…b050e`.
- **Balancer V1 BPool (Aug 31)** (`poc/2026-08/BalancerV1BPool_exp.sol`): with the
  WBTC reserve compressed to dust, `calcSingleInGivenPoolOut` rounded required input
  down to one satoshi while minting full BPT — no minimum-effective-input check.
- **Vault4626 — 13.5 WETH** (`poc/2026-06/Vault4626_exp.sol`): `totalAssets()` quoted
  idle *non-asset* WETH into the share price and `redeem()` also paid that WETH out —
  double counting.
- **Ocean BPool — 128k mOCEAN** (`poc/2026-06/OceanBPoolSideStaking_exp.sol`):
  asymmetric join/exit math + SideStaking auto-mirroring single-sided joins +
  `gulp()` of stale reserves.

### B3. Signature validation gaps

- **Lixir — all holders drained (~$30k)** (`poc/2026-06/LixirPermitDrain_exp.sol`):
  permits accepted a **dummy signature as long as `ecrecover` returned nonzero**
  (zero-address check missing) → forged permits → full-balance withdrawals.
- **Lumi/Sodium — $264k**: Sodium ERC-4337 accounts: (1) type-`0x01` signature
  `0x01 || <attacker-contract> || 00` falls through ECDSA to ERC-1271 — and the
  UserOp names its own verifier contract; (2) `validateUserOp` had an **approval
  side effect** (untrusted `paymasterAndData` → `approve(type(uint256).max)`) and a
  zero `callGasLimit` made execution fail out-of-gas *without reverting the batch*,
  so the allowance persisted. Sweeper tx then `transferFrom`ed users' USDT0.

### B4. Arbitrary-call injection (the sleeper story)

- **Sandbox OFT (Base)** (`poc/2026-08/SandboxOFT_exp.sol`): `approveAndCall(target,
  amount, data)` = unvalidated `target.call(data)` → attacker registered as
  **delegate + DVN** in the LayerZero config → unbacked SAND mints, ~$49B face value
  across 400+ txs.
- **Unistreet Launchpad** (`poc/2026-08/UnistreetLaunchpad_exp.sol`): `launch()`
  forwarded caller calldata **verbatim** into the Uniswap V4 PositionManager *as the
  factory* → custodied LP positions drained.

### B5. Flash-liquidity-staged reward accounting

- **LBP — 610 BNB** (`poc/2026-06/LBP_exp.sol`): borrowed all visible USDT liquidity
  (Moolah + Pancake Vault), staged LP credit so reward accounting minted hLBP credit,
  harvested inflated LBP rewards, sold.
- **JB — $50k** (`poc/2026-06/JB_exp.sol`): unverified helper cycled the live JB
  balance through sell/burn/sync against the pair (flash WBNB → Venus collateral →
  70M USDT borrowed against it).

*(Across — $3.6M — sits between classes: off-chain indexer trusted events from
reverted transactions. 331.8 ETH (~17%) later returned.)*

---

## 4. The attack playbook (cross-cutting mechanics)

1. **Flash loans are capital logistics, never root cause.** Morpho Blue zero-fee
   flashLoan is the mainnet workhorse; Pancake pair flash-swaps on BSC; LULA borrowed
   ~$237M purely for amplification. Where sig verification was broken (Bonzo), no
   flash loan was needed at all.
2. **Donation is the standard inflation primitive** — donate tokens to a
   wrapper/ark/pair and let share math, `convertToAssets()`, or `sync()` launder it
   (edel-xstock, SummerFi, Vault4626, LpdFi, LULA).
3. **Multi-tx staging:** SummerFi pre-positioned vgUSDC in a setup tx; LULA accrued
   referral rewards for 12 days to earn `recycle()` authorization; OLPC's owner
   seeded the kill switch six weeks earlier.
4. **Ephemeral contracts defeat per-address defenses:** fresh helpers bypass AIDC's
   sell cooldown; DLMC/JB register referral trees to reach gated paths.
5. **Third-party and decommissioned infrastructure is where big money dies:** Supra's
   verifier sank Bonzo; Ostium's out-of-scope signer key cost $23.75M; SummerFi
   counted a paused ark; Aztec left a funded rollup with a dev-key operator.
6. **Two economies:** BSC meme-token reserve drains produce the *frequency*
   ($20k–$1.1M each); mainnet logic bugs produce the *size* (Aztec $2.2M, SummerFi
   $6M); oracle-infra failures produce the worst *totals* (Ostium + Bonzo ≈ $33M).

---

## 5. Distilled audit checklist

- Any state-changing valuation reading AMM reserves, `slot0`, `convertToAssets()`, or
  aggregated `totalAssets()` → is there a guard, and does it cover **all** paths or
  only the privileged one?
- Donation/skim semantics: what happens to share price / NAV / reserves if anyone
  sends tokens directly?
- Degenerate-input checks on crypto verification: zero-address `ecrecover` results,
  identity-element pairings, unconstrained circuit witnesses, root-field reuse.
- Edge cases as attack surface: zero-amount batch items, untyped integer casts,
  split-invariance of pricing curves, rounding direction near dust reserves,
  `min*` bounds on reverse-computed inputs.
- Arbitrary-call surfaces: any `target.call(data)` with user-supplied components;
  calldata forwarded into external managers *as the protocol*.
- Off-chain/oracle plumbing: tx-status checks in indexers; signer-key custody and
  bounty-scope coverage; deviation limits on oracle pokes.
- Offboarding hygiene: paused/removed components still counted in aggregations;
  deprecated systems still holding funds.

---

## Appendix: window incident → root cause → PoC index

| Date | Protocol | Loss | Root cause (verified) | PoC |
|---|---|---|---|---|
| 06-16 | DIP | $111k | FoT + skim/sync pair-reserve shrink | `poc/2026-06/DIP_exp.sol` |
| 06-17 | WHALE | $3.4k | transfer accounting reserve desync | `poc/2026-06/WHALE_exp.sol` |
| 06-17 | LBP | 610 BNB | flash-staged LP credit → reward mint | `poc/2026-06/LBP_exp.sol` |
| 06-17 | Aztec V1 | $2.2M | VK soundness: membership/settlement root not compared | `poc/2026-06/AztecEscapeHatch_exp.sol` |
| 06-18 | JB | $50k | unverified helper live-balance cycles | `poc/2026-06/JB_exp.sol` |
| 06-20 | OLPC | $1.1M | owner-set decimalsValue → reserve decay | `poc/2026-06/OLPC_exp.sol` |
| 06-22 | Aztec (whitehat) | — | unconstrained proof_id witness | `poc/2026-06/AztecEscapeHatch_exp2.sol` |
| 06-23 | RoyalRoyalties | $261k | zero-amount ERC1155 items inflate tier balances | `poc/2026-06/RoyalRoyalties_exp.sol` |
| 06-24 | DLMC | $223k | reserve-derived livePrice inflated via two buys | `poc/2026-06/DLMC_exp.sol` |
| 06-25 | Lixir | ~$30k | ecrecover zero-address check missing | `poc/2026-06/LixirPermitDrain_exp.sol` |
| 06-25 | Ocean BPool | 128k mOCEAN | asymmetric join/exit + auto-mirroring SideStaking | `poc/2026-06/OceanBPoolSideStaking_exp.sol` |
| 06-27 | CookFinance | $50k | user-chosen weightings + spot adapter, no min-out | `poc/2026-06/CookFinanceIssuance_exp.sol` |
| 06-28 | AIDC | 220 WBNB | burn-from-pair on transfer; cooldown bypass | `poc/2026-06/AIDC_exp.sol` |
| 06-29 | Vault4626 | 13.5 WETH | non-asset double count in totalAssets/redeem | `poc/2026-06/Vault4626_exp.sol` |
| 07-01 | edel-xstock | $204k | ERC4626 rate as collateral oracle + donation | `poc/2026-07/edel-xstock_exp.sol` |
| 07-06 | SummerFi | $6.02M | NAV sum, paused ark counted, depegged xUSD at par | `poc/2026-07/SummerFi_exp.sol` |
| 07-02/03 | Hinkal | $800k | nullifier not bound to commitment | txs `0xfbedf0cd…`, `0xbf7252af…` |
| 07-11/15 | Bonzo Lend (Hedera) | $9.05M | Supra verifier accepts zeroed BLS sigs | Bonzo incident report |
| 07-13 | Lumi/Sodium | $264k | ERC-1271 self-verifier bypass + UserOp approval side effect | VeriChains write-up |
| 07-14/15 | Drips | $24.9k | uint128→int128 unchecked cast, sign flip | tx `0xc38a6e22…` |
| 07-15 | Ostium | $23.75M | compromised oracle signer key (off-chain) | Halborn/Ostium post-mortem |
| 07-15 | 42DAO | $912k | oracle poke→VAT→Dog with no deviation checks | SlowMist/PeckShield |
| 07-17/28 | Across (Solana) | $3.6M | relayer indexer ignored tx status | Asymmetric Research |
| 07-29 | LULA | $578k | privileged recycle() pulls from pair + sync | AutoSec/Phalcon |
| 08-02 | LpdFi | $693k | live pair reserves as accounting truth | BlockSec |
| 08-09 | USM | 70.8 ETH | split-invariance violation in defund() | `poc/2026-08/USM_exp.sol` |
| 08 | Ajna (7 pools) | $775k | self-controlled liquidation, oracle-free design | `poc/2026-08/AjnaFinance_exp.sol` |
| 08 | Arrakis G-UNI | 2.9 ETH | mint/burn at slot0; guard only on rebalance | `poc/2026-08/ArrakisGUNI_exp.sol` |
| 08 | Float Protocol | 10.7 ETH | LP shares at slot0, no TWAP on deposit/withdraw | `poc/2026-08/FloatProtocol_exp.sol` |
| 08 | Sandbox OFT (Base) | $49B face | approveAndCall arbitrary call → attacker DVN | `poc/2026-08/SandboxOFT_exp.sol` |
| 08 | Unistreet | $17.7k | launch() calldata forwarded verbatim to V4 posm | `poc/2026-08/UnistreetLaunchpad_exp.sol` |
| 08-31 | Balancer V1 BPool | dust-drain | input rounds to 1 satoshi, no min-effective-input | `poc/2026-08/BalancerV1BPool_exp.sol` |

Not in table: key compromises (AFX $24.15M, TripleA $9.7M, SwanTreasury $625k),
governance attacks (BonkDAO $21.3M, BarnBridge $776k, Strongblock, ZKPanther), and
bridge ops (VerusCoin $7.3M notary compromise) — outside the two analyzed classes.
