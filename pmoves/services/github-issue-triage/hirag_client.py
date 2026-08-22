"""
Hi-RAG v2 Client

Integration with PMOVES Hi-RAG Gateway v2 for semantic search and
knowledge retrieval to support intelligent issue triage.

API Reference:
  - Query: POST http://hi-rag-gateway-v2:8086/hirag/query
  - Request: {"query": "...", "top_k": 10, "rerank": true}
"""

import logging
from typing import Optional, List, Dict, Any
import httpx

logger = logging.getLogger(__name__)


class HiRAGClient:
    """
    Client for PMOVES Hi-RAG Gateway v2

    Provides semantic search capabilities for issue triage by finding
    similar historical issues and their resolutions.
    """

    def __init__(self, base_url: str, timeout: int = 30):
        """
        Initialize Hi-RAG client

        Args:
            base_url: Hi-RAG v2 gateway URL (e.g., "http://hi-rag-gateway-v2:8086")
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.query_url = f"{self.base_url}/hirag/query"

    async def query(
        self,
        query_text: str,
        top_k: int = 10,
        rerank: bool = True,
        filters: Optional[Dict[str, Any]] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Query Hi-RAG for similar issues

        Args:
            query_text: Issue text to search for
            top_k: Number of results to return (maps to v2's ``k``)
            rerank: Whether to use cross-encoder reranking (maps to v2's ``use_rerank``)
            filters: Optional metadata filters

        Returns:
            List of similar issues with metadata, or None if query fails
        """
        try:
            # Hi-RAG v2 QueryReq (verified against the live gateway's openapi.json)
            # accepts: query, namespace, k, alpha, use_rerank, rerank_topn,
            # rerank_k, entity_types. The old top_k/rerank names were silently
            # dropped, so every query ran with service defaults instead of the
            # caller's intent.
            payload = {
                "query": query_text,
                "k": top_k,
                "use_rerank": rerank
            }

            if filters:
                payload["filters"] = filters

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.query_url,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()

                data = response.json()

                # Extract results
                if "results" in data:
                    return data["results"]
                elif isinstance(data, list):
                    return data
                else:
                    logger.warning(f"Unexpected Hi-RAG response format: {data.keys()}")
                    return None

        except httpx.TimeoutException:
            logger.error(f"Hi-RAG query timeout after {self.timeout}s")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"Hi-RAG query failed: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Hi-RAG query error: {e}")
            return None

    async def index_issue(
        self,
        repo: str,
        issue_number: int,
        title: str,
        body: str,
        labels: List[str],
        state: str = "closed"
    ) -> bool:
        """
        Index a closed issue for future semantic search

        This enables the triage service to learn from past resolutions.

        Args:
            repo: Repository name
            issue_number: Issue number
            title: Issue title
            body: Issue body
            labels: Issue labels
            state: Issue state (open/closed)

        Returns:
            True if indexing succeeded, False otherwise
        """
        try:
            # TODO: Implement indexing endpoint
            # This would call an ingestion API to add the issue to the Hi-RAG index
            # For now, we'll log it as a placeholder
            logger.info(
                f"Indexing {repo}#{issue_number} - "
                f"labels: {labels}, state: {state}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to index issue {repo}#{issue_number}: {e}")
            return False

    async def health_check(self) -> bool:
        """
        Check if Hi-RAG service is healthy

        Returns:
            True if service is responding, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.base_url}/healthz")
                response.raise_for_status()
                return True
        except Exception as e:
            logger.warning(f"Hi-RAG health check failed: {e}")
            return False

    async def index_historical_issues(
        self,
        repo: str,
        limit: int = 100,
        state: str = "closed"
    ) -> int:
        """
        Index historical issues from a repository

        This should be called on startup to build the semantic search baseline.

        Args:
            repo: Repository name
            limit: Maximum number of issues to index
            state: Issue state to index (default: closed issues with resolutions)

        Returns:
            Number of issues indexed
        """
        logger.info(f"Indexing historical issues from {repo} (limit: {limit})")

        indexed_count = 0

        try:
            # TODO: Implement GitHub API call to fetch historical issues
            # This would use the GitHub MCP tools or direct API to fetch
            # closed issues, then call index_issue() for each one

            # For now, this is a placeholder for the implementation
            logger.warning("Historical issue indexing not yet implemented")

            return indexed_count

        except Exception as e:
            logger.error(f"Failed to index historical issues: {e}")
            return indexed_count
