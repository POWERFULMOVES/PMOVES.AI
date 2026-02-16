"""
Cipher MCP Tools Definition

MCP tools exposed to Claude Code CLI for memory operations.
"""

from typing import Any, Dict, List
from mcp.types import Tool, TextContent


async def pmoves_cipher_store(
    content: str,
    category: str = "context",
    tags: List[str] = None,
    metadata: Dict[str, Any] = None,
) -> List[TextContent]:
    """
    Store knowledge in Cipher Memory.

    Categories:
    - code_pattern: Reusable code patterns and conventions
    - decision: Architectural decisions and rationale
    - context: Project-specific context
    - submodule: Submodule knowledge and configuration
    - architecture: System patterns and design
    - reasoning: Chain-of-thought reasoning traces

    Args:
        content: The knowledge content to store
        category: Memory category for organization
        tags: Optional tags for better retrieval
        metadata: Additional metadata

    Returns:
        Confirmation with memory ID
    """
    from cipher_mcp.client import CipherClient, CipherClientError

    try:
        client = CipherClient()
        memory = await client.store_memory(
            content=content,
            category=category,
            tags=tags or [],
            metadata=metadata or {},
        )

        return [TextContent(
            type="text",
            text=f"Stored memory with ID: {memory.id}\n"
                 f"Category: {memory.category}\n"
                 f"Tags: {', '.join(memory.tags) if memory.tags else 'none'}"
        )]
    except CipherClientError as e:
        return [TextContent(
            type="text",
            text=f"Failed to store memory: {e}"
        )]


async def pmoves_cipher_search(
    query: str,
    category: str = None,
    tags: List[str] = None,
    limit: int = 10,
) -> List[TextContent]:
    """
    Search stored memories in Cipher.

    Args:
        query: Search query (semantic search)
        category: Filter by category
        tags: Filter by tags
        limit: Maximum number of results

    Returns:
        Search results with relevant memories
    """
    from cipher_mcp.client import CipherClient, CipherClientError

    try:
        client = CipherClient()
        memories = await client.search_memories(
            query=query,
            category=category,
            tags=tags,
            limit=limit,
        )

        if not memories:
            return [TextContent(
                type="text",
                text=f"No memories found for query: {query}"
            )]

        results = [f"Found {len(memories)} memories for '{query}':\n"]
        for i, memory in enumerate(memories, 1):
            results.append(
                f"\n{i}. [{memory.category}] {memory.id}\n"
                f"   Tags: {', '.join(memory.tags) if memory.tags else 'none'}\n"
                f"   Content: {memory.content[:200]}{'...' if len(memory.content) > 200 else ''}\n"
            )

        return [TextContent(type="text", text="\n".join(results))]

    except CipherClientError as e:
        return [TextContent(
            type="text",
            text=f"Failed to search memories: {e}"
        )]


async def pmoves_cipher_store_reasoning(
    question: str,
    reasoning: str,
    result: str,
    metadata: Dict[str, Any] = None,
) -> List[TextContent]:
    """
    Store a reasoning trace in Cipher.

    Use this to capture complex problem-solving processes
    that can be referenced later for similar problems.

    Args:
        question: The question or problem being solved
        reasoning: Chain of thought reasoning
        result: Final result or answer
        metadata: Additional context metadata

    Returns:
        Confirmation with reasoning ID
    """
    from cipher_mcp.client import CipherClient, CipherClientError

    try:
        client = CipherClient()
        memory = await client.store_reasoning(
            question=question,
            reasoning=reasoning,
            result=result,
            metadata=metadata or {},
        )

        return [TextContent(
            type="text",
            text=f"Stored reasoning trace with ID: {memory.id}\n"
                 f"Question: {question[:100]}{'...' if len(question) > 100 else ''}"
        )]
    except CipherClientError as e:
        return [TextContent(
            type="text",
            text=f"Failed to store reasoning: {e}"
        )]


async def pmoves_cipher_reasoning_patterns(
    query: str,
    limit: int = 5,
) -> List[TextContent]:
    """
    Search past reasoning traces.

    Use this to find similar problems and their solutions.

    Args:
        query: Search query describing the problem
        limit: Maximum number of results

    Returns:
        Relevant reasoning traces
    """
    from cipher_mcp.client import CipherClient, CipherClientError

    try:
        client = CipherClient()
        memories = await client.search_reasoning(
            query=query,
            limit=limit,
        )

        if not memories:
            return [TextContent(
                type="text",
                text=f"No reasoning patterns found for: {query}"
            )]

        results = [f"Found {len(memories)} reasoning patterns:\n"]
        for i, memory in enumerate(memories, 1):
            results.append(
                f"\n{i}. {memory.id}\n"
                f"   {memory.content[:300]}{'...' if len(memory.content) > 300 else ''}\n"
            )

        return [TextContent(type="text", text="\n".join(results))]

    except CipherClientError as e:
        return [TextContent(
            type="text",
            text=f"Failed to search reasoning: {e}"
        )]


# Tool definitions for MCP server
TOOLS: List[Tool] = [
    Tool(
        name="pmoves_cipher_store",
        description="Store knowledge in Cipher Memory with categories and tags",
        inputSchema={
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The knowledge content to store"
                },
                "category": {
                    "type": "string",
                    "enum": ["code_pattern", "decision", "context", "submodule", "architecture", "reasoning"],
                    "description": "Memory category for organization",
                    "default": "context"
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional tags for better retrieval"
                },
                "metadata": {
                    "type": "object",
                    "description": "Additional metadata"
                }
            },
            "required": ["content"]
        }
    ),
    Tool(
        name="pmoves_cipher_search",
        description="Search stored memories in Cipher using semantic search",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (semantic search)"
                },
                "category": {
                    "type": "string",
                    "description": "Filter by category"
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter by tags"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results",
                    "default": 10
                }
            },
            "required": ["query"]
        }
    ),
    Tool(
        name="pmoves_cipher_store_reasoning",
        description="Store a reasoning trace for complex problem-solving",
        inputSchema={
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The question or problem being solved"
                },
                "reasoning": {
                    "type": "string",
                    "description": "Chain of thought reasoning"
                },
                "result": {
                    "type": "string",
                    "description": "Final result or answer"
                },
                "metadata": {
                    "type": "object",
                    "description": "Additional context metadata"
                }
            },
            "required": ["question", "reasoning", "result"]
        }
    ),
    Tool(
        name="pmoves_cipher_reasoning_patterns",
        description="Search past reasoning traces for similar problems",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query describing the problem"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results",
                    "default": 5
                }
            },
            "required": ["query"]
        }
    ),
]

# Tool handler mapping
TOOL_HANDLERS = {
    "pmoves_cipher_store": pmoves_cipher_store,
    "pmoves_cipher_search": pmoves_cipher_search,
    "pmoves_cipher_store_reasoning": pmoves_cipher_store_reasoning,
    "pmoves_cipher_reasoning_patterns": pmoves_cipher_reasoning_patterns,
}


__all__ = [
    "TOOLS",
    "TOOL_HANDLERS",
    "pmoves_cipher_store",
    "pmoves_cipher_search",
    "pmoves_cipher_store_reasoning",
    "pmoves_cipher_reasoning_patterns",
]
