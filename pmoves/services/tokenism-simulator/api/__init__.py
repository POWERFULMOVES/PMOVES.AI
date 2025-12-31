"""Tokenism Simulator API endpoints.

Flask Blueprint providing REST API for:
- Running simulations (sync and async)
- Querying available scenarios and contract types
- Health checks and metrics
"""

from .simulation import simulation_bp

__all__ = ["simulation_bp"]
