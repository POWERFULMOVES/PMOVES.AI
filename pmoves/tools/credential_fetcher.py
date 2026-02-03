"""
Active Credential Fetcher for PMOVES.AI

Fetches credentials from multiple active sources:
- GitHub Actions Secrets API (requires authentication)
- Docker registry credentials (~/.docker/config.json)
- Existing env files (for merging)

This module provides both library functions and CLI commands.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import base64
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import yaml

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

DEFAULT_GITHUB_API_BASE = "https://api.github.com"
DEFAULT_DOCKER_CONFIG = Path.home() / ".docker" / "config.json"


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class FetchResult:
    """Result of a credential fetch operation."""
    source: str
    credentials: Dict[str, str] = field(default_factory=dict)
    success: bool = True
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "credentials": self.credentials,
            "success": self.success,
            "error": self.error,
            "metadata": self.metadata,
        }


@dataclass
class GitHubSecret:
    """GitHub Actions Secret representation."""
    name: str
    value: str


# =============================================================================
# Utility Functions
# =============================================================================

def _is_credential_key(key: str) -> bool:
    """Check if a key looks like a credential (contains sensitive suffixes)."""
    sensitive_suffixes = ("_KEY", "_TOKEN", "_SECRET", "_PASSWORD", "_AUTH", "_API_KEY")
    return key.endswith(sensitive_suffixes)


def _mask_value(value: str, visible: int = 4) -> str:
    """Mask a credential value for display.

    Args:
        value: The credential value to mask
        visible: Number of characters to show at start

    Returns:
        Masked value (e.g., "skja...xyz")
    """
    if len(value) <= visible + 3:
        return "***"
    return value[:visible] + "..." + value[-3:]


def _mask_credentials_for_display(credentials: Dict[str, str]) -> Dict[str, str]:
    """Mask credential values for safe display.

    Args:
        credentials: Dictionary of credential key/value pairs

    Returns:
        Dictionary with sensitive values masked
    """
    masked = {}
    for key, value in credentials.items():
        if _is_credential_key(key):
            masked[key] = _mask_value(value)
        else:
            masked[key] = value
    return masked


# =============================================================================
# GitHub Secrets Fetcher
# =============================================================================

class GitHubSecretsFetcher:
    """
    Active fetcher for GitHub Actions Secrets.

    Requires a GitHub Personal Access Token (PAT) with:
    - repo:admin scope for repository secrets
    - admin:org scope for organization secrets

    Usage:
        fetcher = GitHubSecretsFetcher()
        secrets = await fetcher.fetch_repository_secrets("owner", "repo")
    """

    def __init__(
        self,
        token: Optional[str] = None,
        token_file: Optional[Path] = None,
        api_base: str = DEFAULT_GITHUB_API_BASE,
    ):
        """
        Initialize GitHub Secrets fetcher.

        Args:
            token: GitHub PAT (defaults to GITHUB_PAT env var)
            token_file: Path to file containing token (defaults to ~/.github-pat)
            api_base: GitHub API base URL
        """
        self._token = token
        self._token_file = token_file or Path.home() / ".github-pat"
        self._api_base = api_base.rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_token(self) -> str:
        """Get GitHub PAT from env, file, or prompt."""
        if self._token:
            return self._token

        # Try environment variable
        token = os.environ.get("GITHUB_PAT") or os.environ.get("GITHUB_TOKEN")
        if token:
            return token

        # Try file
        if self._token_file.exists():
            return self._token_file.read_text().strip()

        raise RuntimeError(
            "GitHub PAT not found. Set GITHUB_PAT env var, "
            f"create {self._token_file}, or pass token parameter."
        )

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            token = await self._get_token()
            self._client = httpx.AsyncClient(
                base_url=self._api_base,
                headers={
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {token}",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> Any:
        """Make authenticated API request."""
        client = await self._get_client()
        response = await client.request(method, path, **kwargs)

        if response.status_code == 204:
            return None

        response.raise_for_status()
        return response.json()

    async def list_repository_secrets(
        self,
        owner: str,
        repo: str,
    ) -> List[str]:
        """
        List all secret names in a repository.

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            List of secret names
        """
        try:
            data = await self._request(
                "GET",
                f"/repos/{owner}/{repo}/actions/secrets",
            )
            return [s["name"] for s in data.get("secrets", [])]
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to list secrets for {owner}/{repo}: {e}")
            return []

    async def get_repository_secret(
        self,
        owner: str,
        repo: str,
        secret_name: str,
    ) -> Optional[GitHubSecret]:
        """
        Get a single secret from a repository.

        Note: This only gets metadata, not the actual value.
        To get the value, you need to use the Actions API directly
        or have the secret value in your env.shared.

        Args:
            owner: Repository owner
            repo: Repository name
            secret_name: Name of the secret

        Returns:
            GitHubSecret with metadata (value will be None)
        """
        try:
            data = await self._request(
                "GET",
                f"/repos/{owner}/{repo}/actions/secrets/{secret_name}",
            )
            return GitHubSecret(
                name=data["name"],
                value="",  # GitHub API doesn't return values
                created_at=data.get("created_at"),
                updated_at=data.get("updated_at"),
            )
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to get secret {secret_name}: {e}")
            return None

    async def fetch_repository_secrets(
        self,
        owner: str,
        repo: str,
        secret_names: Optional[List[str]] = None,
        env_map: Optional[Dict[str, str]] = None,
    ) -> FetchResult:
        """
        Fetch repository secrets with optional value mapping.

        Since GitHub API doesn't return secret values directly,
        this method:
        1. Lists available secrets (metadata only)
        2. Maps secret names to expected environment variable names

        To get actual values, you must:
        - Have them in your local environment
        - Use GitHub CLI: gh secret list
        - Use the env.shared file as source of truth

        Args:
            owner: Repository owner
            repo: Repository name
            secret_names: Optional list of secrets to fetch (default: all)
            env_map: Optional mapping of secret_name -> env_var_name

        Returns:
            FetchResult with secret metadata
        """
        # Default mapping: secret name to env var (uppercase)
        if env_map is None:
            env_map = {}

        # List all secrets
        all_secrets = await self.list_repository_secrets(owner, repo)
        if secret_names:
            secrets_to_fetch = [s for s in secret_names if s in all_secrets]
        else:
            secrets_to_fetch = all_secrets

        credentials: Dict[str, str] = {}

        # Try to get values from environment (common pattern)
        for secret in secrets_to_fetch:
            env_name = env_map.get(secret, secret.upper())
            value = os.environ.get(env_name)

            if value:
                credentials[env_name] = value
                logger.debug(f"Found {env_name} in environment")
            else:
                # Record that secret exists but value is not available
                credentials[f"{secret}_exists"] = "true"
                logger.warning(f"Secret {secret} exists but value not in environment")

        return FetchResult(
            source=f"github:{owner}/{repo}",
            credentials=credentials,
            success=True,
            metadata={
                "total_secrets": len(all_secrets),
                "fetched": len(secrets_to_fetch),
                "with_values": len([v for v in credentials.values() if v and v != "true"]),
            },
        )

    async def fetch_organization_secrets(
        self,
        org: str,
        secret_names: Optional[List[str]] = None,
    ) -> FetchResult:
        """
        List organization secrets.

        Args:
            org: Organization name
            secret_names: Optional list of secrets to fetch

        Returns:
            FetchResult with secret metadata
        """
        try:
            data = await self._request(
                "GET",
                f"/orgs/{org}/actions/secrets",
            )
            all_secrets = [s["name"] for s in data.get("secrets", [])]

            if secret_names:
                secrets_to_fetch = [s for s in secret_names if s in all_secrets]
            else:
                secrets_to_fetch = all_secrets

            credentials: Dict[str, str] = {}

            for secret in secrets_to_fetch:
                env_name = secret.upper()
                value = os.environ.get(env_name)
                if value:
                    credentials[env_name] = value

            return FetchResult(
                source=f"github:org/{org}",
                credentials=credentials,
                success=True,
                metadata={
                    "total_secrets": len(all_secrets),
                    "fetched": len(secrets_to_fetch),
                },
            )
        except httpx.HTTPStatusError as e:
            return FetchResult(
                source=f"github:org/{org}",
                credentials={},
                success=False,
                error=str(e),
            )


# =============================================================================
# Docker Credentials Fetcher
# =============================================================================

class DockerCredentialsFetcher:
    """
    Fetch Docker registry credentials from Docker config.

    Reads from ~/.docker/config.json which contains auth tokens
    for various Docker registries.
    """

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize Docker credentials fetcher.

        Args:
            config_path: Path to Docker config.json
        """
        self._config_path = config_path or DEFAULT_DOCKER_CONFIG

    def fetch(self) -> FetchResult:
        """
        Fetch Docker registry credentials.

        Returns:
            FetchResult with registry credentials
        """
        if not self._config_path.exists():
            return FetchResult(
                source="docker",
                credentials={},
                success=False,
                error=f"Docker config not found: {self._config_path}",
            )

        try:
            config = json.loads(self._config_path.read_text())
            credentials: Dict[str, str] = {}

            # Extract auths
            for registry, auth_data in config.get("auths", {}).items():
                if "auth" in auth_data:
                    # Decode base64 auth (username:password)
                    try:
                        decoded = base64.b64decode(auth_data["auth"]).decode()
                        username, password = decoded.split(":", 1)
                        credentials[f"DOCKER_{registry.upper().replace('.', '_')}_USERNAME"] = username
                        credentials[f"DOCKER_{registry.upper().replace('.', '_')}_PASSWORD"] = password
                    except Exception:
                        # Store raw auth if decode fails
                        credentials[f"DOCKER_{registry.upper().replace('.', '_')}_AUTH"] = auth_data["auth"]

            # Extract credsStore (credential helpers)
            if "credsStore" in config:
                credentials["DOCKER_CREDS_STORE"] = config["credsStore"]

            return FetchResult(
                source="docker",
                credentials=credentials,
                success=True,
                metadata={
                    "registries": len(config.get("auths", {})),
                    "creds_store": config.get("credsStore"),
                },
            )
        except Exception as e:
            return FetchResult(
                source="docker",
                credentials={},
                success=False,
                error=str(e),
            )


# =============================================================================
# Environment File Fetcher
# =============================================================================

class EnvFileFetcher:
    """Fetch credentials from environment files."""

    def __init__(self, env_paths: Optional[List[Path]] = None):
        """
        Initialize env file fetcher.

        Args:
            env_paths: List of env file paths to read
        """
        self._env_paths = env_paths or []

    def fetch(self, env_path: Optional[Path] = None) -> FetchResult:
        """
        Fetch credentials from an env file.

        Args:
            env_path: Specific env file to read (uses default paths if not provided)

        Returns:
            FetchResult with env variables
        """
        paths = [env_path] if env_path else self._env_paths
        credentials: Dict[str, str] = {}

        for path in paths:
            if not path or not path.exists():
                continue

            try:
                for line in path.read_text().splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, value = line.split("=", 1)
                        credentials[key.strip()] = value.strip()
            except Exception as e:
                logger.warning(f"Failed to read {path}: {e}")

        return FetchResult(
            source=f"env_file:{env_path or 'multiple'}",
            credentials=credentials,
            success=len(credentials) > 0,
        )


# =============================================================================
# Universal Credential Fetcher (Main Entry Point)
# =============================================================================

class CredentialFetcher:
    """
    Universal credential fetcher that combines all sources.

    Priority order (highest to lowest):
    1. Environment variables (already loaded)
    2. GitHub Secrets (with env values)
    3. Docker config credentials
    4. Env files
    5. CHIT CGP files (if specified)
    """

    def __init__(
        self,
        github_token: Optional[str] = None,
        docker_config: Optional[Path] = None,
        env_paths: Optional[List[Path]] = None,
    ):
        """
        Initialize universal credential fetcher.

        Args:
            github_token: Optional GitHub PAT
            docker_config: Optional path to Docker config
            env_paths: Optional list of env file paths
        """
        self._github_token = github_token
        self._docker_config = docker_config
        self._env_paths = env_paths
        self._github_fetcher = GitHubSecretsFetcher(token=github_token)
        self._docker_fetcher = DockerCredentialsFetcher(config_path=docker_config)
        self._env_fetcher = EnvFileFetcher(env_paths=env_paths)

    async def fetch_all(
        self,
        github_owner: Optional[str] = None,
        github_repo: Optional[str] = None,
        include_docker: bool = True,
        include_env: bool = True,
        env_file: Optional[Path] = None,
    ) -> Dict[str, str]:
        """
        Fetch credentials from all available sources.

        Args:
            github_owner: Optional GitHub owner for repo secrets
            github_repo: Optional GitHub repo name
            include_docker: Include Docker credentials
            include_env: Include env file credentials
            env_file: Specific env file to read

        Returns:
            Combined credentials dictionary
        """
        all_credentials: Dict[str, str] = {}
        results: List[FetchResult] = []

        # 1. Environment (already loaded, just capture)
        for key, value in os.environ.items():
            if any(key.endswith(suffix) for suffix in ["_KEY", "_TOKEN", "_SECRET", "_PASSWORD", "_API_KEY"]):
                all_credentials[key] = value

        logger.debug(f"Loaded {len(all_credentials)} credentials from environment")

        # 2. GitHub Secrets (if repo specified)
        if github_owner and github_repo:
            try:
                result = await self._github_fetcher.fetch_repository_secrets(
                    github_owner, github_repo
                )
                results.append(result)
                all_credentials.update(result.credentials)
                logger.info(f"GitHub: {result.metadata}")
            except Exception as e:
                logger.warning(f"GitHub fetch failed: {e}")

        # 3. Docker credentials
        if include_docker:
            try:
                result = self._docker_fetcher.fetch()
                results.append(result)
                all_credentials.update(result.credentials)
                if result.success:
                    logger.info(f"Docker: {result.metadata}")
            except Exception as e:
                logger.warning(f"Docker fetch failed: {e}")

        # 4. Env files
        if include_env:
            try:
                if env_file:
                    result = self._env_fetcher.fetch(env_file)
                else:
                    result = self._env_fetcher.fetch()
                results.append(result)
                all_credentials.update(result.credentials)
                logger.info(f"Env file: {len(result.credentials)} credentials")
            except Exception as e:
                logger.warning(f"Env file fetch failed: {e}")

        await self.close()

        return all_credentials

    async def close(self) -> None:
        """Close all fetchers."""
        await self._github_fetcher.close()

    def fetch_all_sync(
        self,
        github_owner: Optional[str] = None,
        github_repo: Optional[str] = None,
        include_docker: bool = True,
        include_env: bool = True,
        env_file: Optional[Path] = None,
    ) -> Dict[str, str]:
        """
        Synchronous wrapper for fetch_all.

        Args:
            github_owner: Optional GitHub owner
            github_repo: Optional GitHub repo
            include_docker: Include Docker credentials
            include_env: Include env file credentials
            env_file: Specific env file to read

        Returns:
            Combined credentials dictionary
        """
        return asyncio.run(self.fetch_all(
            github_owner=github_owner,
            github_repo=github_repo,
            include_docker=include_docker,
            include_env=include_env,
            env_file=env_file,
        ))


# =============================================================================
# CLI Functions
# =============================================================================

def fetch_credentials_to_env_shared(
    output_path: Optional[Path] = None,
    github_owner: Optional[str] = None,
    github_repo: Optional[str] = None,
    include_docker: bool = True,
) -> Dict[str, str]:
    """
    Fetch credentials and write to env.shared file.

    Args:
        output_path: Output path for env.shared (default: pmoves/env.shared)
        github_owner: Optional GitHub owner
        github_repo: Optional GitHub repo
        include_docker: Include Docker credentials

    Returns:
        Dictionary of fetched credentials
    """
    if output_path is None:
        output_path = Path.cwd() / "pmoves" / "env.shared"

    fetcher = CredentialFetcher()
    credentials = fetcher.fetch_all_sync(
        github_owner=github_owner,
        github_repo=github_repo,
        include_docker=include_docker,
        include_env=True,
        env_file=output_path if output_path.exists() else None,
    )

    # Write to env.shared
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# PMOVES.AI Shared Credentials",
        "# Auto-generated by credential_fetcher.py",
        f"# Source: GitHub={github_owner}/{github_repo if github_owner and github_repo else 'none'}, "
        f"Docker={include_docker}",
        "# DO NOT commit this file to git",
        "",
    ]

    for key in sorted(credentials.keys()):
        value = credentials[key]
        # Sanitize value (avoid overly long lines)
        if len(value) > 100:
            value = value[:97] + "..."
        lines.append(f"{key}={value}")

    output_path.write_text("\n".join(lines) + "\n")

    logger.info(f"Wrote {len(credentials)} credentials to {output_path}")

    return credentials


# =============================================================================
# Main Entry Point
# =============================================================================

def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Active Credential Fetcher for PMOVES.AI"
    )
    parser.add_argument(
        "action",
        choices=["fetch", "list-github", "list-docker", "to-env-shared"],
        help="Action to perform",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output file for 'to-env-shared' action",
    )
    parser.add_argument(
        "--github-owner",
        help="GitHub repository owner",
    )
    parser.add_argument(
        "--github-repo",
        help="GitHub repository name",
    )
    parser.add_argument(
        "--github-token",
        help="GitHub PAT (or set GITHUB_PAT env var)",
    )
    parser.add_argument(
        "--no-docker",
        action="store_true",
        help="Skip Docker credentials",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        help="Additional env file to read",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output",
    )

    args = parser.parse_args(argv)

    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    try:
        if args.action == "to-env-shared":
            credentials = fetch_credentials_to_env_shared(
                output_path=args.output,
                github_owner=args.github_owner,
                github_repo=args.github_repo,
                include_docker=not args.no_docker,
            )

            if args.json:
                # Mask credentials for safe display in JSON
                masked = _mask_credentials_for_display(credentials)
                print(json.dumps(masked, indent=2))
            else:
                print(f"Fetched {len(credentials)} credentials")

        elif args.action == "fetch":
            fetcher = CredentialFetcher(github_token=args.github_token)
            credentials = fetcher.fetch_all_sync(
                github_owner=args.github_owner,
                github_repo=args.github_repo,
                include_docker=not args.no_docker,
                env_file=args.env_file,
            )

            if args.json:
                # Mask credentials for safe display in JSON
                masked = _mask_credentials_for_display(credentials)
                print(json.dumps(masked, indent=2))
            else:
                for key, value in sorted(credentials.items()):
                    if _is_credential_key(key):
                        value = "***"
                    elif len(value) > 50:
                        value = value[:47] + "..."
                    print(f"{key}={value}")

        elif args.action == "list-github":
            if not args.github_owner or not args.github_repo:
                print("Error: --github-owner and --github-repo required for list-github")
                return 1

            async def list_secrets():
                fetcher = GitHubSecretsFetcher(token=args.github_token)
                secrets = await fetcher.list_repository_secrets(
                    args.github_owner, args.github_repo
                )
                await fetcher.close()
                return secrets

            secrets = asyncio.run(list_secrets())

            if args.json:
                print(json.dumps(secrets, indent=2))
            else:
                print(f"Found {len(secrets)} secrets:")
                for secret in secrets:
                    print(f"  - {secret}")

        elif args.action == "list-docker":
            fetcher = DockerCredentialsFetcher()
            result = fetcher.fetch()

            if args.json:
                print(json.dumps(result.to_dict(), indent=2))
            else:
                if result.success:
                    print(f"Docker registries: {result.metadata.get('registries', 0)}")
                    print(f"Creds store: {result.metadata.get('creds_store', 'none')}")
                    for key, value in sorted(result.credentials.items()):
                        if "PASSWORD" in key or "AUTH" in key:
                            value = "***"
                        print(f"  {key}={value}")
                else:
                    print(f"Error: {result.error}")
                    return 1

        return 0

    except Exception as e:
        logger.error(f"Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
