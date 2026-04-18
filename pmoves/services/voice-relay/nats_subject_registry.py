"""Voice NATS Subject Registry.

Tracks voice-related NATS subjects from TAC trees.
Generated: 2026-04-17
Source: pmoves/configs/tac_trees/
"""

from typing import List

# Import shared SubjectEntry from common types
import sys
from pathlib import Path
_SERVICES_DIR = Path(__file__).resolve().parent.parent
_COMMON_DIR = _SERVICES_DIR / "common"
if str(_SERVICES_DIR.parent) not in sys.path:
    sys.path.insert(0, str(_SERVICES_DIR.parent))
from services.common.nats_types import SubjectEntry  # noqa: E402


SUBJECT_REGISTRY: List[SubjectEntry] = [
    SubjectEntry(
        subject="voice.agent.response.v1",
        status="wired",
        subscriber_file="pmoves/services/voice-relay/main.py",
        notes="JetStream publish with ack — P1-3 wiring applied",
        stage="voice-relay",
        publisher="voice-relay",
    ),
    SubjectEntry(
        subject="voice.cast.request.v1",
        status="defined_only",
        subscriber_file="",
        notes="TAC-defined, no subscriber yet",
        stage="voice-cast",
        publisher="",
    ),
    SubjectEntry(
        subject="voice.cast.completed.v1",
        status="defined_only",
        subscriber_file="",
        notes="TAC-defined, no subscriber yet",
        stage="voice-cast",
        publisher="",
    ),
    SubjectEntry(
        subject="voice.cast.failed.v1",
        status="defined_only",
        subscriber_file="",
        notes="TAC-defined, no subscriber yet",
        stage="voice-cast",
        publisher="",
    ),
    SubjectEntry(
        subject="voice.training.request.v1",
        status="defined_only",
        subscriber_file="",
        notes="TAC-defined, no subscriber yet",
        stage="voice-training",
        publisher="",
    ),
    SubjectEntry(
        subject="tokenism.prosodic.bpm.v1",
        status="defined_only",
        subscriber_file="",
        notes="Flute gateway, TAC-defined",
        stage="flute-gateway",
        publisher="",
    ),
    SubjectEntry(
        subject="device.cast.discovered.v1",
        status="defined_only",
        subscriber_file="",
        notes="TAC-defined, no subscriber yet",
        stage="device-cast",
        publisher="",
    ),
    SubjectEntry(
        subject="device.cast.status.v1",
        status="defined_only",
        subscriber_file="",
        notes="TAC-defined, no subscriber yet",
        stage="device-cast",
        publisher="",
    ),
]


def get_wired() -> List[SubjectEntry]:
    return [s for s in SUBJECT_REGISTRY if s.status == "wired"]


def get_defined_only() -> List[SubjectEntry]:
    return [s for s in SUBJECT_REGISTRY if s.status == "defined_only"]
