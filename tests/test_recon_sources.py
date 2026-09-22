"""Tests for the recon repo-snapshot fetcher: extraction, guards, cache, HTTP."""

from __future__ import annotations

import io
import tarfile

import pytest
from pytest_httpx import HTTPXMock

from tvl_scanner.recon.sources import (
    RepoSnapshot,
    _extract_snapshot,
    _safe_rel_path,
    fetch_snapshot,
)


def _tar_gz(members: dict[str, str | bytes]) -> bytes:
    buf = io.BytesIO()
    root = "repo-abc123/"  # GitHub tarball root: {repo}-{sha}/
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, content in members.items():
            data = content.encode() if isinstance(content, str) else content
            info = tarfile.TarInfo(root + name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def test_safe_rel_path_strips_root_and_rejects_traversal() -> None:
    assert _safe_rel_path("repo-abc/src/A.sol") == "src/A.sol"
    assert _safe_rel_path("repo-abc/src/../../../etc/passwd") is None
    assert _safe_rel_path("/abs/path.sol") is None
    assert _safe_rel_path("repo-abc/dir/") is None
    assert _safe_rel_path("") is None


def test_extract_separates_code_contents_from_tree_paths() -> None:
    data = _tar_gz(
        {
            "src/Vault.sol": "contract Vault {}\n",
            "README.md": "# docs\n",
            "package.json": "{}",
        }
    )
    snap = _extract_snapshot("o", "r", "abc123def0", data)
    assert isinstance(snap, RepoSnapshot)
    assert sorted(snap.paths) == ["README.md", "package.json", "src/Vault.sol"]
    assert set(snap.contents) == {"src/Vault.sol"}
    assert snap.complete is True


def test_extract_skips_oversized_file_contents() -> None:
    big = b"x" * (1_000_000 + 1)
    snap = _extract_snapshot("o", "r", "abc", _tar_gz({"src/Big.sol": big}))
    assert "src/Big.sol" in snap.paths
    assert "src/Big.sol" not in snap.contents


def test_extract_bad_tarball_raises_tar_error() -> None:
    with pytest.raises(tarfile.TarError):
        _extract_snapshot("o", "r", "abc", b"not a tarball at all")


async def test_fetch_snapshot_downloads_and_caches(httpx_mock: HTTPXMock, tmp_path) -> None:
    url = "https://api.github.com/repos/o/r/tarball/deadbeef12"
    httpx_mock.add_response(url=url, content=_tar_gz({"src/A.sol": "contract A {}\n"}))
    cache = str(tmp_path / "cache")

    snap = await fetch_snapshot("o", "r", "deadbeef12", cache_dir=cache)
    assert snap is not None
    assert snap.contents["src/A.sol"] == "contract A {}\n"

    # Second call: served from cache (no HTTP mock registered → any request fails)
    snap2 = await fetch_snapshot("o", "r", "deadbeef12", cache_dir=cache)
    assert snap2 is not None
    assert snap2.contents["src/A.sol"] == "contract A {}\n"

    # refresh=True bypasses the cache and re-downloads
    httpx_mock.add_response(url=url, content=_tar_gz({"src/B.sol": "contract B {}\n"}))
    snap3 = await fetch_snapshot("o", "r", "deadbeef12", cache_dir=cache, refresh=True)
    assert snap3 is not None
    assert set(snap3.contents) == {"src/B.sol"}


async def test_fetch_snapshot_http_failure_returns_none(
    httpx_mock: HTTPXMock, tmp_path
) -> None:
    httpx_mock.add_response(
        url="https://api.github.com/repos/o/r/tarball/deadbeef12", status_code=404
    )
    snap = await fetch_snapshot("o", "r", "deadbeef12", cache_dir=str(tmp_path / "c"))
    assert snap is None


async def test_fetch_snapshot_rejects_oversized_tarball(
    httpx_mock: HTTPXMock, tmp_path, monkeypatch
) -> None:
    from tvl_scanner.config import settings

    monkeypatch.setattr(settings(), "RECON_MAX_TARBALL_MB", 0)  # cap: 0 bytes
    httpx_mock.add_response(
        url="https://api.github.com/repos/o/r/tarball/deadbeef12",
        content=_tar_gz({"src/A.sol": "x"}),
        headers={"content-length": "1024"},
    )
    snap = await fetch_snapshot("o", "r", "deadbeef12", cache_dir=str(tmp_path / "c"))
    assert snap is None


async def test_get_bytes_returns_body(httpx_mock: HTTPXMock) -> None:
    from tvl_scanner.http import get_bytes

    httpx_mock.add_response(url="https://example.com/blob", content=b"payload")
    assert await get_bytes("https://example.com/blob") == b"payload"
