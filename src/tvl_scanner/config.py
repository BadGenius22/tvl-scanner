"""Configuration shim.

Secrets are read from `pass` (GPG-encrypted store). Non-secret config is loaded
from `.env` via pydantic-settings. This module is the ONLY place in the codebase
that knows how secrets are stored — every other module calls `get_secret()`.

Design notes:
- pass is invoked via subprocess. Alternatives considered and rejected: the
  python-gnupg library (heavier dep, more failure modes) and direct gpg-agent
  socket (fragile across WSL/Linux/macOS).
- get_secret() is cached per-process. The scanner is a short-lived CLI so
  we never need cache invalidation.
- If pass is not installed, we fall back to environment variables (CI, testing).
  Production runs on the user's machine should always use pass.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SecretsError(RuntimeError):
    """Raised when a required secret cannot be retrieved."""


@lru_cache(maxsize=32)
def get_secret(name: str, *, required: bool = True) -> str | None:
    """Read a secret from `pass` under the `tvl-scanner/` namespace.

    Resolution order:
      1. `pass show tvl-scanner/<name>` (preferred)
      2. Environment variable `TVL_SCANNER_<NAME_UPPER>` (fallback for CI)

    Args:
        name: short key name, e.g. "github", "birdeye". NOT the full pass path.
        required: if True, raise SecretsError on miss. If False, return None.

    Returns:
        The secret string, stripped of trailing whitespace, or None.
    """
    pass_error: str | None = None
    if shutil.which("pass"):
        try:
            result = subprocess.run(
                ["pass", "show", f"tvl-scanner/{name}"],
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )
            secret = result.stdout.strip()
            if secret:
                return secret
        except subprocess.CalledProcessError as exc:
            # Distinguish "entry does not exist" from "gpg decryption failed".
            # GPG errors are surfaced so the user can fix pinentry / cache issues.
            stderr = (exc.stderr or "").lower()
            if "decryption failed" in stderr or "no such file or directory" in stderr:
                pass_error = (
                    f"pass entry exists but GPG decryption failed — likely gpg-agent needs "
                    f"a fresh passphrase. Run this once in a terminal with a TTY: "
                    f"`pass show tvl-scanner/{name} >/dev/null`"
                )
        except subprocess.TimeoutExpired as exc:
            raise SecretsError(
                f"pass show tvl-scanner/{name} timed out — is gpg-agent stuck?"
            ) from exc

    env_name = f"TVL_SCANNER_{name.upper()}"
    env_value = os.environ.get(env_name)
    if env_value:
        return env_value.strip()

    if required:
        base_msg = (
            f"Required secret 'tvl-scanner/{name}' not found. "
            f"Store it via: pass insert --echo tvl-scanner/{name} "
            f"(or set ${env_name})."
        )
        if pass_error:
            raise SecretsError(f"{base_msg}\n  Hint: {pass_error}")
        raise SecretsError(base_msg)
    return None


class Settings(BaseSettings):
    """Non-secret configuration loaded from .env or process environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Pipeline thresholds
    MIN_TVL_USD: int = 100_000
    MAX_AGE_DAYS: int = 365
    MIN_UNIQUE_USERS_30D: int = 50
    MAX_CANDIDATES_PER_SOURCE: int = 200

    # Chains
    CHAINS: str = "solana,arbitrum,base"

    # Paths
    ARTIFACTS_DIR: str = "artifacts"
    REPORTS_DIR: str = "reports"

    # API endpoints
    GECKOTERMINAL_BASE: str = "https://api.geckoterminal.com/api/v2"
    BIRDEYE_BASE: str = "https://public-api.birdeye.so"
    DEFILLAMA_BASE: str = "https://api.llama.fi"
    GITHUB_API_BASE: str = "https://api.github.com"
    C4_CONTESTS_URL: str = "https://code4rena.com/api/contests"

    # HTTP behavior
    HTTP_TIMEOUT_SECONDS: int = 30
    HTTP_MAX_RETRIES: int = 3
    HTTP_BACKOFF_SECONDS: float = 2.0

    # Logging
    LOG_LEVEL: str = "INFO"

    # Edge-match keywords — protocols matching these get a priority boost
    EDGE_MATCH_KEYWORDS: list[str] = Field(
        default_factory=lambda: [
            "leverage",
            "vault",
            "pendle",
            "aave",
            "compound",
            "silo",
            "balancer",
            "chainlink",
            "anchor",
            "noir",
            "zk",
            "passkey",
        ]
    )

    @property
    def chain_list(self) -> list[str]:
        return [c.strip() for c in self.CHAINS.split(",") if c.strip()]

    @property
    def repo_root(self) -> Path:
        return Path(__file__).resolve().parents[2]

    @property
    def artifacts_path(self) -> Path:
        return self.repo_root / self.ARTIFACTS_DIR

    @property
    def reports_path(self) -> Path:
        return self.repo_root / self.REPORTS_DIR


@lru_cache(maxsize=1)
def settings() -> Settings:
    """Singleton accessor. Reloads only when cache is cleared (tests)."""
    return Settings()  # type: ignore[call-arg]
