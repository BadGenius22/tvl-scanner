"""Pydantic models for the pipeline data flow.

The schema is designed so that a `CandidateRecord` can be serialized as YAML
frontmatter and lifted directly into the vault's `VAULT_CONTEXT.md` Phase 2a
template (sections 1, 2, 6, 7). Field names match the template's section labels.

Stage flow:
    Raw API responses → DiscoveredContract (Stage 1)
    DiscoveredContract → EnrichedCandidate (Stage 2)
    EnrichedCandidate → AuditedCandidate (Stage 3, adds audit_density_score)
    AuditedCandidate → CandidateRecord (Stage 4, final with priority_score)
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Chain(StrEnum):
    ETHEREUM = "ethereum"
    ARBITRUM = "arbitrum"
    BASE = "base"
    OPTIMISM = "optimism"
    POLYGON = "polygon"
    BSC = "bsc"
    SOLANA = "solana"


class Language(StrEnum):
    SOLIDITY = "solidity"
    RUST = "rust"
    MOVE = "move"


class DiscoverySource(StrEnum):
    GECKOTERMINAL = "geckoterminal"
    BIRDEYE = "birdeye"
    DEFILLAMA_CATALOG = "defillama_catalog"
    IMMUNEFI_CATALOG = "immunefi_catalog"
    ALCHEMY_DEPLOYMENTS = "alchemy_deployments"
    RPC_ACTIVE_HOLDERS = "rpc_active_holders"
    FACTORY_EVENTS = "factory_events"
    DUNE = "dune"
    FLIPSIDE = "flipside"
    EXPLORER_VERIFIED = "explorer_verified"


class AuditSourceKind(StrEnum):
    DEFILLAMA = "defillama"
    GITHUB_AUDITS_FOLDER = "github_audits_folder"
    SOLODIT = "solodit"
    CODE4RENA = "code4rena"
    SHERLOCK = "sherlock"
    CANTINA = "cantina"
    DOCS_MENTION = "docs_mention"
    BOUNTY_TRUST = "bounty_trust"
    WRAPPER_PROGRAM = "wrapper_program"  # Batch J: protocol wraps a known audited program (SPL stake pool, Uniswap V2 pair, etc.)
    HOMEPAGE_SCRAPE = "homepage_scrape"  # Batch K: regex hit on the protocol's own homepage citing an audit firm
    FACTORY_ATTRIBUTION = "factory_attribution"  # Batch N: contract's factory() returns a known DEX factory (V3 pool etc.)
    PARENT_PROTOCOL = "parent_protocol"  # Batch Q: sibling under the same DefiLlama parentProtocol group has audit signals — typical pattern for multi-product teams (Rho Labs: rho-x, rho-x-lp-vault, rho-vaults-v1, rho-protocol all share rho.trading audits)
    BOUNTY_SCOPE_AUDIT = "bounty_scope_audit"  # audit report linked in the bounty program's own prose (prior findings are out of scope, so programs cite them) — the only signal that sees PDF-publishing firms like Sigma Prime / ChainSecurity / PeckShield
    GITHUB_ORG_AUDIT_REPO = "github_org_audit_repo"  # a dedicated org-level `Audits` REPO (not an audits/ folder inside a code repo) — teams that publish reports this way are invisible to the folder check, since the org name rarely matches the DefiLlama slug (0xhyperbeat vs hyperbeat-usd)


class AuditSource(BaseModel):
    """One evidence item for a prior audit of a protocol."""

    model_config = ConfigDict(use_enum_values=True)

    source: AuditSourceKind
    # Stored as a plain string, not pydantic HttpUrl: these URLs come from
    # scraped homepages / API responses and are only ever displayed in the
    # report. HttpUrl added no value (nothing parses the components) and two
    # liabilities — it normalizes the URL (trailing-slash rewrites leaking into
    # the report) and raises ValidationError on a malformed scrape, which would
    # abort the whole enrichment stage. A plain string is faithful and safe.
    url: str | None = None
    published_at: date | None = None
    title: str | None = None
    weight: int = Field(default=1, ge=0, description="Points contributed to audit_density_score")


class RewardTier(BaseModel):
    """One severity row of a bounty program's reward table.

    Immunefi publishes rewards per (assetType, severity). `reward_model` is
    Immunefi's own vocabulary: "range" (min..max, triager picks), "fixed" (flat
    payout) or "up_to" (max only, fully discretionary).
    """

    severity: str
    asset_type: str
    reward_model: str | None = None
    min_usd: int | None = None
    max_usd: int | None = None
    calculation_percentage: float | None = Field(
        default=None,
        description="Percent of funds-at-risk this tier pays (Immunefi's rewardCalculationPercentage)",
    )
    poc_required: bool | None = None


class KnownIssue(BaseModel):
    """A publicly declared known issue — a documented dead zone for submissions.

    Anything a program lists here is pre-emptively out of scope: a finding in
    that area is closed as a known issue / duplicate no matter how good the
    write-up. A long list is a minefield AND evidence the program has already
    been mined hard by other researchers.
    """

    description: str
    link: str | None = None
    last_updated: date | None = None
    related_impact: str | None = None


class ScopeAsset(BaseModel):
    """One row of a bounty program's assets-in-scope table, kept verbatim.

    The scanner used to reduce the whole table to a count and one representative
    address, which is not enough to start an audit: the standing rule is to
    extract and verify the FULL in-scope list before writing a line of analysis,
    and a count sends you back to the website to do it by hand.

    `is_placeholder` marks Immunefi's Primacy-of-Impact sentinel row — an entry
    whose url is `https://immunefi.com/` and whose only job is to carry
    `isPrimacyOfImpact: true`. It is not a contract, and 80 of them are spread
    across 61 programs in the 2026-08 catalogue, so counting them as scope
    inflates criterion 8 for a quarter of the universe.
    """

    asset_type: str = Field(
        ..., description="Immunefi's own label: smart_contract | websites_and_applications | blockchain_dlt"
    )
    url: str
    description: str | None = None
    address: str | None = Field(
        default=None, description="EVM address parsed out of an explorer URL, when there is one"
    )
    repo: str | None = Field(
        default=None,
        description=(
            "owner/repo[/path] when the asset points at GitHub. Repo- and "
            "directory-level scope is a different audit shape from an address: it "
            "usually means source review against a branch rather than a deployed "
            "target, and the deployed code must be matched back by hand."
        ),
    )
    explorer: str | None = Field(
        default=None, description="Explorer host the address came from, e.g. 'arbiscan.io'"
    )
    added_at: date | None = None
    revision: int = 0
    primacy_of_impact: bool = False
    safe_harbor: bool = False
    is_placeholder: bool = Field(
        default=False, description="Primacy-of-Impact sentinel row, not a real in-scope asset"
    )
    is_testnet: bool = False


class ProgramImpact(BaseModel):
    """One row of the program's own impact table.

    Carried at every severity, not just critical. The rule for reading a program
    is to take its impact rows verbatim across all tiers: a finding that maps to
    no row is unpayable however good it is, and a reachable Low floor beats an
    unreachable Critical ceiling.
    """

    severity: str
    asset_type: str
    title: str


class AuditRecord(BaseModel):
    """One entry of the program's self-declared audit list.

    `is_placeholder` is the load-bearing field. Programs routinely fill this list
    with a single link to their own security page under a non-name like "All
    Audits", dated the day the bounty launched. That is a pointer, not a review,
    and scoring it as one makes audit staleness read as program age. 16 of the
    237 audit rows in the 2026-08 catalogue are placeholders by these tests.
    """

    auditor: str | None = None
    url: str | None = None
    performed_at: date | None = None
    is_placeholder: bool = False
    placeholder_reason: str | None = None


class ProgramExclusions(BaseModel):
    """The published limits on what a program will accept.

    Immunefi splits this across seven prose fields that the scanner previously
    read none of. They are where the auto-invalidators live: the feasibility
    limitations alone run to ~1.4K characters on a typical program and decide
    whether a whole class of finding is submittable. Reading them before picking
    a target is cheaper than reading them after writing a report.

    Every field is the program's text, truncated to `EXCLUSION_TEXT_CHARS`.
    """

    rules: str | None = Field(default=None, description="outOfScopeAndRules")
    out_of_scope_general: str | None = None
    out_of_scope_smart_contract: str | None = None
    out_of_scope_blockchain: str | None = None
    out_of_scope_web: str | None = None
    custom_out_of_scope: str | None = None
    feasibility_limitations: str | None = None
    prohibited_activities: str | None = None
    custom_prohibited_activities: list[str] = Field(default_factory=list)
    prioritized_vulnerabilities: str | None = Field(
        default=None,
        description="What the program says it most wants — the inverse of an exclusion",
    )

    def published_sections(self) -> list[str]:
        """Names of the sections this program actually filled in."""
        named = [
            ("rules", self.rules),
            ("out_of_scope_general", self.out_of_scope_general),
            ("out_of_scope_smart_contract", self.out_of_scope_smart_contract),
            ("out_of_scope_blockchain", self.out_of_scope_blockchain),
            ("out_of_scope_web", self.out_of_scope_web),
            ("custom_out_of_scope", self.custom_out_of_scope),
            ("feasibility_limitations", self.feasibility_limitations),
            ("prohibited_activities", self.prohibited_activities),
            ("prioritized_vulnerabilities", self.prioritized_vulnerabilities),
        ]
        out = [name for name, text in named if text]
        if self.custom_prohibited_activities:
            out.append("custom_prohibited_activities")
        return out


class ProgramResource(BaseModel):
    """A link the program publishes about itself: docs, repo, audit report."""

    kind: Literal["website", "repo", "audit"]
    url: str
    label: str | None = None


class BountyProfile(BaseModel):
    """Bounty-program target-selection profile, extracted from the Immunefi catalogue.

    Carries the rubric criteria that live on the *program* rather than on the
    protocol's code — criteria 2-6 and 8-12 of the immunefi-scan ranking (see
    `rank/bounty_priority.py`). Criterion 1 (funds at risk) is the candidate's
    `tvl_usd`, criterion 7's count is `defillama_audit_count`, and criterion 10
    is the edge-match keyword set; only the audit *recency* half of criterion 7
    is stored here, because DefiLlama's integer says nothing about when.

    Every field is best-effort: a program that omits a section leaves the
    corresponding fields at their neutral default, and the scorer treats a
    missing signal as unknown rather than as a zero.
    """

    # --- 2. Maximum + minimum bounty ---
    max_bounty_usd: int | None = None
    min_bounty_usd: int | None = Field(
        default=None, description="Smallest floor across the smart-contract tiers"
    )
    critical_min_usd: int | None = None
    critical_max_usd: int | None = None
    reward_tiers: list[RewardTier] = Field(default_factory=list)

    # --- 3. Bounty calculation ---
    reward_model: str | None = Field(
        default=None, description="Model of the critical smart-contract tier"
    )
    reward_calculation_percentage: float | None = None
    ten_percent_economic_rule: bool = False
    poc_required_for_critical: bool | None = None
    poc_required_tiers: list[str] = Field(
        default_factory=list,
        description=(
            "Raw `pocPerTypeAndSeverity` rows, each '<assetType> - <severity>' "
            "(e.g. 'smart_contract - critical'). Every program in the catalogue "
            "publishes this list, and a mandatory PoC is real work to budget for."
        ),
    )
    payout_basis: str = Field(
        default="unspecified",
        description="One-line human summary of how a critical payout is actually computed",
    )
    max_payout_vs_tvl_pct: float | None = Field(
        default=None,
        description=(
            "max_bounty_usd as a percent of the protocol's TVL. The headline max "
            "is meaningless without it: a $50K cap over $2B of funds at risk is "
            "0.0025%, which is what the payout actually is regardless of the "
            "advertised 10% rule. None when TVL is unresolved."
        ),
    )

    # --- 4. Last update ---
    program_updated_at: date | None = None
    days_since_program_update: int | None = None

    # --- 5. Program age ---
    program_launched_at: date | None = None
    program_age_days: int | None = None
    program_ends_at: date | None = None
    is_time_boxed: bool = Field(
        default=False, description="Has an endDate — audit comp / attackathon, not an open bounty"
    )

    # --- 6. Known issues ---
    known_issue_count: int = 0
    known_issues: list[KnownIssue] = Field(default_factory=list)
    known_issues_last_updated: date | None = None

    # --- 7. Audit history (recency half; the count lives on defillama_audit_count) ---
    audit_count: int = Field(
        default=0, description="Rows in the program's audit list, placeholders included"
    )
    verified_audit_count: int = Field(
        default=0,
        description=(
            "Audit rows that name a real firm and are not dated to the program "
            "launch. Only these set `latest_audit_at`, so a program whose whole "
            "audit list is a link to its own security page reads as undated "
            "rather than as freshly audited."
        ),
    )
    audit_records: list[AuditRecord] = Field(default_factory=list)
    latest_audit_at: date | None = None
    days_since_latest_audit: int | None = None
    auditors: list[str] = Field(default_factory=list)

    # --- 8. Protocol architecture ---
    scope_assets: list[ScopeAsset] = Field(
        default_factory=list,
        description="The full assets-in-scope table, Primacy-of-Impact placeholders included and flagged",
    )
    smart_contract_assets: int = Field(
        default=0, description="Real smart-contract assets, excluding Primacy-of-Impact placeholders"
    )
    web_app_assets: int = 0
    blockchain_dlt_assets: int = 0
    repo_scoped_assets: int = Field(
        default=0,
        description=(
            "In-scope assets that point at a repo or a path inside one rather "
            "than at a deployed address. High counts mean source-level scope, "
            "where the deployed code has to be matched back by hand."
        ),
    )
    primacy_of_impact: bool = False
    ecosystems: list[str] = Field(default_factory=list)
    program_types: list[str] = Field(default_factory=list)
    project_types: list[str] = Field(default_factory=list)
    impacts: list[ProgramImpact] = Field(
        default_factory=list, description="The program's own impact table, every severity and asset type"
    )
    critical_impacts: list[str] = Field(
        default_factory=list, description="Titles of the in-scope critical-severity impacts"
    )

    # --- Scope limits and published resources ---
    exclusions: ProgramExclusions = Field(default_factory=ProgramExclusions)
    resources: list[ProgramResource] = Field(default_factory=list)

    # --- 9. Recent upgrades / features ---
    newest_asset_added_at: date | None = None
    days_since_newest_asset: int | None = None
    assets_added_90d: int = 0
    assets_revised: int = Field(
        default=0, description="In-scope assets whose Immunefi revision counter is above zero"
    )

    # --- 11. Likely researcher competition ---
    kyc_required: bool = False
    invite_only: bool = False
    pay_to_submit: bool = Field(
        default=False,
        description=(
            "Immunefi 'Pay to Submit': the researcher pays a fee per report. Cuts "
            "both ways — a real cost shifted onto you, but also a spam filter that "
            "thins the field, so it is scored on both criterion 11 and 12."
        ),
    )
    subscription_plan: str | None = Field(
        default=None,
        description=(
            "The project's paid Immunefi tier (Essential / Pro / Elite), parsed from "
            "the 'Subscription Plan: X' feature label. This is what the PROJECT pays "
            "Immunefi, not a researcher-facing gate — exposed as context only, and "
            "deliberately left out of scoring."
        ),
    )
    researcher_level_gate: str | None = Field(
        default=None,
        description=(
            "Verbatim sentence where the program restricts submissions by Immunefi "
            "researcher level (Novice / Junior / Intermediate / …). Stored as the "
            "quote rather than a bool because whether the gate blocks YOU depends on "
            "your own level, which the scanner cannot know — so the record shows the "
            "claim and lets the reader decide. LOW RECALL by nature: the public "
            "catalogue has no structured field for this, so it is only found when a "
            "program happens to state it in prose."
        ),
    )
    immunefi_standard: bool = False
    is_boosted: bool = Field(
        default=False, description="Boost / Attackathon / audit competition — many eyes, at once"
    )
    boosted_researcher_count: int = 0
    boosted_total_paid_usd: int = 0
    program_features: list[str] = Field(default_factory=list)

    # --- 12. Historical payout / resolution quality ---
    responsible_publication_category: str | None = None
    safe_harbor: bool = False
    arbitration_available: bool = False
    pay_to_mediate: bool = False
    no_free_mediation: bool = Field(
        default=False, description="Researcher must pay to open a mediation — a dispute-cost red flag"
    )
    vault_escrow: bool = Field(
        default=False, description="Immunefi Vault — payout funds are escrowed on-chain and provable"
    )
    managed_triage: bool = False


class DiscoveredContract(BaseModel):
    """Stage 1 output: a contract above the TVL threshold, not yet enriched."""

    chain: Chain
    address: str = Field(..., description="Contract address (or Solana program/account)")
    protocol_guess: str | None = Field(
        default=None, description="Best-effort protocol name at discovery time"
    )
    tvl_usd: float
    first_seen: date
    unique_users_30d: int | None = None
    source: DiscoverySource


class EnrichedCandidate(BaseModel):
    """Stage 2 output: contract with protocol identity and metadata."""

    # Carry-forward
    chain: Chain
    address: str
    tvl_usd: float
    tvl_resolved: bool = Field(
        default=True,
        description=(
            "False when TVL could not be measured, so `tvl_usd` is 0.0 as a "
            "placeholder meaning UNKNOWN, not a measured zero. Happens when the "
            "DefiLlama name-match fails or DefiLlama carries the protocol with a "
            "null tvl. KAST reads 0.0 here — DefiLlama lists it as 'Kast Card' "
            "with tvl=null — while its two in-scope Solana programs are live and "
            "hold real value. Reporting a hard $0 for an unmeasured protocol is "
            "a false statement, so render it as unknown and score it neutrally."
        ),
    )
    first_seen: date
    unique_users_30d: int | None = None
    source: DiscoverySource

    # Enrichment
    target_name: str = Field(..., description="Canonical slug, e.g. 'factor-finance'")
    display_name: str
    protocol_type: str = Field(..., description="One-sentence classification")
    languages: list[Language]
    # URL fields are plain strings by design — see the AuditSource.url note above.
    github_repo: str | None = None
    loc_estimate: int | None = None
    docs_url: str | None = None
    bounty_program: Literal[
        "immunefi", "hackerone", "hackenproof", "cantina", "bugcrowd", "intigriti", "selfhosted", "none"
    ] = "none"
    bounty_url: str | None = None
    bounty_max_payout_usd: int | None = None
    defillama_slug: str | None = None
    defillama_audit_links: list[str] = Field(default_factory=list)
    # From DefiLlama /protocol/{slug} detail endpoint — deeper signal than the
    # flat /protocols catalog. audit_count is the integer count reported by
    # DefiLlama (may differ from len(audit_links) if some audits are linked in
    # prose elsewhere); audit_note is free-form text like "Last audited 2024-01
    # by ToB, OpenZeppelin". Both None if the detail fetch wasn't made.
    defillama_audit_count: int | None = None
    defillama_audit_note: str | None = None
    github_audits_folder_exists: bool = False
    github_audit_report_count: int = 0  # count of audit reports in the repo (saturation signal)

    # Etherscan V2 verification enrichment (EVM only; Solana records leave these blank).
    # Populated by Stage 2 via enrich/etherscan.py when the candidate has an EVM
    # address. `is_verified=False` is a RED FLAG — scanner still reports the candidate,
    # but the per-candidate file carries a warning.
    is_verified: bool | None = None
    contract_name: str | None = None
    is_proxy: bool = False
    proxy_impl_address: str | None = None
    compiler_version: str | None = None

    # Real on-chain contract address resolved from the DefiLlama detail endpoint
    # (the protocol's governance/token contract), chain-qualified as
    # "{chain}:{0xaddr}". Catalog-sourced candidates otherwise have NO contract
    # address (`address="defillama:{slug}"`) and fall back to an unreliable
    # listedAt-based age (a 180-day placeholder when listedAt is null), which
    # made the scanner blind to true protocol age. This field lets the catalog
    # path resolve the TRUE deployment date (via enrich/etherscan.py) and use it
    # as first_seen. None for pool-sourced candidates (their `address` is already
    # the real contract) and for catalog protocols with no usable EVM address.
    onchain_address: str | None = None

    # Solana on-chain program resolution (populated by enrich/solana_rpc.py for
    # DefiLlama-catalog Solana candidates). Stage 1 has no Solana leg, so a
    # catalog Solana candidate otherwise carries only a `defillama:{slug}`
    # placeholder and no auditable code pointer. The resolver walks the DefiLlama
    # TVL adapter's token account → SPL authority → owning program to recover the
    # real program id, then reads its upgrade authority. `solana_upgrade_authority_type`
    # is the load-bearing centralization signal: "single_keypair" means one key
    # can redeploy the program and reach all funds it controls. All None for EVM
    # candidates and for Solana protocols whose TVL is custodied (no custom program).
    solana_program_id: str | None = None
    solana_upgrade_authority: str | None = None
    solana_upgrade_authority_type: str | None = None

    # Pre-computed audit sources from Batch J/K detection (wrapper programs,
    # bytecode pattern matches, homepage regex hits). compute_score in stage 3
    # appends these to its all_sources list. Default empty.
    precomputed_audit_sources: list[AuditSource] = Field(default_factory=list)

    # Bounty-program target-selection profile. Populated only by the
    # immunefi-scan path (enrich/immunefi_profile.py), where the whole program
    # record is available; None for every candidate discovered by TVL, whose
    # bounty is at best a name-match with no program detail behind it. The
    # 12-criteria ranking in rank/bounty_priority.py reads it and falls back to
    # neutral sub-scores when it is None.
    bounty_profile: BountyProfile | None = None


class AuditedCandidate(EnrichedCandidate):
    """Stage 3 output: enriched candidate with audit density computed."""

    audit_density_score: int = Field(..., ge=0)
    audit_sources_found: list[AuditSource] = Field(default_factory=list)
    under_audited: bool = Field(..., description="True if audit_density_score <= 2")
    audit_record_resolved: bool = Field(
        default=True,
        description=(
            "False when NO audit source could be consulted at all — no DefiLlama "
            "audit field, no GitHub repo to inspect, and no audit URL cited in the "
            "bounty prose. A score of 0 then means 'unknown', NOT 'zero audits'. "
            "Ranking must treat unresolved as neutral, never as maximum audit gap: "
            "Pareto Credit scored 0 here while actually carrying 14 audits published "
            "only on its own docs site, and that inflated it to rank 2 of a scan."
        ),
    )


class CandidateRecord(AuditedCandidate):
    """Stage 4 final output. Serialized as YAML frontmatter per candidate file.

    The field layout mirrors VAULT_CONTEXT.md sections so Stage A can lift
    directly without a transformation layer.
    """

    # Scoring
    priority_score: float = Field(..., ge=0)
    tvl_score: float
    freshness_score: float
    audit_gap_score: float
    activity_score: float
    edge_match_score: float
    bounty_score: float

    # Which formula produced `priority_score`. "tvl" is the 6-factor discovery
    # formula (rank/priority.py); "bounty" is the 12-criteria target-selection
    # formula used by immunefi-scan (rank/bounty_priority.py). The two are NOT
    # comparable across reports — the sub-scores below are only populated by
    # the bounty formula.
    priority_formula: Literal["tvl", "bounty"] = "tvl"

    # --- 12-criteria bounty sub-scores (immunefi-scan only; None otherwise) ---
    # Named for the rubric criterion each one answers. tvl_score (1),
    # audit_gap_score (7) and edge_match_score (10) are reused from above
    # rather than duplicated.
    bounty_size_score: float | None = None  # 2. max + min bounty
    bounty_calc_score: float | None = None  # 3. how the payout is computed
    program_update_score: float | None = None  # 4. last update
    program_age_score: float | None = None  # 5. program age
    known_issues_score: float | None = None  # 6. known issues
    architecture_score: float | None = None  # 8. protocol architecture
    upgrade_activity_score: float | None = None  # 9. recent upgrades / features
    competition_score: float | None = None  # 11. likely researcher competition
    resolution_quality_score: float | None = None  # 12. historical payout / resolution

    # Stage A lift targets (derived fields)
    edge_match_keywords: list[str] = Field(default_factory=list)
    focus_areas_suggested: list[str] = Field(default_factory=list)
    inferred_platform: Literal["immunefi", "private", "unknown"] = "unknown"
    inferred_mode: Literal["bug-bounty", "competitive", "private"] = "private"

    # Metadata
    why_interesting: str = Field(..., description="One-sentence summary for report header")
    scan_date: date
    age_days: int

    @property
    def primary_contract(self) -> str:
        # Prefer the real on-chain contract resolved during enrichment. Catalog
        # candidates' `address` is the synthetic "defillama:{slug}"; the resolved
        # onchain_address is the chain-qualified governance/token contract
        # ("{chain}:0x..") and is what an auditor actually needs for the handoff.
        if self.onchain_address:
            return self.onchain_address
        return f"{self.chain.value}:{self.address}"


class FundPathChange(BaseModel):
    """One changed file on a fund-exit path between the baseline and HEAD commits.

    Emitted by the delta-watch flow. A "fund-exit path" is a file whose name
    matches one of the FUND_PATH_KEYWORDS (withdraw/redeem/borrow/liquidate/
    collateral/mint/flashloan/...). These are the surfaces where a new commit
    most plausibly introduces a permissionless-theft bug.
    """

    model_config = ConfigDict(use_enum_values=True)

    path: str = Field(..., description="Repo-relative file path that changed")
    status: str = Field(..., description="added / modified / removed / renamed")
    additions: int = Field(default=0, ge=0)
    deletions: int = Field(default=0, ge=0)
    matched_keyword: str = Field(..., description="Which FUND_PATH_KEYWORD this path matched")


class DeltaWatchResult(BaseModel):
    """Delta-watch output: a watched protocol's changes since its baseline commit.

    The baseline is, in precedence order: the known audited commit, the last
    commit this watcher checked, or (first run) the current HEAD. A result with
    `total_commits == 0` means nothing changed since the baseline.

    Field names overlap CandidateRecord where they apply (target_name,
    display_name, chains, github_repo, bounty_*, why_interesting) so a picked
    delta lifts into the same Phase 2a vault handoff as a normal scan candidate.
    """

    model_config = ConfigDict(use_enum_values=True)

    # Identity (vault-liftable)
    target_name: str
    display_name: str
    protocol_type: str = "Delta-watch target"
    languages: list[Language] = Field(default_factory=list)
    chains: list[Chain] = Field(default_factory=list)
    github_repo: str
    bounty_program: str = "none"
    bounty_max_payout_usd: int | None = None

    # Baseline / HEAD
    default_branch: str
    baseline_commit: str = Field(..., description="The ref the diff started from")
    baseline_source: Literal["audited_commit", "last_checked", "first_run"] = "first_run"
    audited_at_date: date | None = None
    head_commit: str

    # Delta
    total_commits: int = Field(default=0, ge=0, description="Commits baseline..HEAD")
    total_files_changed: int = Field(default=0, ge=0)
    fund_path_changes: list[FundPathChange] = Field(default_factory=list)
    fund_path_files_changed: int = Field(default=0, ge=0)
    fund_path_additions: int = Field(default=0, ge=0)
    notable_commits: list[str] = Field(
        default_factory=list, description="Commit subjects that touch fund-exit paths"
    )
    files_truncated: bool = Field(
        default=False, description="True if GitHub capped the compare file list (>300 files)"
    )
    unmerged_audit_branches: list[str] = Field(
        default_factory=list,
        description=(
            "Audit-named branches (audit/*, firm names) with commits not in the scoped "
            "branch — a frozen-branch/known-issue-minefield signal that damps the score."
        ),
    )

    # Ranking + metadata
    delta_score: float = Field(default=0.0, ge=0)
    why_interesting: str = ""
    checked_date: date

    @property
    def has_delta(self) -> bool:
        if self.total_commits <= 0:
            return False
        if self.fund_path_files_changed > 0:
            return True
        # File list incomplete (GitHub's 300-file cap couldn't be fully
        # resolved): a 0 fund-path count is NOT a clean negative. Fall back to
        # the commit-log signal — keyword-flagged commit subjects indicate
        # fund-path activity the truncated file scan couldn't confirm.
        return self.files_truncated and bool(self.notable_commits)


class ScanReport(BaseModel):
    """Top-level container for a single scan run, written to artifacts/scan.json."""

    scan_date: date
    chains_scanned: list[Chain]
    total_discovered: int
    total_after_threshold: int
    total_under_audited: int
    total_in_report: int
    candidates: list[CandidateRecord]
