"""Shared NATS types for service registries.

Provides a single SubjectEntry dataclass used across all service
NATS subject registries to avoid duplication.
"""

from dataclasses import dataclass


@dataclass
class SubjectEntry:
    subject: str
    status: str  # 'wired' | 'stub' | 'defined_only'
    stage: str  # pipeline stage or team (empty string if unused)
    subscriber_file: str  # path to subscriber code, or empty
    publisher: str  # agent/service that publishes (empty string if unused)
    notes: str
