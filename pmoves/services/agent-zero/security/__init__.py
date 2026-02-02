"""
PMOVES.AI Agent Zero Security Module

This module provides security hooks for Agent Zero, implementing
defense-in-depth patterns from PMOVES-BoTZ.

Components:
- patterns.yaml: Security constitution with blocked commands and protected paths
- hooks/deterministic.py: Regex-based pre-execution validation
- hooks/probabilistic.py: LLM-based semantic safety analysis
- hooks/audit_log.py: JSONL audit trail for security and debugging
"""

__version__ = "1.0.0"
