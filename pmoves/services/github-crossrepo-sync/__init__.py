"""GitHub Cross-Repo Sync Service

Automatically synchronizes branch promotions across PMOVES.AI-Edition repositories
and their submodules when promotions occur in the main repository.

NATS Events:
  - Subscribe: github.promotion.completed.v1
  - Publish: github.crossrepo.sync.v1, github.crossrepo.sync.completed.v1,
             github.crossrepo.sync.failed.v1

API Endpoints:
  - GET /healthz - Health check
  - GET /metrics - Prometheus metrics
  - POST /api/sync - Trigger manual sync
  - GET /api/submodules - List tracked submodules
"""

from .app import app

__all__ = ['app']
