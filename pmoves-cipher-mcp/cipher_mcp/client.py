"""
Cipher Memory HTTP Client

Communicates with the Cipher Memory Node.js service via HTTP.
"""

import asyncio
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import httpx


@dataclass
class MemoryItem:
    """Memory item returned from Cipher."""
    id: str
    content: str
    category: str
    tags: List[str]
    created_at: str
    embedding_id: Optional[str] = None
    reasoning_id: Optional[str] = None


class CipherClientError(Exception):
    """Base exception for Cipher client errors."""
    pass


class CipherConnectionError(CipherClientError):
    """Connection error."""
    pass


class CipherAPIError(CipherClientError):
    """API error response."""
    pass


class CipherClient:
    """
    HTTP client for Cipher Memory service.

    Cipher Memory provides:
    - Store memory with embeddings (Qdrant)
    - Search by semantic similarity
    - Store reasoning traces (knowledge graph)
    - Query reasoning patterns
    """

    def __init__(
        self,
        base_url: str = None,
        timeout: float = 5.0,
    ):
        """
        Initialize Cipher client.

        Args:
            base_url: Cipher service URL (default: from CIPHER_URL env)
            timeout: HTTP request timeout
        """
        from pmoves_registry import get_cipher_url

        self.base_url = base_url or get_cipher_url()
        self.timeout = timeout
        self._token = os.getenv("CIPHER_API_TOKEN", "")

    def _get_headers(self) -> dict:
        """Get auth headers if token is configured."""
        if self._token:
            return {"Authorization": f"Bearer {self._token}"}
        return {}

    def _get_client(self) -> httpx.AsyncClient:
        """Get HTTP client with configured timeout and auth headers."""
        return httpx.AsyncClient(
            timeout=self.timeout,
            headers=self._get_headers(),
        )

    async def health_check(self) -> Dict[str, Any]:
        """
        Check Cipher service health.

        Returns:
            Health status dictionary

        Raises:
            CipherConnectionError: If connection fails
        """
        async with self._get_client() as client:
            try:
                response = await client.get(f"{self.base_url}/health")
                response.raise_for_status()
                return response.json()
            except httpx.ConnectError as e:
                raise CipherConnectionError(f"Cannot connect to Cipher at {self.base_url}: {e}")
            except httpx.HTTPStatusError as e:
                raise CipherAPIError(f"Health check failed: {e.response.status_code}")

    async def store_memory(
        self,
        content: str,
        category: str = "context",
        tags: List[str] = None,
        metadata: Dict[str, Any] = None,
    ) -> MemoryItem:
        """
        Store a memory in Cipher.

        Args:
            content: Memory content
            category: Memory category (code_pattern, decision, context, etc.)
            tags: Optional tags for retrieval
            metadata: Additional metadata

        Returns:
            Created memory item

        Raises:
            CipherAPIError: If storage fails
        """
        async with self._get_client() as client:
            payload = {
                "content": content,
                "category": category,
                "tags": tags or [],
                "metadata": metadata or {},
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

            try:
                response = await client.post(
                    f"{self.base_url}/api/memory",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

                return MemoryItem(
                    id=data["id"],
                    content=content,
                    category=category,
                    tags=tags or [],
                    created_at=payload["created_at"],
                    embedding_id=data.get("embedding_id"),
                )
            except httpx.ConnectError as e:
                raise CipherConnectionError(f"Cannot connect to Cipher: {e}")
            except httpx.HTTPStatusError as e:
                raise CipherAPIError(f"Store failed: {e.response.status_code} - {e.response.text}")

    async def search_memories(
        self,
        query: str,
        category: str = None,
        tags: List[str] = None,
        limit: int = 10,
    ) -> List[MemoryItem]:
        """
        Search memories by semantic similarity.

        Args:
            query: Search query
            category: Filter by category
            tags: Filter by tags
            limit: Max results

        Returns:
            List of matching memories
        """
        async with self._get_client() as client:
            params = {
                "q": query,
                "limit": limit,
            }
            if category:
                params["category"] = category
            if tags:
                params["tags"] = ",".join(tags)

            try:
                response = await client.get(
                    f"{self.base_url}/api/memory/search",
                    params=params,
                )
                response.raise_for_status()
                data = response.json()

                return [
                    MemoryItem(
                        id=item["id"],
                        content=item["content"],
                        category=item.get("category", "context"),
                        tags=item.get("tags", []),
                        created_at=item.get("created_at", ""),
                    )
                    for item in data.get("results", [])
                ]
            except httpx.ConnectError as e:
                raise CipherConnectionError(f"Cannot connect to Cipher: {e}")
            except httpx.HTTPStatusError as e:
                raise CipherAPIError(f"Search failed: {e.response.status_code}")

    async def store_reasoning(
        self,
        question: str,
        reasoning: str,
        result: str,
        category: str = "reasoning",
        metadata: Dict[str, Any] = None,
    ) -> MemoryItem:
        """
        Store a reasoning trace.

        Args:
            question: The question or problem
            reasoning: Chain of thought reasoning
            result: Final result or answer
            category: Memory category
            metadata: Additional metadata

        Returns:
            Created reasoning item
        """
        content = f"Q: {question}\n\nReasoning:\n{reasoning}\n\nResult:\n{result}"
        return await self.store_memory(
            content=content,
            category=category,
            metadata=metadata or {},
        )

    async def search_reasoning(
        self,
        query: str,
        limit: int = 5,
    ) -> List[MemoryItem]:
        """
        Search past reasoning traces.

        Args:
            query: Search query
            limit: Max results

        Returns:
            List of matching reasoning traces
        """
        return await self.search_memories(
            query=query,
            category="reasoning",
            limit=limit,
        )

    async def get_memory(self, memory_id: str) -> Optional[MemoryItem]:
        """
        Get a specific memory by ID.

        Args:
            memory_id: Memory ID

        Returns:
            Memory item or None if not found
        """
        async with self._get_client() as client:
            try:
                response = await client.get(f"{self.base_url}/api/memory/{memory_id}")
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                data = response.json()

                return MemoryItem(
                    id=data["id"],
                    content=data["content"],
                    category=data.get("category", "context"),
                    tags=data.get("tags", []),
                    created_at=data.get("created_at", ""),
                )
            except httpx.ConnectError as e:
                raise CipherConnectionError(f"Cannot connect to Cipher: {e}")

    async def delete_memory(self, memory_id: str) -> bool:
        """
        Delete a memory by ID.

        Args:
            memory_id: Memory ID

        Returns:
            True if deleted
        """
        async with self._get_client() as client:
            try:
                response = await client.delete(f"{self.base_url}/api/memory/{memory_id}")
                response.raise_for_status()
                return True
            except httpx.HTTPStatusError:
                return False


__all__ = [
    "CipherClient",
    "MemoryItem",
    "CipherClientError",
    "CipherConnectionError",
    "CipherAPIError",
]
