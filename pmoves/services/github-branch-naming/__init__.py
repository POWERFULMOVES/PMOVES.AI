"""GitHub Branch Naming Enforcement Service

Validates branch names against PMOVES.AI conventions:
- feat/ - New features
- fix/ - Bug fixes
- chore/ - Maintenance tasks
- docs/ - Documentation updates
- codex/ - CODEX-generated branches
- ref/docs/ - Reference documentation branches

Protected branches (no validation):
- PMOVES.AI-Edition-Hardened
- PMOVES.AI-Edition-Hardened-Integrations
- main
"""

from .app import app

__all__ = ['app']
