"""Agent Zero MCP Client for GitHub Operations

Integrates with Agent Zero's MCP API to perform GitHub operations
such as creating PRs, merging PRs, and adding comments.
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass
class GitHubTokenResponse:
    """Response from GitHub token minting."""
    token: str
    expires_at: str
    installation_id: int
    repository: str


@dataclass
class PRCreateResult:
    """Result from PR creation."""
    success: bool
    pr_number: Optional[int]
    pr_url: Optional[str]
    error: Optional[str]


@dataclass
class PRMergeResult:
    """Result from PR merge."""
    success: bool
    merged: bool
    error: Optional[str]


@dataclass
class CommentResult:
    """Result from comment creation."""
    success: bool
    comment_id: Optional[int]
    error: Optional[str]


class AgentZeroMCPClient:
    """Client for Agent Zero MCP GitHub operations."""

    def __init__(
        self,
        mcp_url: str = "http://agent-zero:8080/mcp/command",
        timeout: float = 30.0
    ):
        """Initialize Agent Zero MCP client.

        Args:
            mcp_url: Agent Zero MCP endpoint URL
            timeout: Request timeout in seconds
        """
        self.mcp_url = mcp_url
        self.timeout = timeout
        self.http_client = httpx.AsyncClient(timeout=timeout)

    async def close(self):
        """Close HTTP client."""
        await self.http_client.aclose()

    async def _call_mcp_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call Agent Zero MCP tool.

        Args:
            tool_name: Name of the MCP tool to call
            parameters: Tool parameters

        Returns:
            Tool response data

        Raises:
            httpx.HTTPError: If request fails
        """
        try:
            response = await self.http_client.post(
                f"{self.mcp_url}/tools/{tool_name}",
                json=parameters)
            response.raise_for_status()
            data = response.json()

            if data.get("error"):
                raise Exception(data["error"])

            return data.get("result", data)

        except httpx.HTTPError as e:
            logger.error(f"Agent Zero MCP request failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error calling MCP tool {tool_name}: {e}")
            raise

    async def mint_github_token(
        self,
        repository: str = "PMOVES.AI",
        installation_id: Optional[int] = None
    ) -> GitHubTokenResponse:
        """Mint GitHub App installation token.

        Args:
            repository: Repository name
            installation_id: Specific installation ID (optional)

        Returns:
            GitHubTokenResponse with token details

        Raises:
            Exception: If token minting fails
        """
        try:
            parameters = {"repository": repository}
            if installation_id:
                parameters["installation_id"] = installation_id

            result = await self._call_mcp_tool(
                "github_mint_token",
                parameters
            )

            return GitHubTokenResponse(
                token=result["token"],
                expires_at=result.get("expires_at", ""),
                installation_id=result.get("installation_id", 0),
                repository=result.get("repository", repository)
            )

        except Exception as e:
            logger.error(f"Failed to mint GitHub token: {e}")
            raise

    async def create_pull_request(
        self,
        repo: str,
        title: str,
        body: str,
        head: str,
        base: str,
        labels: Optional[List[str]] = None,
        reviewers: Optional[List[str]] = None,
        assignees: Optional[List[str]] = None,
        draft: bool = False,
        organization: str = "POWERFULMOVES"
    ) -> PRCreateResult:
        """Create a pull request via GitHub API.

        Args:
            repo: Repository name
            title: PR title
            body: PR body/description
            head: Source branch
            base: Target branch
            labels: Labels to add (optional)
            reviewers: Reviewers to request (optional)
            assignees: Users to assign (optional)
            draft: Create as draft PR
            organization: GitHub organization name

        Returns:
            PRCreateResult with PR details
        """
        try:
            # Mint token first
            token_response = await self.mint_github_token(repo)

            # Call GitHub MCP tool to create PR
            result = await self._call_mcp_tool(
                "github_create_pr",
                {
                    "repo": repo,
                    "organization": organization,
                    "title": title,
                    "body": body,
                    "head": head,
                    "base": base,
                    "labels": labels or [],
                    "reviewers": reviewers or [],
                    "assignees": assignees or [],
                    "draft": draft,
                    "token": token_response.token
                }
            )

            return PRCreateResult(
                success=True,
                pr_number=result.get("number"),
                pr_url=result.get("html_url"),
                error=None
            )

        except Exception as e:
            logger.error(f"Failed to create PR: {e}")
            return PRCreateResult(
                success=False,
                pr_number=None,
                pr_url=None,
                error="Internal client error"
            )

    async def merge_pull_request(
        self,
        repo: str,
        pr_number: int,
        merge_method: str = "squash",
        commit_title: Optional[str] = None,
        commit_message: Optional[str] = None,
        organization: str = "POWERFULMOVES"
    ) -> PRMergeResult:
        """Merge a pull request via GitHub API.

        Args:
            repo: Repository name
            pr_number: PR number
            merge_method: Merge method (merge, squash, rebase)
            commit_title: Custom commit title (optional)
            commit_message: Custom commit message (optional)
            organization: GitHub organization name

        Returns:
            PRMergeResult with merge status
        """
        try:
            # Mint token first
            token_response = await self.mint_github_token(repo)

            # Call GitHub MCP tool to merge PR
            result = await self._call_mcp_tool(
                "github_merge_pr",
                {
                    "repo": repo,
                    "organization": organization,
                    "pr_number": pr_number,
                    "merge_method": merge_method,
                    "commit_title": commit_title,
                    "commit_message": commit_message,
                    "token": token_response.token
                }
            )

            return PRMergeResult(
                success=True,
                merged=result.get("merged", False),
                error=None
            )

        except Exception as e:
            logger.error(f"Failed to merge PR #{pr_number}: {e}")
            return PRMergeResult(
                success=False,
                merged=False,
                error="Internal client error"
            )

    async def add_comment(
        self,
        repo: str,
        pr_number: int,
        body: str,
        organization: str = "POWERFULMOVES"
    ) -> CommentResult:
        """Add comment to pull request.

        Args:
            repo: Repository name
            pr_number: PR number
            body: Comment body
            organization: GitHub organization name

        Returns:
            CommentResult with comment details
        """
        try:
            # Mint token first
            token_response = await self.mint_github_token(repo)

            # Call GitHub MCP tool to add comment
            result = await self._call_mcp_tool(
                "github_add_comment",
                {
                    "repo": repo,
                    "organization": organization,
                    "pr_number": pr_number,
                    "body": body,
                    "token": token_response.token
                }
            )

            return CommentResult(
                success=True,
                comment_id=result.get("id"),
                error=None
            )

        except Exception as e:
            logger.error(f"Failed to add comment to PR #{pr_number}: {e}")
            return CommentResult(
                success=False,
                comment_id=None,
                error="Internal client error"
            )

    async def update_pr_branch(
        self,
        repo: str,
        pr_number: int,
        organization: str = "POWERFULMOVES"
    ) -> bool:
        """Update pull request branch with latest base.

        Args:
            repo: Repository name
            pr_number: PR number
            organization: GitHub organization name

        Returns:
            True if update successful
        """
        try:
            # Mint token first
            token_response = await self.mint_github_token(repo)

            # Call GitHub MCP tool to update branch
            await self._call_mcp_tool(
                "github_update_pr_branch",
                {
                    "repo": repo,
                    "organization": organization,
                    "pr_number": pr_number,
                    "token": token_response.token
                }
            )

            return True

        except Exception as e:
            logger.error(f"Failed to update PR #{pr_number} branch: {e}")
            return False

    async def list_prs(
        self,
        repo: str,
        state: str = "open",
        base: Optional[str] = None,
        organization: str = "POWERFULMOVES"
    ) -> List[Dict[str, Any]]:
        """List pull requests for a repository.

        Args:
            repo: Repository name
            state: PR state (open, closed, all)
            base: Filter by base branch (optional)
            organization: GitHub organization name

        Returns:
            List of PR dictionaries
        """
        try:
            # Mint token first
            await self.mint_github_token(repo)

            # Call GitHub MCP tool to list PRs
            result = await self._call_mcp_tool(
                "github_list_prs",
                {
                    "repo": repo,
                    "organization": organization,
                    "state": state,
                    "base": base
                }
            )

            return result.get("pull_requests", [])

        except Exception as e:
            logger.error(f"Failed to list PRs for {repo}: {e}")
            return []
