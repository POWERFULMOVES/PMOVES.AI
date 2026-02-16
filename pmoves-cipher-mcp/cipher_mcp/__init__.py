"""
Cipher MCP Bridge - Main Package

Bridge server connecting Claude Code CLI to Cipher Memory via MCP.

Architecture:
    Claude Code (stdio MCP)
        ↓
    cipher_mcp (Python MCP server)
        ↓ HTTP
    Cipher Memory (Node.js)

Tools:
- pmoves_cipher_store: Store knowledge with category/tags
- pmoves_cipher_search: Search stored memories
- pmoves_cipher_store_reasoning: Store reasoning traces
- pmoves_cipher_reasoning_patterns: Search past reasoning
"""

__version__ = "0.1.0"
