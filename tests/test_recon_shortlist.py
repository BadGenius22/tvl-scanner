"""Tests for recon shortlist selection and the ranked-artifact roundtrip."""

from __future__ import annotations

import json
from datetime import date

import pytest

from tvl_scanner.models import (
    BountyProfile,
    CandidateRecord,
    Chain,
    DiscoverySource,
    Language,
)
from tvl_scanner.rank.report import write_ranked
from tvl_scanner.recon.shortlist import (
    ShortlistError,
    load_ranked,
    scope_branch,
    select_shortlist,
)


def _record(
    name: str,
    *,
    tvl: float = 5_000_000.0,
    formula: str = "tvl",
    github: str | None = "https://github.com/org/repo",
    profile: BountyProfile | None = None,
    resolved: bool = True,
) -> CandidateRecord:
    return CandidateRecord(
        chain=Chain.ETHEREUM,
        address=f"0x{name}",
        tvl_usd=tvl,
        tvl_resolved=resolved,
        first_seen=date(2026, 1, 1),
        source=DiscoverySource.DEFILLAMA_CATALOG,
        target_name=name,
        display_name=name.replace("-", " ").title(),
        protocol_type="Lending on ethereum",
        languages=[Language.SOLIDITY],
        github_repo=github,
        audit_density_score=1,
        under_audited=True,
        priority_score=7.0,
        tvl_score=8.0,
        freshness_score=6.0,
        audit_gap_score=8.0,
        activity_score=5.0,
        edge_match_score=5.0,
        bounty_score=0.0,
        priority_formula=formula,  # type: ignore[arg-type]
        why_interesting="test record",
        scan_date=date(2026, 8, 24),
        age_days=100,
        bounty_profile=profile,
    )


def _write_ranked(path, records: list[CandidateRecord], formula: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "label": "x",
                "scan_date": "2026-08-24",
                "priority_formula": formula,
                "candidates": [r.model_dump(mode="json") for r in records],
            }
        )
    )


# ---- write_ranked / load_ranked roundtrip ----


def test_write_ranked_and_load_roundtrip(tmp_path) -> None:
    rec = _record("alpha")
    out = write_ranked([rec], date(2026, 8, 24), "scan", path=tmp_path / "ranked-scan.json")
    assert out.is_file()
    loaded = load_ranked("scan", path=out)
    assert len(loaded) == 1
    assert loaded[0].target_name == "alpha"
    assert loaded[0].priority_formula == "tvl"


def test_load_ranked_missing_artifact_raises(tmp_path) -> None:
    with pytest.raises(ShortlistError):
        load_ranked("scan", path=tmp_path / "nope.json")


def test_load_ranked_garbage_raises(tmp_path) -> None:
    p = tmp_path / "ranked-scan.json"
    p.write_text("{not json")
    with pytest.raises(ShortlistError):
        load_ranked("scan", path=p)


def test_load_ranked_skips_unvalidatable_records(tmp_path) -> None:
    p = tmp_path / "ranked-scan.json"
    _write_ranked(p, [_record("alpha")], "tvl")
    data = json.loads(p.read_text())
    data["candidates"].insert(0, {"target_name": "broken"})  # missing required fields
    p.write_text(json.dumps(data))
    loaded = load_ranked("scan", path=p)
    assert [c.target_name for c in loaded] == ["alpha"]


# ---- select_shortlist ----


def test_union_interleaves_and_prefers_immunefi_on_duplicate(tmp_path) -> None:
    run_path = tmp_path / "ranked-scan.json"
    imm_path = tmp_path / "ranked-immunefi-scan.json"
    _write_ranked(
        run_path,
        [
            _record("shared", formula="tvl", github=None),
            _record("run-only", formula="tvl"),
        ],
        "tvl",
    )
    _write_ranked(
        imm_path,
        [
            _record("shared", formula="bounty", github="https://github.com/i/s"),
            _record("imm-only", formula="bounty"),
        ],
        "bounty",
    )
    sel = select_shortlist(
        from_="union", top=10, paths={"run": run_path, "immunefi": imm_path}
    )
    # Positional interleave: run-only is rank 2 of its list, imm-only rank 2 of
    # the other; run's #2 wins the second slot because dedupe promoted run-only
    # to position 2 of the merged sequence.
    names = [c.target_name for c in sel.candidates]
    assert names == ["shared", "run-only", "imm-only"]
    # the immunefi record won the dedupe (its repo survived)
    assert sel.candidates[0].github_repo == "https://github.com/i/s"
    assert sel.source_of["shared"] == "immunefi"
    assert sel.source_of["run-only"] == "run"


def test_single_source_selects_only_that_list(tmp_path) -> None:
    run_path = tmp_path / "ranked-scan.json"
    _write_ranked(run_path, [_record("a"), _record("b")], "tvl")
    sel = select_shortlist(from_="run", top=10, paths={"run": run_path})
    assert [c.target_name for c in sel.candidates] == ["a", "b"]
    assert sel.source_of["a"] == "run"


def test_min_tvl_drops_are_counted(tmp_path) -> None:
    run_path = tmp_path / "ranked-scan.json"
    _write_ranked(
        run_path,
        [
            _record("big", tvl=10_000_000.0),
            _record("small", tvl=50_000.0),
            _record("unresolved", tvl=0.0, resolved=False),
        ],
        "tvl",
    )
    sel = select_shortlist(from_="run", top=10, min_tvl=100_000, paths={"run": run_path})
    names = [c.target_name for c in sel.candidates]
    assert names == ["big", "unresolved"]  # unresolved TVL stays eligible (neutral)
    assert sel.funnel.total_dropped == 1
    assert any("TVL below" in r for r, _ in sel.funnel.rows())


def test_top_cap_counts_the_remainder(tmp_path) -> None:
    run_path = tmp_path / "ranked-scan.json"
    _write_ranked(run_path, [_record(f"c{i}") for i in range(5)], "tvl")
    sel = select_shortlist(from_="run", top=2, paths={"run": run_path})
    assert len(sel.candidates) == 2
    assert sel.funnel.total_dropped == 3
    assert any("beyond --top" in r for r, _ in sel.funnel.rows())


def test_missing_single_source_raises(tmp_path) -> None:
    with pytest.raises(ShortlistError):
        select_shortlist(from_="run", top=5, paths={"run": tmp_path / "nope.json"})


def test_union_with_one_missing_source_notes_and_proceeds(tmp_path) -> None:
    imm_path = tmp_path / "ranked-immunefi-scan.json"
    _write_ranked(imm_path, [_record("imm", formula="bounty")], "bounty")
    sel = select_shortlist(
        from_="union", top=5, paths={"run": tmp_path / "nope.json", "immunefi": imm_path}
    )
    assert [c.target_name for c in sel.candidates] == ["imm"]
    assert any("unavailable" in n for n in sel.notes)


def test_targets_filter_selects_explicitly(tmp_path) -> None:
    run_path = tmp_path / "ranked-scan.json"
    _write_ranked(run_path, [_record("a"), _record("b"), _record("c")], "tvl")
    sel = select_shortlist(from_="run", top=10, targets={"b"}, paths={"run": run_path})
    assert [c.target_name for c in sel.candidates] == ["b"]
    assert sel.funnel.total_dropped == 2


# ---- scope_branch ----


def test_scope_branch_parses_tree_ref() -> None:
    from tvl_scanner.models import ScopeAsset

    profile = BountyProfile(
        scope_assets=[
            ScopeAsset(
                asset_type="smart_contract",
                url="https://github.com/org/repo/tree/dev/src",
                repo="org/repo/tree/dev/src",
            )
        ]
    )
    rec = _record("x", profile=profile)
    assert scope_branch(rec) == "dev"


def test_scope_branch_absent_without_profile_or_plain_repo() -> None:
    from tvl_scanner.models import ScopeAsset

    assert scope_branch(_record("x")) is None
    profile = BountyProfile(
        scope_assets=[
            ScopeAsset(
                asset_type="smart_contract",
                url="https://etherscan.io/address/0x123",
                repo=None,
            )
        ]
    )
    assert scope_branch(_record("x", profile=profile)) is None
