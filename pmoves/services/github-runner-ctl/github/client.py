"""
GitHub API client for runner management.

Handles authentication, rate limiting, and API calls to GitHub
for runner status, workflow runs, and job information.
"""

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

import httpx

from metrics import GITHUB_API_REQUESTS_TOTAL, GITHUB_API_RATE_LIMIT
from nats_publisher import NATSPublisher

logger = logging.getLogger("github-runner-ctl")


class GitHubClient:
    """GitHub API client with authentication and rate limit tracking.

    Uses a Personal Access Token (PAT) from a file for authentication.
    """

    def __init__(
        self,
        pat_file: str = "/run/secrets/github_pat",
        nats_publisher: Optional[NATSPublisher] = None,
    ):
        """Initialize GitHub client.

        Args:
            pat_file: Path to file containing GitHub Personal Access Token
            nats_publisher: Optional NATS publisher for events
        """
        self.pat_file = pat_file
        self._pat: Optional[str] = None
        self._base_url = "https://api.github.com"
        self._client: Optional[httpx.AsyncClient] = None
        self._nats = nats_publisher
        self._rate_limit_remaining: Dict[str, int] = {}

    @property
    def is_authenticated(self) -> bool:
        """Check if client has valid PAT."""
        return self._pat is not None

    async def _load_pat(self) -> bool:
        """Load Personal Access Token from file.

        Returns:
            True if token loaded successfully
        """
        try:
            with open(self.pat_file, "r") as f:
                self._pat = f.read().strip()
            return bool(self._pat)
        except FileNotFoundError:
            logger.error(f"GitHub PAT file not found: {self.pat_file}")
            return False
        except Exception as e:
            logger.error(f"Failed to load GitHub PAT: {e}")
            return False

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with auth headers.

        Returns:
            Authenticated httpx.AsyncClient
        """
        if self._client is None or self._client.is_closed:
            if not self._pat and not await self._load_pat():
                raise RuntimeError("GitHub PAT not available")

            headers = {
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self._pat}",
                "X-GitHub-Api-Version": "2022-11-28",
            }
            timeout = httpx.Timeout(30.0, connect=10.0)
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers=headers,
                timeout=timeout,
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Make authenticated request to GitHub API.

        Args:
            method: HTTP method
            path: API path (without base URL)
            **kwargs: Additional arguments for httpx request

        Returns:
            Parsed JSON response

        Raises:
            httpx.HTTPStatusError: On API errors
        """
        client = await self._get_client()
        endpoint = path.split("?")[0]  # Remove query string for metrics

        try:
            response = await client.request(method, path, **kwargs)

            # Track rate limit
            remaining = response.headers.get("x-ratelimit-remaining")
            if remaining:
                user = "default"  # Could parse from PAT if needed
                self._rate_limit_remaining[user] = int(remaining)
                GITHUB_API_RATE_LIMIT.labels(user=user).set(int(remaining))

            # Track request metrics
            status = str(response.status_code)
            GITHUB_API_REQUESTS_TOTAL.labels(endpoint=endpoint, status=status).inc()

            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(f"GitHub API error: {e.response.status_code} {path}")
            GITHUB_API_REQUESTS_TOTAL.labels(endpoint=endpoint, status=str(e.response.status_code)).inc()
            raise

    async def get_runners(
        self,
        owner: str,
        repo: str,
    ) -> List[Dict[str, Any]]:
        """Get list of self-hosted runners for a repository.

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            List of runner data
        """
        path = f"/repos/{owner}/{repo}/actions/runners"
        data = await self._request("GET", path)
        return data.get("runners", [])

    async def get_runner(
        self,
        owner: str,
        repo: str,
        runner_id: int,
    ) -> Dict[str, Any]:
        """Get specific runner details.

        Args:
            owner: Repository owner
            repo: Repository name
            runner_id: Runner ID

        Returns:
            Runner data
        """
        path = f"/repos/{owner}/{repo}/actions/runners/{runner_id}"
        return await self._request("GET", path)

    async def get_organization_runners(
        self,
        org: str,
    ) -> List[Dict[str, Any]]:
        """Get list of self-hosted runners for an organization.

        Args:
            org: Organization name

        Returns:
            List of runner data
        """
        path = f"/orgs/{org}/actions/runners"
        data = await self._request("GET", path)
        return data.get("runners", [])

    async def delete_runner(
        self,
        owner: str,
        repo: str,
        runner_id: int,
    ) -> bool:
        """Delete a runner from GitHub.

        Args:
            owner: Repository owner
            repo: Repository name
            runner_id: Runner ID

        Returns:
            True if deleted successfully
        """
        path = f"/repos/{owner}/{repo}/actions/runners/{runner_id}"
        await self._request("DELETE", path)
        return True

    async def get_workflow_runs(
        self,
        owner: str,
        repo: str,
        status: Optional[str] = None,
        per_page: int = 30,
    ) -> List[Dict[str, Any]]:
        """Get workflow runs for a repository.

        Args:
            owner: Repository owner
            repo: Repository name
            status: Filter by status (queued, in_progress, completed, etc.)
            per_page: Results per page

        Returns:
            List of workflow runs
        """
        path = f"/repos/{owner}/{repo}/actions/runs"
        params = {"per_page": per_page}
        if status:
            params["status"] = status
        data = await self._request("GET", path, params=params)
        return data.get("workflow_runs", [])

    async def get_workflow_run_jobs(
        self,
        owner: str,
        repo: str,
        run_id: int,
    ) -> List[Dict[str, Any]]:
        """Get jobs for a workflow run.

        Args:
            owner: Repository owner
            repo: Repository name
            run_id: Workflow run ID

        Returns:
            List of jobs
        """
        path = f"/repos/{owner}/{repo}/actions/runs/{run_id}/jobs"
        data = await self._request("GET", path)
        return data.get("jobs", [])

    async def get_queue_status(
        self,
        owner: str,
        repo: str,
    ) -> Dict[str, Any]:
        """Get current queue depth for a repository.

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            Queue status with counts
        """
        # Get queued workflow runs
        queued_runs = await self.get_workflow_runs(owner, repo, status="queued")

        # Get in-progress runs to estimate active jobs
        in_progress = await self.get_workflow_runs(owner, repo, status="in_progress")

        return {
            "queued": len(queued_runs),
            "in_progress": len(in_progress),
            "total_queued": len(queued_runs),
        }

    async def list_repositories(
        self,
        org: Optional[str] = None,
        per_page: int = 100,
    ) -> List[Dict[str, Any]]:
        """List repositories to monitor.

        Args:
            org: Optional organization to filter by
            per_page: Results per page

        Returns:
            List of repositories
        """
        if org:
            path = f"/orgs/{org}/repos"
        else:
            path = "/user/repos?type=owner"

        params = {"per_page": per_page}
        return await self._request("GET", path, params=params)


class RunnerMonitor:
    """Monitor runner status across configured repositories."""

    def __init__(
        self,
        github_client: GitHubClient,
        runners: List[str],  # List of "owner/repo" or "org" strings
        nats_publisher: NATSPublisher,
    ):
        """Initialize runner monitor.

        Args:
            github_client: GitHub API client
            runners: List of repository/org identifiers
            nats_publisher: NATS publisher for events
        """
        self.github = github_client
        self.runners = runners
        self._nats = nats_publisher
        self._runner_status: Dict[str, Dict[str, Any]] = {}

    async def refresh_all(self) -> Dict[str, Any]:
        """Refresh status of all configured runners.

        Returns:
            Summary of runner status
        """
        results = {
            "online": 0,
            "offline": 0,
            "busy": 0,
            "runners": [],
        }

        for identifier in self.runners:
            if "/" in identifier:
                # Repository runner
                owner, repo = identifier.split("/", 1)
                try:
                    runners = await self.github.get_runners(owner, repo)
                    for runner in runners:
                        status = self._process_runner(runner, identifier)
                        results["runners"].append(status)
                        if status["status"] == "online":
                            results["online"] += 1
                        elif status["status"] == "busy":
                            results["busy"] += 1
                        else:
                            results["offline"] += 1
                except Exception as e:
                    logger.error(f"Failed to get runners for {identifier}: {e}")
            else:
                # Organization runner
                try:
                    runners = await self.github.get_organization_runners(identifier)
                    for runner in runners:
                        status = self._process_runner(runner, identifier)
                        results["runners"].append(status)
                        if status["status"] == "online":
                            results["online"] += 1
                        elif status["status"] == "busy":
                            results["busy"] += 1
                        else:
                            results["offline"] += 1
                except Exception as e:
                    logger.error(f"Failed to get org runners for {identifier}: {e}")

        return results

    def _process_runner(
        self,
        runner: Dict[str, Any],
        source: str,
    ) -> Dict[str, Any]:
        """Process runner data from API.

        Args:
            runner: Raw runner data from API
            source: Source repository/org

        Returns:
            Processed runner status
        """
        runner_id = runner.get("id")
        name = runner.get("name")
        busy = runner.get("busy", False)
        status = "busy" if busy else "online"

        # Store for tracking
        self._runner_status[str(runner_id)] = {
            "id": runner_id,
            "name": name,
            "status": status,
            "source": source,
            "os": runner.get("os"),
            "labels": [l.get("name") for l in runner.get("labels", [])],
        }

        return {
            "id": runner_id,
            "name": name,
            "status": status,
            "source": source,
            "os": runner.get("os"),
            "labels": [l.get("name") for l in runner.get("labels", [])],
        }
