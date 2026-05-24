"""Audit density scoring and under-audited classification.

Stage 3 combines signals from multiple audit-history sources into a single
`audit_density_score` (integer, 0 = none found, higher = more audits). The
under_audited threshold is 2 — anything at or below is a candidate.

Weights (per the plan):
    DefiLlama audit_links:       1 point each, cap 3
    GitHub audits/ folder:       1 point (presence only — we don't count files)
    Solodit prior findings:      2 points (v2 — deferred)
    C4/Sherlock/Cantina hit:     3 points per unique contest match
    Protocol docs mention:       1 point each (v2 — deferred)
"""

from __future__ import annotations

import logging

from tvl_scanner.models import (
    AuditedCandidate,
    AuditSource,
    AuditSourceKind,
    EnrichedCandidate,
)

log = logging.getLogger(__name__)


# Protocols whose DefiLlama slug (or display name) maps to a well-known
# audited upstream. When the candidate's slug starts with any of these
# prefixes, the audit attribution is definitive regardless of what
# DefiLlama's `audits` field says. Why this exists: DefiLlama lists each
# Uniswap V4 pool as a separate sub-entry with audits=0, even though the
# underlying V4 core is heavily audited. Without this whitelist those
# pools surface as multi-billion-TVL "under-audited" false positives.
#
# Match is case-insensitive prefix-match on the slug. Conservative — only
# protocols whose audit history is universally known.
KNOWN_AUDITED_SLUG_PREFIXES: tuple[str, ...] = (
    "uniswap",       # uniswap-v2, uniswap-v3, uniswap-v4, uniswap-v4-arbitrum, etc.
    "sushiswap",
    "pancakeswap",
    "curve",         # curve-dex, curve-finance
    "balancer",      # balancer-v2, balancer-v3
    "aave",          # aave-v2, aave-v3, aave-v3-lite
    "compound",      # compound-v2, compound-v3
    "maker",         # makerdao, maker-rwa
    "morpho",        # morpho-blue, morpho-aave-v3
    "aerodrome",
    "velodrome",
    "quickswap",
    "lido",
    "rocket-pool",
    "stader",
    "ether-fi",
    "renzo",
    "pendle",
    # Added Batch N.3 — confirmed public audit history:
    "venus",         # Venus Protocol (Peckshield, OpenZeppelin)
    "obol",          # Obol Network (Sigma Prime, ChainSecurity)
    "usual",         # Usual.money (Sherlock)
    "inverse",       # Inverse Finance (DeFiSafety + others)
    "spark",         # Spark Protocol (Maker subsidiary)
    "yearn",         # Yearn V2/V3 (multiple audits)
    "fluid",         # Fluid by Instadapp (multiple audits)
    "ethena",        # Ethena USDe (Quantstamp, Spearbit, Cantina)
    "zircuit",       # Zircuit (zk audits)
    "kelp",          # Kelp DAO (Sigma Prime)
    # Added Batch N.5 — surfaced as false positives in real scans:
    "raydium",       # Raydium (Ottersec, multiple)
    "euler",         # Euler Vault Kit / Euler v2 (Spearbit, Cantina, Hexens, others)
    "jupiter",       # Jupiter Aggregator (Solana, multiple audits)
    "marginfi",      # marginfi (Halborn, Ottersec)
    "drift",         # Drift Protocol (Solana, multiple audits)
    "kamino",        # Kamino Finance (Ottersec, Trail of Bits)
    "marinade",      # Marinade Finance (Neodyme, Kudelski)
    # Added Batch N.6 — confirmed via Etherscan source verification
    # (@author tags) and/or direct docs lookups during real-scan iteration:
    "nexus",         # Nexus Mutual (iosiro multi, Chaos Labs, G0 Group, Solidified — confirmed)
    "nexus-mutual",
    "silo",          # Silo Finance V3 (2+ audits on DefiLlama, established 2022)
    "alchemix",      # Alchemix V3 (2+ audits on DefiLlama, Trail of Bits history)
    "zama",          # Zama (homomorphic encryption — audits per their docs)
    "royco",         # Royco V2 (Sherlock contests)
    "citrea",        # Citrea Bridge (Code4rena)
    "lorenzo",       # Lorenzo Protocol (Zellic + multiple per docs)
    "doublezero",    # DoubleZero (established Solana LST infrastructure)
    "gmx",           # GMX (Trail of Bits + multiple)
    "ether.fi",      # EtherFi (Cantina + multiple — also matches source_author with dot)
    "etherfi",
    "ostium",        # Ostium Labs (Pashov, Three Sigma)
    "synthetix",     # Synthetix (well audited)
    "gauntlet",      # Gauntlet (curator with audited vault impls)
    "morpho",        # Already injectable but reinforced (Spearbit, Cantina)
    "sosovalue",     # SosoValue index funds
    # Smart wallets & multisig singletons — NOT protocols, but heavily audited
    # and surface as candidates because each user-deployed clone holds funds.
    # Treating them as "audited" filters them from the under-audited list.
    "safe",          # Gnosis Safe (SafeProxy, GnosisSafeProxy)
    "gnosis",
    "richard-meissner",  # Gnosis Safe lead — appears in @author tag
    "singleowner",   # SingleOwnerMSCA (ERC-6900 modular smart account)
    "singleownermsca",
    "msca",
    "modularsmart",
    "smartaccount",
    "kernel",        # ZeroDev Kernel (modular smart account)
    "biconomy",      # Biconomy smart account
    "coinbase",      # Coinbase Smart Wallet
    # Additional well-audited protocols surfaced as false positives:
    "avalon",        # Avalon Finance (PeckShield, BlockSec)
    "dydx",          # dYdX (multiple)
    "harvest",       # Harvest Finance (multiple)
    "homora",        # Homora / Alpha Homora V2 (audits per DefiLlama)
    "alpha",         # Alpha Finance (Homora) — same family
    "lyra",          # Lyra Finance (Sherlock + multiple)
    "near",          # NEAR Protocol family
    # Batch N.7 — identified via Etherscan source paths during real-scan iteration:
    "moolah",        # Moolah (Lista DAO ecosystem BSC, PeckShield + multi)
    "lista",         # Lista DAO (audits)
    "alpaca",        # Alpaca Finance (multiple audits)
    "stableswap",    # Generic Curve-style — only matches when name() is literally StableSwap*
    "uniswapv3pool", # Match when verified ContractName is UniswapV3Pool
    "uniswapv2pair", # Match when verified ContractName is UniswapV2Pair
    "mstable",       # mStable (multiple audits)
    # Batch N.8 — bridge / interop infrastructure (false positives where a
    # protocol deploys stock infra but DefiLlama lists it as a new "protocol"
    # with audit_count=0):
    "hyperlane",     # Hyperlane (Abacus Works) — Trail of Bits, Halborn, Zellic
    "abacus",        # @author: "Abacus Works" (Hyperlane's original org)
    "hypnative",     # Hyperlane Warp Route contract names
    "hyperc20",      # HypERC20, HypERC20Collateral
    "hypxerc20",
    "wormhole",      # Wormhole (multiple)
    "axelar",        # Axelar (Halborn + multiple)
    "layerzero",     # LayerZero (Trail of Bits + multiple)
    "across",        # Across Protocol (Open Zeppelin + multiple)
    "stargate",      # Stargate (LayerZero-based, audited)
    "ccip",          # Chainlink CCIP (heavily audited)
    "connext",       # Connext (multi-audit)
    "celer",         # Celer Network
    "circle",        # Circle CCTP (USDC issuer's own bridge)
    "cctp",          # CCTP same as above
    "socket",        # Socket Tech (multiple audits)
    "li.fi",         # LI.FI aggregator (audits per docs)
    "lifi",
    "across-",
    "dango",         # Dango Bridge (Hyperlane warp-route deployment)
    "ekubo",         # Ekubo Protocol DEX (audited by Spearbit, ChainSecurity)
    "lagoon",        # Lagoon Finance v0.5.0 vault infrastructure (Spearbit/Cantina)
    "lagoonvault",   # contract_name "LagoonVault" / "LagoonVaultProxy"
    "erc7540",       # ERC-7540 async vault standard — Lagoon's ERC7540Upgradeable
    "optinproxy",    # Lagoon's OptinProxy contract_name
    "rocksolid",     # RockSolid Network (Lagoon vault deployment, no proprietary code)
    "flex",          # Flex (Liquity V2 fork; 4 audits including Dedaub May 2026 in repo /audits folder)
    "flexmeow",      # Flex's GitHub org / brand
    "liquity",       # Liquity V1/V2 (multiple audits, well-known base)
    "yuga",          # Yuga Labs (CryptoPunks, BAYC parent — well-resourced security team)
    "yugalabs",
    "punks",         # Punks Terminal (Yuga Labs / Lightyear)
    "lightyear",     # Lightyear (Yuga Labs affiliate building Punks Terminal)
    "stashfactory",  # contract_name for Punks Terminal Stash Factory
)


# Cap per source kind to prevent one noisy source from dominating
CAPS: dict[AuditSourceKind, int] = {
    AuditSourceKind.DEFILLAMA: 3,
    AuditSourceKind.GITHUB_AUDITS_FOLDER: 1,
}

# Any candidate at or below this score is flagged as under-audited
UNDER_AUDITED_THRESHOLD = 2


def _defillama_sources(candidate: EnrichedCandidate) -> list[AuditSource]:
    """Build AuditSource entries from DefiLlama audit metadata.

    Uses BOTH the flat catalog's audit_links AND the detail endpoint's audit
    count (when available). The count can exceed the number of linked audits
    if some audits are only referenced in prose — we trust DefiLlama's count
    as the upper bound but cap at CAPS[DEFILLAMA] to prevent over-scoring.

    Scoring: max(count, len(links)), capped at 3. Each unit = 1 AuditSource.
    Prefer concrete URLs over phantom count-only entries when available.
    """
    cap = CAPS[AuditSourceKind.DEFILLAMA]
    links = candidate.defillama_audit_links[:cap]
    count = candidate.defillama_audit_count or 0

    sources: list[AuditSource] = []
    # First, emit AuditSource records for each concrete link (has URL)
    for link in links:
        sources.append(
            AuditSource(
                source=AuditSourceKind.DEFILLAMA,
                url=link,
                weight=1,
            )
        )

    # If DefiLlama's integer count exceeds the number of links, add phantom
    # URL-less records up to the cap. This captures protocols where an audit
    # note says "audited by ToB in 2024" but the link list is empty.
    if count > len(sources):
        extra = min(count - len(sources), cap - len(sources))
        note = candidate.defillama_audit_note
        for _ in range(extra):
            sources.append(
                AuditSource(
                    source=AuditSourceKind.DEFILLAMA,
                    url=None,
                    title=note[:80] if note else "DefiLlama audit (no link)",
                    weight=1,
                )
            )
    return sources


def _github_folder_source(candidate: EnrichedCandidate) -> list[AuditSource]:
    """A single AuditSource if the github audits folder exists, else empty."""
    if not candidate.github_audits_folder_exists or not candidate.github_repo:
        return []
    audits_url = str(candidate.github_repo).rstrip("/") + "/tree/HEAD/audits"
    return [
        AuditSource(
            source=AuditSourceKind.GITHUB_AUDITS_FOLDER,
            url=audits_url,
            weight=1,
        )
    ]


# Minimum bounty payout (USD) below which we don't trust the program as
# evidence of prior auditing. Below ~$100K, bounty programs are common for
# unaudited code (community bounties, beta tests). At $100K+, platforms like
# Immunefi require audit reports during onboarding.
BOUNTY_TRUST_MIN_PAYOUT_USD = 100_000
BOUNTY_TRUST_WEIGHT = 4


def _bounty_trust_source(candidate: EnrichedCandidate) -> list[AuditSource]:
    """If the candidate has a substantial public bug bounty, treat that as
    strong evidence the protocol has been audited.

    Rationale: Immunefi (and HackerOne for crypto) require audit reports as
    part of program onboarding for any meaningful payout cap. A $1M bounty
    on Immunefi means the team has been through audit due diligence — even
    if their audit reports are hosted on private docs sites that our
    scanner can't reach (Trail of Bits / Halborn / Zellic / ChainSecurity
    typically deliver PDFs hosted by the protocol, not in github).

    BATCH I.2 fix: closes the false-negative class where Hyperlane, Synapse,
    and similar protocols showed audit_density_score=0 because their
    private audits aren't in DefiLlama, GitHub `audits/` folders, or any
    contest org. Previously they ranked at the top of the under-audited
    list which was wrong — they're audited, just not by sources we index.

    Weight is 4 (single source) which:
      - raises total above the under_audited threshold (>2)
      - drops audit_gap_score by 8 points (max(0, 10 - 2*4) = 2)
      - drops priority score by 8 * 0.30 = 2.4 points
    Net effect: bounty-having protocols leave the top of the report and
    truly-fresh / truly-unindexed protocols rise.
    """
    if candidate.bounty_program == "none":
        return []
    if (
        candidate.bounty_max_payout_usd is None
        or candidate.bounty_max_payout_usd < BOUNTY_TRUST_MIN_PAYOUT_USD
    ):
        return []

    title = (
        f"Trusted via {candidate.bounty_program} bounty "
        f"(max ${candidate.bounty_max_payout_usd:,}) — bounty platforms "
        f"vet protocols against audit reports during onboarding"
    )
    return [
        AuditSource(
            source=AuditSourceKind.BOUNTY_TRUST,
            url=candidate.bounty_url,
            title=title,
            weight=BOUNTY_TRUST_WEIGHT,
        )
    ]


def compute_score(
    candidate: EnrichedCandidate,
    *,
    contest_sources: list[AuditSource] | None = None,
) -> AuditedCandidate:
    """Combine all audit-history signals into an AuditedCandidate.

    Caller is responsible for fetching `contest_sources` (via the contests
    module) — this function is pure and synchronous so it's testable in
    isolation.

    BATCH I fix #2: under_audited logic now has a definitive-override path.
    Previously any candidate with total_score ≤ 2 was flagged as
    under-audited, which mislabeled protocols like Pendle/Convex/Lido/Maple
    whose DefiLlama audit count was exactly 2 but who are heavily audited in
    reality (DefiLlama's count undercounts patches and follow-up reviews).
    If DefiLlama explicitly reports audit_count ≥ 2, we trust that as
    definitive evidence of prior auditing and force under_audited=False,
    regardless of what total_score lands at.
    """
    contest_sources = contest_sources or []

    all_sources: list[AuditSource] = []
    all_sources.extend(_defillama_sources(candidate))
    all_sources.extend(_github_folder_source(candidate))
    all_sources.extend(_bounty_trust_source(candidate))
    # BATCH J/K: pre-computed sources from wrapper detection, bytecode
    # pattern matching, and homepage scraping. Stage 2 enrichment populates
    # these on the EnrichedCandidate; here we just include them in the total.
    all_sources.extend(candidate.precomputed_audit_sources)
    all_sources.extend(contest_sources)

    # BATCH N.2: slug/name-prefix attribution. Done HERE (before total_score)
    # so the synthetic source contributes to audit_density_score, which feeds
    # the priority formula's audit_gap calculation. Without this, V4 pools
    # would stay flagged with audit_density_score=0 → audit_gap=10 → high
    # priority, even though we'd correctly set under_audited=False.
    #
    # Matches against EITHER defillama_slug or display_name (lowercased,
    # whitespace-stripped to first token). GeckoTerminal-sourced candidates
    # often have display_name="Uniswap V4 (Arbitrum)" but slug=None, so a
    # slug-only check misses them.
    name_for_match = None
    if candidate.defillama_slug:
        name_for_match = candidate.defillama_slug.lower()
    elif candidate.display_name:
        # Take the first token of the display name, lowercased. Handles
        # "Uniswap V4 (Arbitrum)" → "uniswap", "SushiSwap (BSC)" → "sushiswap".
        first_token = candidate.display_name.split()[0] if candidate.display_name.strip() else ""
        name_for_match = first_token.lower()

    if name_for_match and any(
        name_for_match.startswith(prefix)
        for prefix in KNOWN_AUDITED_SLUG_PREFIXES
    ):
        all_sources.append(
            AuditSource(
                source=AuditSourceKind.FACTORY_ATTRIBUTION,
                url=None,
                title=(
                    f"Name '{name_for_match}' matches known audited protocol "
                    f"family — audit attribution by name"
                ),
                weight=4,
            )
        )

    total_score = sum(src.weight for src in all_sources)
    under_audited = total_score <= UNDER_AUDITED_THRESHOLD

    # Definitive-override: DefiLlama-reported audit count ≥ 2 wins over
    # any weaker aggregated signal. Catches protocols whose underlying
    # audits exist but aren't all visible to GitHub contest search.
    if (
        candidate.defillama_audit_count is not None
        and candidate.defillama_audit_count >= 2
    ):
        under_audited = False

    # BATCH J/K/N override: a single wrapper-program, homepage-scrape, or
    # factory-attribution source is definitive evidence of prior auditing —
    # these are signals the other override paths miss. WRAPPER_PROGRAM
    # (bytecode hash match) and FACTORY_ATTRIBUTION (factory() call or
    # slug-prefix match) both attribute audits via the upstream protocol;
    # HOMEPAGE_SCRAPE picks up self-hosted audit firm citations.
    for src in all_sources:
        if src.source in (
            AuditSourceKind.WRAPPER_PROGRAM,
            AuditSourceKind.HOMEPAGE_SCRAPE,
            AuditSourceKind.FACTORY_ATTRIBUTION,
        ):
            under_audited = False
            break

    return AuditedCandidate(
        **candidate.model_dump(),
        audit_density_score=total_score,
        audit_sources_found=all_sources,
        under_audited=under_audited,
    )
