"""
EvoSwarm Persona Optimizer Service.

This service extends EvoSwarm to optimize persona parameters based on
performance feedback from evaluation gates.

Key Features:
- Fetches persona configuration from Supabase
- Evaluates fitness based on persona_eval_gates metrics
- Defines search spaces for temperature, behavior_weights, and boosts
- Publishes optimization results via NATS
- Integrates with consciousness namespace for geometry-aware optimization
"""

__version__ = "0.1.0"

from .persona_optimizer import PersonaOptimizer, PersonaSearchSpace, OptimizationResult

__all__ = [
    "PersonaOptimizer",
    "PersonaSearchSpace",
    "OptimizationResult",
]
