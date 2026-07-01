"""Tests for GitHub commit-delta access (delta-watch)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from pytest_httpx import HTTPXMock

from tvl_scanner.enrich.github_delta import (
    audit_branches_ahead,
    compare_commits,
    fetch_delta,
    get_default_branch,
    get_head_sha,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def gh_compare() -> dict:
    return json.loads((FIXTURES / "github_compare_sample.json").read_text())


@pytest.fixture(autouse=True)
def _no_auth() -> None:
    """Stub the GitHub token so tests don't touch pass/env."""
    with patch("tvl_scanner.enrich.github_delta._auth_headers", return_value={}):
        yield


async def test_get_default_branch(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://api.github.com/repos/omnipair/omnipair-rs",
        json={"default_branch": "main"},
    )
    assert await get_default_branch("omnipair", "omnipair-rs") == "main"


async def test_get_default_branch_gone_repo(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://api.github.com/repos/ghost/gone",
        status_code=404,
        json={"message": "Not Found"},
    )
    assert await get_default_branch("ghost", "gone") is None


async def test_get_head_sha(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://api.github.com/repos/omnipair/omnipair-rs/commits/main",
        json={"sha": "deadbeef00000000000000000000000000000000"},
    )
    sha = await get_head_sha("omnipair", "omnipair-rs", "main")
    assert sha == "deadbeef00000000000000000000000000000000"


async def test_compare_commits_parses_commits_and_files(
    httpx_mock: HTTPXMock, gh_compare: dict
) -> None:
    httpx_mock.add_response(
        url="https://api.github.com/repos/omnipair/omnipair-rs/compare/a927600...deadbeef",
        json=gh_compare,
    )
    result = await compare_commits("omnipair", "omnipair-rs", "a927600", "deadbeef")
    assert result is not None
    assert result.total_commits == 3
    assert len(result.commits) == 3
    assert result.commits[0].subject == "fix(omnipair): validate borrow token identity"
    assert len(result.files) == 5
    borrow = next(f for f in result.files if f.filename.endswith("borrow.rs"))
    assert borrow.additions == 219
    assert borrow.status == "modified"
    assert result.truncated is False


async def test_compare_commits_unknown_ref_returns_none(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://api.github.com/repos/omnipair/omnipair-rs/compare/badref...main",
        status_code=404,
        json={"message": "Not Found"},
    )
    assert await compare_commits("omnipair", "omnipair-rs", "badref", "main") is None


async def test_compare_commits_splits_when_truncated(httpx_mock: HTTPXMock) -> None:
    """A >300-file diff is reconstructed by splitting the commit range. GitHub
    won't paginate the 300-file cap and returns files alphabetically, so paths
    that sort late (e.g. `src/`) are otherwise dropped — the split recovers them."""

    def _commits(shas: list[str]) -> list[dict]:
        return [
            {"sha": s, "commit": {"message": f"c {s}", "author": {"date": None}}} for s in shas
        ]

    capped = {
        "total_commits": 4,
        "commits": _commits(["c1", "c2", "c3", "h9"]),
        # 300 alphabetically-first files → triggers the cap; these get replaced
        # by the union of the sub-ranges below.
        "files": [
            {"filename": f"alpha/f{i}.txt", "status": "modified", "additions": 1, "deletions": 0}
            for i in range(300)
        ],
    }
    left = {
        "total_commits": 2,
        "commits": _commits(["c1", "c2"]),
        "files": [
            {"filename": "src/Borrow.sol", "status": "modified", "additions": 10, "deletions": 2},
            {"filename": "shared.txt", "status": "modified", "additions": 1, "deletions": 0},
        ],
    }
    right = {
        "total_commits": 2,
        "commits": _commits(["c3", "h9"]),
        "files": [
            {"filename": "src/Vault.sol", "status": "added", "additions": 99, "deletions": 0},
            {"filename": "shared.txt", "status": "modified", "additions": 1, "deletions": 0},
        ],
    }
    base, head = "b0", "h9"
    httpx_mock.add_response(
        url=f"https://api.github.com/repos/o/r/compare/{base}...{head}", json=capped
    )
    # mid = commits[(4 - 1) // 2] = commits[1] = "c2"
    httpx_mock.add_response(url="https://api.github.com/repos/o/r/compare/b0...c2", json=left)
    httpx_mock.add_response(url="https://api.github.com/repos/o/r/compare/c2...h9", json=right)

    result = await compare_commits("o", "r", base, head)
    assert result is not None
    assert result.total_commits == 4
    # The capped 300 are replaced by the true union of the sub-ranges (deduped).
    assert {f.filename for f in result.files} == {"src/Borrow.sol", "src/Vault.sol", "shared.txt"}
    assert result.truncated is False  # fully resolved after the split


def test_count_code_lines_distinguishes_comments_from_code() -> None:
    """Diff-patch parsing must tell comment/doc churn from real code, so a
    NatSpec / `// Last audited:` sweep is recognised as zero-code (the basis for
    dropping comment-only fund-path files)."""
    from tvl_scanner.enrich.github_delta import ChangedFile, _count_code_lines

    comment_patch = "@@ -1,2 +1,5 @@\n+// Last audited: abc\n+/**\n+ * @dev docs\n+ */\n+\n unchanged"
    assert _count_code_lines(comment_patch) == (0, 0)
    assert ChangedFile("f.sol", "modified", 5, 0, code_additions=0, code_deletions=0).is_comment_only

    code_patch = "@@ -1,1 +1,3 @@\n+    uint256 x = withdraw(a); // inline\n+// comment\n-    old();"
    assert _count_code_lines(code_patch) == (1, 1)
    assert not ChangedFile("f.sol", "modified", 2, 1, code_additions=1, code_deletions=1).is_comment_only

    # no patch → unknown → never comment-only (don't drop a real change on missing data)
    assert _count_code_lines(None) == (None, None)
    assert not ChangedFile("f.sol", "modified", 9, 0).is_comment_only


async def test_compare_commits_truncation_unresolvable_when_single_commit(
    httpx_mock: HTTPXMock,
) -> None:
    """One commit changing >300 files can't be split further → stays truncated."""
    payload = {
        "total_commits": 1,
        "commits": [{"sha": "only", "commit": {"message": "huge", "author": {"date": None}}}],
        "files": [
            {"filename": f"f{i}.sol", "status": "added", "additions": 1, "deletions": 0}
            for i in range(300)
        ],
    }
    httpx_mock.add_response(
        url="https://api.github.com/repos/o/r/compare/b0...h9", json=payload
    )
    result = await compare_commits("o", "r", "b0", "h9")
    assert result is not None
    assert result.truncated is True


async def test_fetch_delta_full_flow(httpx_mock: HTTPXMock, gh_compare: dict) -> None:
    httpx_mock.add_response(
        url="https://api.github.com/repos/omnipair/omnipair-rs",
        json={"default_branch": "main"},
    )
    httpx_mock.add_response(
        url="https://api.github.com/repos/omnipair/omnipair-rs/commits/main",
        json={"sha": "deadbeef"},
    )
    httpx_mock.add_response(
        url="https://api.github.com/repos/omnipair/omnipair-rs/compare/a927600...deadbeef",
        json=gh_compare,
    )
    out = await fetch_delta("https://github.com/omnipair/omnipair-rs", "a927600")
    assert out is not None
    branch, head, comparison = out
    assert branch == "main"
    assert head == "deadbeef"
    assert comparison is not None
    assert comparison.total_commits == 3


async def test_fetch_delta_first_run_no_baseline(httpx_mock: HTTPXMock) -> None:
    """base=None → records head, returns no comparison (first run)."""
    httpx_mock.add_response(
        url="https://api.github.com/repos/omnipair/omnipair-rs",
        json={"default_branch": "main"},
    )
    httpx_mock.add_response(
        url="https://api.github.com/repos/omnipair/omnipair-rs/commits/main",
        json={"sha": "headsha"},
    )
    out = await fetch_delta("https://github.com/omnipair/omnipair-rs", None)
    assert out is not None
    _branch, head, comparison = out
    assert head == "headsha"
    assert comparison is None  # no diff on first run


async def test_fetch_delta_base_equals_head_no_diff(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://api.github.com/repos/omnipair/omnipair-rs",
        json={"default_branch": "main"},
    )
    httpx_mock.add_response(
        url="https://api.github.com/repos/omnipair/omnipair-rs/commits/main",
        json={"sha": "samesha"},
    )
    out = await fetch_delta("https://github.com/omnipair/omnipair-rs", "samesha")
    assert out is not None
    _, head, comparison = out
    assert head == "samesha"
    assert comparison is None  # base == head → no comparison call needed


async def test_fetch_delta_unparseable_url() -> None:
    assert await fetch_delta("https://gitlab.com/foo/bar", "abc") is None


async def test_audit_branches_ahead_flags_unmerged(httpx_mock: HTTPXMock) -> None:
    """An audit-named branch with commits not in the scoped branch is flagged."""
    httpx_mock.add_response(
        url="https://api.github.com/repos/o/r/branches?per_page=100",
        json=[
            {"name": "main", "commit": {"sha": "h9"}},
            {"name": "audit/bailsec-june-2026", "commit": {"sha": "b1"}},
            {"name": "feature/x", "commit": {"sha": "f1"}},  # non-audit → ignored
        ],
    )
    httpx_mock.add_response(
        url="https://api.github.com/repos/o/r/compare/main...audit/bailsec-june-2026",
        json={"total_commits": 3, "commits": [], "files": []},  # 3 ahead → unmerged
    )
    assert await audit_branches_ahead("o", "r", "main") == ["audit/bailsec-june-2026"]


async def test_audit_branches_ahead_ignores_merged(httpx_mock: HTTPXMock) -> None:
    """An audit branch that is 0 commits ahead (already merged) is not flagged."""
    httpx_mock.add_response(
        url="https://api.github.com/repos/o/r/branches?per_page=100",
        json=[
            {"name": "main", "commit": {"sha": "h9"}},
            {"name": "cyfrin-may-2026", "commit": {"sha": "m0"}},
        ],
    )
    httpx_mock.add_response(
        url="https://api.github.com/repos/o/r/compare/main...cyfrin-may-2026",
        json={"total_commits": 0, "commits": [], "files": []},  # ancestor → merged
    )
    assert await audit_branches_ahead("o", "r", "main") == []


async def test_audit_branches_ahead_empty_on_error(httpx_mock: HTTPXMock) -> None:
    """Branch-list failure yields [] — the signal never blocks the delta."""
    httpx_mock.add_response(
        url="https://api.github.com/repos/o/r/branches?per_page=100", status_code=404
    )
    assert await audit_branches_ahead("o", "r", "main") == []
