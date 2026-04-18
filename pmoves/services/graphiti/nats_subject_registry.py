"""GRAPHITI NATS Subject Registry.

Tracks all GRAPHITI-related NATS subjects defined in TAC trees.
Each subject has a status: 'wired' (has subscriber code), 'stub' (has stub subscriber), 'defined_only' (TAC tree only).

Generated: 2026-04-17
Source: pmoves/configs/tac_trees/ (7 files with GRAPHITI references)
See: research/part1_tac_trees_analysis.md for full 97-subject analysis

Subject count: 97 unique subjects across 17 teams.
Wired: 1 | Stub: 3 | Defined only: 93
"""

import sys
from pathlib import Path
from typing import List

_SERVICES_DIR = Path(__file__).resolve().parent.parent
if str(_SERVICES_DIR.parent) not in sys.path:
    sys.path.insert(0, str(_SERVICES_DIR.parent))

from services.common.nats_types import SubjectEntry  # noqa: E402


SUBJECT_REGISTRY: List[SubjectEntry] = [
    # ── Pipeline stages (4 subjects) ──
    SubjectEntry(
        subject="ops.pr.monitor.completed.v1",
        status="stub",
        subscriber_file="pmoves/services/graphiti/stage1_pr_monitor.py",
        notes="Stage 1 output — raises NotImplementedError",
        stage="pr-monitor",
        publisher="",
    ),
    SubjectEntry(
        subject="ops.pr.trim.completed.v1",
        status="stub",
        subscriber_file="pmoves/services/graphiti/stage2_pr_trim.py",
        notes="Stage 2 output — raises NotImplementedError",
        stage="pr-trim",
        publisher="",
    ),
    SubjectEntry(
        subject="ops.pr.learnings.encoded.v1",
        status="stub",
        subscriber_file="pmoves/services/graphiti/stage3_chit_encode.py",
        notes="Stage 3 output — raises NotImplementedError",
        stage="chit-encode",
        publisher="",
    ),
    SubjectEntry(
        subject="agent.graphiti.signed.v1",
        status="wired",
        subscriber_file="pmoves/tools/sign_trail.py",
        notes="Stage 4 — implemented, delegates to chit_security.sign_cgp",
        stage="sign-trail",
        publisher="sign-trail",
    ),
    # ── Remaining 93 subjects are defined_only ──
    # Full list with team assignments in research/part1_tac_trees_analysis.md
    # Teams: geometry, evolution, training, skills, orchestration, research,
    #        media, infra, ui, automation, discord, agentgym, vpn, external, life
]

# Updated 2026-04-17: Research doc inconsistencies resolved —
# table said 78, spec said 88, full unique count = 97.
# This registry contains the 4 pipeline subjects; the remaining 93
# defined_only subjects are catalogued in the research report.
# To generate the full registry, parse part1_tac_trees_analysis.md
# and create SubjectEntry instances with status="defined_only".


def get_subjects_by_status(status: str) -> List[SubjectEntry]:
    """Filter subjects by status: 'wired', 'stub', or 'defined_only'."""
    return [s for s in SUBJECT_REGISTRY if s.status == status]


def get_subjects_by_stage(stage: str) -> List[SubjectEntry]:
    """Filter subjects by pipeline stage."""
    return [s for s in SUBJECT_REGISTRY if s.stage == stage]


def get_wired_count() -> int:
    return len(get_subjects_by_status("wired"))


def get_stub_count() -> int:
    return len(get_subjects_by_status("stub"))


def get_defined_only_count() -> int:
    return 93  # From research/part1_tac_trees_analysis.md


def get_total_count() -> int:
    return len(SUBJECT_REGISTRY) + get_defined_only_count()
