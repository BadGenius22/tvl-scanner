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
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class Chain(str, Enum):
    ETHEREUM = "ethereum"
    ARBITRUM = "arbitrum"
    BASE = "base"
    OPTIMISM = "optimism"
    POLYGON = "polygon"
    BSC = "bsc"
    SOLANA = "solana"


class Language(str, Enum):
    SOLIDITY = "solidity"
    RUST = "rust"
    MOVE = "move"


class DiscoverySource(str, Enum):
    GECKOTERMINAL = "geckoterminal"
    BIRDEYE = "birdeye"
    DEFILLAMA_CATALOG = "defillama_catalog"
    ALCHEMY_DEPLOYMENTS = "alchemy_deployments"
    RPC_ACTIVE_HOLDERS = "rpc_active_holders"
    FACTORY_EVENTS = "factory_events"
    DUNE = "dune"
    FLIPSIDE = "flipside"
    EXPLORER_VERIFIED = "explorer_verified"


class AuditSourceKind(str, Enum):
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


class AuditSource(BaseModel):
    """One evidence item for a prior audit of a protocol."""

    model_config = ConfigDict(use_enum_values=True)

    source: AuditSourceKind
    url: HttpUrl | None = None
    published_at: date | None = None
    title: str | None = None
    weight: int = Field(default=1, ge=0, description="Points contributed to audit_density_score")


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
    first_seen: date
    unique_users_30d: int | None = None
    source: DiscoverySource

    # Enrichment
    target_name: str = Field(..., description="Canonical slug, e.g. 'factor-finance'")
    display_name: str
    protocol_type: str = Field(..., description="One-sentence classification")
    languages: list[Language]
    github_repo: HttpUrl | None = None
    loc_estimate: int | None = None
    docs_url: HttpUrl | None = None
    bounty_program: Literal["immunefi", "hackerone", "hackenproof", "cantina", "selfhosted", "none"] = "none"
    bounty_url: HttpUrl | None = None
    bounty_max_payout_usd: int | None = None
    defillama_slug: str | None = None
    defillama_audit_links: list[HttpUrl] = Field(default_factory=list)
    # From DefiLlama /protocol/{slug} detail endpoint — deeper signal than the
    # flat /protocols catalog. audit_count is the integer count reported by
    # DefiLlama (may differ from len(audit_links) if some audits are linked in
    # prose elsewhere); audit_note is free-form text like "Last audited 2024-01
    # by ToB, OpenZeppelin". Both None if the detail fetch wasn't made.
    defillama_audit_count: int | None = None
    defillama_audit_note: str | None = None
    github_audits_folder_exists: bool = False

    # Etherscan V2 verification enrichment (EVM only; Solana records leave these blank).
    # Populated by Stage 2 via enrich/etherscan.py when the candidate has an EVM
    # address. `is_verified=False` is a RED FLAG — scanner still reports the candidate,
    # but the per-candidate file carries a warning.
    is_verified: bool | None = None
    contract_name: str | None = None
    is_proxy: bool = False
    proxy_impl_address: str | None = None
    compiler_version: str | None = None

    # Pre-computed audit sources from Batch J/K detection (wrapper programs,
    # bytecode pattern matches, homepage regex hits). compute_score in stage 3
    # appends these to its all_sources list. Default empty.
    precomputed_audit_sources: list[AuditSource] = Field(default_factory=list)


class AuditedCandidate(EnrichedCandidate):
    """Stage 3 output: enriched candidate with audit density computed."""

    audit_density_score: int = Field(..., ge=0)
    audit_sources_found: list[AuditSource] = Field(default_factory=list)
    under_audited: bool = Field(..., description="True if audit_density_score <= 2")


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

    # Ranking + metadata
    delta_score: float = Field(default=0.0, ge=0)
    why_interesting: str = ""
    checked_date: date

    @property
    def has_delta(self) -> bool:
        return self.total_commits > 0 and self.fund_path_files_changed > 0


class ScanReport(BaseModel):
    """Top-level container for a single scan run, written to artifacts/scan.json."""

    scan_date: date
    chains_scanned: list[Chain]
    total_discovered: int
    total_after_threshold: int
    total_under_audited: int
    total_in_report: int
    candidates: list[CandidateRecord]
