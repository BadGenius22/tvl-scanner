"""Tests for the pure recon signal extractor (tree + content greps)."""

from __future__ import annotations

from tvl_scanner.recon.signals import extract_signals
from tvl_scanner.recon.sources import RepoSnapshot


def _snap(paths: list[str], contents: dict[str, str] | None = None) -> RepoSnapshot:
    return RepoSnapshot(
        owner="o",
        repo="r",
        ref="abc123def0",
        paths=paths,
        sizes={p: len(contents.get(p, "")) if contents else 0 for p in paths},
        contents=contents or {},
    )


def test_none_snapshot_yields_all_unknown() -> None:
    sig = extract_signals(None)
    assert sig.source_files is None
    assert sig.test_files is None
    assert sig.privileged_markers is None
    assert sig.oracle_markers is None
    assert sig.toolchain == "unknown"


def test_tree_signals_split_source_vs_tests() -> None:
    sig = extract_signals(
        _snap(
            [
                "src/Vault.sol",
                "src/oracle/PriceFeed.sol",
                "test/Vault.t.sol",
                "tests/unit/test_vault.rs",
                "README.md",  # non-code: not source, not test
                "foundry.toml",
                ".github/workflows/ci.yml",
            ]
        )
    )
    assert sig.source_files == 2
    assert sig.test_files == 2
    assert sig.has_ci is True
    assert sig.toolchain == "foundry"


def test_hardhat_and_other_toolchains() -> None:
    assert extract_signals(_snap(["hardhat.config.ts", "contracts/A.sol"])).toolchain == "hardhat"
    assert extract_signals(_snap(["contracts/A.sol"])).toolchain == "other"
    assert extract_signals(_snap([])).toolchain == "unknown"


def test_fund_path_files_use_delta_classifier() -> None:
    sig = extract_signals(
        _snap(["src/WithdrawHandler.sol", "src/Frontend.sol", "docs/withdraw.md"])
    )
    # docs/withdraw.md is excluded by the classifier (non-code extension)
    assert sig.fund_path_files == 1


def test_content_markers_counted_per_family() -> None:
    src = (
        "contract V {\n"
        "  function pull() external onlyOwner {}\n"        # onlyOwner
        "  function set() external onlyRole(ADMIN) {}\n"   # onlyRole(
        "  function go() external {\n"
        "    require(msg.sender == keeper);\n"             # msg.sender ==
        "  }\n"
        "  function initialize() initializer {} \n"        # initialize( + initializer
        "  uint256 price = feed.latestRoundData();\n"      # latestRoundData
        "  (uint112 r0, , , ) = pair.getReserves();\n"     # getReserves
        "  AggregatorV3Interface agg;\n"                   # AggregatorV3
        "}\n"
    )
    sig = extract_signals(_snap(["src/V.sol"], {"src/V.sol": src}))
    assert sig.privileged_markers == 3
    assert sig.initializer_markers == 2  # `initializer` + `function initialize(`
    assert sig.oracle_markers == 3
    assert sig.scanned_loc == src.count("\n") + 1


def test_rust_anchor_access_markers() -> None:
    src = (
        "#[program]\n"
        "pub mod vault {\n"
        "  #[access_control(Checks::Price)]\n"
        "  pub fn withdraw(ctx: Context<Withdraw>) -> Result<()> {\n"
        "    has_authority!(ctx.accounts.user, &ctx.accounts.vault.authority)?;\n"
        "    require_auth!(ctx.accounts.vault)?;\n"
        "    Ok(())\n"
        "  }\n"
        "}\n"
    )
    sig = extract_signals(_snap(["programs/vault/src/lib.rs"], {"programs/vault/src/lib.rs": src}))
    assert sig.rust_access_markers == 3
    assert sig.source_files == 1


def test_reentrancy_guard_markers_counted() -> None:
    sig = extract_signals(
        _snap(["src/A.sol"], {"src/A.sol": "function f() external nonReentrant {}\n"})
    )
    assert sig.reentrancy_guard_markers == 1


def test_latest_price_not_excluded_as_test() -> None:
    """Path-segment awareness: 'latest_price.rs' contains 'test_' as a
    substring of 'latest_' but must count as production source."""
    sig = extract_signals(_snap(["src/latest_price.rs"]))
    assert sig.source_files == 1
    assert sig.test_files == 0
