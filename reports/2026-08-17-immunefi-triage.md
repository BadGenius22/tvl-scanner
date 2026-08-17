# Immunefi Bounty Triage — 2026-08-17

**Method**: `tvl-scanner immunefi-scan` on the 12-criteria bounty formula, then
hand-checked against live Immunefi pages, DefiLlama `chainTvls`, and (for the
pick) an on-chain balance sweep. The raw rank is a shortlist, not a verdict —
this scan still promoted a Solana *devnet* listing to #3 and a Katana-L2
program to #12.

```
tvl-scanner immunefi-scan --cutoff 0 --cap 60 \
    --exclude-invite-only --exclude-pay-to-submit --exclude-level-gated \
    --exclude-slugs-file reports/excluded-slugs.txt
```

**Funnel** (248 programs fetched):

| Drop | Reason |
|------|--------|
| −89 | no in-scope contract on a supported chain |
| −18 | program closed |
| −1 | invite-only |
| −11 | exclusion list (KAST, SparkLend, Pareto, Beanstalk + already-hunted) |
| −15 | Pay to Submit |
| **114** | **kept; top 60 written** |

Lives beside the auto-generated `2026-08-17-immunefi-scan.md`. That file is
regenerated every run. This one is the decision record.

---

## What the scanner got wrong this run (fixed in-tree, not re-scanned)

The branch already had per-chain TVL for the *catalog* path (`run`). Immunefi-scan
still copied DefiLlama's protocol-wide `tvl` onto whichever explorer showed up
first. Live log from this run, before the remaining guards landed:

| Program | What the old path would have done | What this run did |
|---------|-----------------------------------|-------------------|
| TruYields | $7 Ethereum leftover → 400,000% payout ratio → rank 3–4 | refused the off-chain TVL (`?`) |
| Katana | Solana Katana's $1.4M as Ethereum | refused, then measured katanascan 0x addrs on Ethereum → **$0** |
| Stargate | VeChain Stargate $3.7M | refused |
| Folks Finance | Algorand $20M as Ethereum | refused |
| USDT0 | $3.2B Ethereum total on an Optimism-scoped row | refused |
| function-fbtc | $544M Bitcoin as Ethereum | refused |

Two more defects showed up in the records themselves and are now patched
(tests green, **not** re-run — the report above still contains the old rows):

1. `?cluster=devnet` was not a testnet marker. TruYields' only explorer row is
   Solana **devnet**. Added `cluster=devnet` / `cluster=testnet`.
2. An unrecognized explorer (`katanascan.com`) fell through to `ecosystem: ETH`.
   Unmapped mainnet explorers now skip the program instead of inventing an
   Ethereum target.

Also: Immunefi `language[]` no longer gets Solidity prepended just because the
explorer is etherscan, and a payout ratio with TVL &lt; $10k is left unknown
so dust cannot max criterion 3.

---

## Ranked leads (after throwing out the artifacts)

| # | Target | Floor / cap | On-scope TVL | Scope | New 90d | KYC | Why it stays |
|---|--------|-------------|--------------|-------|---------|-----|--------------|
| 1 | **Synthetix DepositContract** | table says $100k flat; body says 10% / $10k min / $100k cap. High is **flat $50k**. | **$872k** (on-chain, 3 tokens on the deposit proxy — matches DefiLlama ETH) | 3 (1 is a view lens) | **3 (100%)** | no | New custody + multi-stage withdraw surface, listed 2026-06-21, deploy 2025-11-06 |
| 2 | Hashflow (June 2026 factory/pool/router) | $5k / $50k (20% of funds) | $115k ETH / $239k all chains (DefiLlama agrees) | 4 | **4 (100%)** | no | Tight, fresh listing. Critical on current TVL is ~$23k. CertiK 2022 audits do **not** cover this code; they were hacked June 2023 (access control, out of those audits' scope). |
| 3 | Balancer V3 / reclamm adds | $100k / $1M (10%) | $20.5M ETH (per-chain; not the old $2B+ headline) | 24 | 14 | no | Real money and a real floor. Already opened 2026-07-13. Density 16, 3 known issues, Critical needs &gt;1% of the Vault. Crowded post-Nov-2025 hack. |

### The one worth a week

**Synthetix — on-chain custody layer**
(`https://immunefi.com/bug-bounty/synthetix`).

This is not the old SNX debt-pool bounty. The 2026-06-21 rewrite scoped three
contracts:

| Address | Role |
|---------|------|
| `0xD62595c3c23B690BAEE0935e107A209Cb1Dbd37B` | `SynthetixDepositContract` proxy — collateral custody + multi-stage withdrawals |
| `0x99E61877aF9Bc6805BCc3813F655D94Ed5f3782A` | view-only lens |
| `0x45F91031b33Da2585932c8f1cdFF0faa6cD329ae` | `PermissionsRegistry` proxy |

On-chain sweep of those three addresses: **$872,279** across 3 tokens on the
deposit proxy. That is the funds-at-risk number, not a leftover SNX staking
figure.

Start at the withdraw/unlock path. The program text says "audited, role-governed
custody contract" — I could not find a public report that names
`SynthetixDepositContract` (V3 iosiro/ChainSecurity reports are a different
system). Treat "audited" as a claim until the PDF is in hand. The scanner's
density 8 is a `synthetix-v4` *name* attribution, not a report on this proxy.

**Read the reward table twice before scoping a Critical.** The Immunefi table
prints Critical as flat $100k; the same page's calculation paragraph says 10%
of funds affected, cap $100k, **minimum $10k**. Primacy of Rules. High is
unambiguously flat $50k. A full drain of today's $872k is ~$87k under the 10%
rule — still a week of work. Restricted-country clause in out-of-scope.

Repo pointer in the record is the org (`github.com/Synthetixio`), not a
contract repo. First hour: bind the proxy implementation and find the source
tree that matches bytecode.

No KYC. PoC required (page says all severities; scanner only flagged web
tiers — trust the page).

### If that binds or the TVL is dust

**Hashflow** — four contracts, all added 2026-06-08, no KYC, $5k floor.
Only take this as a *short* engagement: 20% of $115k ETH is $23k. Confirm the
June 2026 factory/pool/router is new bytecode, not the 2022 CertiK surface
re-listed.

**Balancer** — only if you want to resume the 2026-07-13 V3/reclamm look.
Do not start it cold; the crowd already did.

---

## Ruled out this run

| Target | Why |
|--------|-----|
| **TruYields** (raw #3) | Only explorer row is `explorer.solana.com/…?cluster=devnet`. $20k flat, KYC. Now on the exclusion list. |
| **Katana** (raw #12) | Every address is on `katanascan.com` (Katana L2). Not a scanned chain. $0 TVL was us probing those 0x addrs on Ethereum. Excluded. |
| **Livepeer** (raw #2) | Reviewed 2026-07-31. Live BondingManager/TicketBroker implementations are **not** the in-scope addresses. Density 0 in this scan is also a lie. Excluded. |
| CapyFi (#4) | KYC, 10 audits (OZ + Coinspect), 0 scope added in 90d. Compound fork. |
| Compound, Sky, Aave, Lido, Yearn, Lista, Origin | Already hunted or too picked-over. Origin/Lista specifically done (ARM / Moolah). |
| Variational, Kleidi, Immutable, Horizen, OnRe | KYC and/or no fresh scope and/or $10k cap (Horizen) and/or 1-contract surface (OnRe). |
| Hashflow as a *week* | TVL too small for the calendar time. Keep as a one- or two-day if Synthetix dies. |

Already-hunted slugs added to `reports/excluded-slugs.txt` this session:
`twyne`, `strata`, `veda`, `nuva`, `gmtrade`, `enzyme-onyx`, `marinade`,
`sbtc`, `subfrost`, `livepeer`, `trufin`, `katana`.

---

## Verification still needed before the first finding (Synthetix)

1. Pull the deposit-proxy implementation bytecode and match it to a repo.
   `github.com/Synthetixio` is not enough.
2. Resolve the Critical payout conflict (table flat $100k vs body 10%/$10k min)
   against the current program document, not this note.
3. Find the audit they allude to, or confirm there isn't one for *this*
   contract. V3 vault audits do not count.
4. Re-sweep token balances on `0xD625…d37B` the morning you start — $872k is
   today's number.

To open the work: `new audit on synthetix at ~/audit/2026-08-17-synthetix/`.
