"""GitHub Cross-Repository PR Automation Service

Automates pull request creation and management across multiple PMOVES.AI
repositories for dependency updates, security patches, and feature backports.

This service provides:
- Workflow templates for common PR patterns
- Agent Zero MCP integration for GitHub operations
- NATS event coordination with other GitHub automation services
- Prometheus metrics for observability
"""

__version__ = "1.0.0"
