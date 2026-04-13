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
    bounty_program: Literal["immunefi", "hackerone", "hackenproof", "none"] = "none"
    bounty_url: HttpUrl | None = None
    bounty_max_payout_usd: int | None = None
    defillama_slug: str | None = None
    defillama_audit_links: list[HttpUrl] = Field(default_factory=list)
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


class ScanReport(BaseModel):
    """Top-level container for a single scan run, written to artifacts/scan.json."""

    scan_date: date
    chains_scanned: list[Chain]
    total_discovered: int
    total_after_threshold: int
    total_under_audited: int
    total_in_report: int
    candidates: list[CandidateRecord]
