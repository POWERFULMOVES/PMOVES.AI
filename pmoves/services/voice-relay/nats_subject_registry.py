"""Voice NATS Subject Registry.

Tracks voice-related NATS subjects from TAC trees.
Generated: 2026-04-17
Source: pmoves/configs/tac_trees/
"""

from typing import List
from dataclasses import dataclass


@dataclass
class SubjectEntry:
    subject: str
    status: str  # 'wired' | 'defined_only'
    subscriber_file: str
    notes: str


SUBJECT_REGISTRY: List[SubjectEntry] = [
    SubjectEntry(
        "voice.agent.response.v1",
        "wired",
        "pmoves/services/voice-relay/main.py",
        "JetStream publish with ack — P1-3 wiring applied",
    ),
    SubjectEntry("voice.cast.request.v1", "defined_only", "", "TAC-defined, no subscriber yet"),
    SubjectEntry("voice.cast.completed.v1", "defined_only", "", "TAC-defined, no subscriber yet"),
    SubjectEntry("voice.cast.failed.v1", "defined_only", "", "TAC-defined, no subscriber yet"),
    SubjectEntry("voice.training.request.v1", "defined_only", "", "TAC-defined, no subscriber yet"),
    SubjectEntry("tokenism.prosodic.bpm.v1", "defined_only", "", "Flute gateway, TAC-defined"),
    SubjectEntry("device.cast.discovered.v1", "defined_only", "", "TAC-defined, no subscriber yet"),
    SubjectEntry("device.cast.status.v1", "defined_only", "", "TAC-defined, no subscriber yet"),
]


def get_wired() -> List[SubjectEntry]:
    return [s for s in SUBJECT_REGISTRY if s.status == "wired"]


def get_defined_only() -> List[SubjectEntry]:
    return [s for s in SUBJECT_REGISTRY if s.status == "defined_only"]
