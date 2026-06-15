"""PMOVES Hi-RAG MCP bridge — thin MCP server over existing PMOVES retrieval APIs.

Covers three lanes the Cowork plugins expect from SaaS connectors:
Notion/Confluence-style knowledge search (Hi-RAG v2), notebook lookup
(Open Notebook), and service health probes (catalog `/healthz`).
Per the Integration Rule: leverage, don't duplicate — no retrieval is
rebuilt here; every tool is a typed HTTP passthrough.
"""

__version__ = "0.1.0"
