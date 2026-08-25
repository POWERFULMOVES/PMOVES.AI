#!/usr/bin/env python3
"""Model-harness fitting: loading and resolution.

Owns reading the role vocabulary and the `fit` blocks in the model-suit files.
Deliberately does NOT touch routing identity — `kong_route_seeder` reads that from
the top level of each file and must keep working unchanged.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
ROLES_PATH = REPO_ROOT / "pmoves" / "configs" / "model-roles.yaml"
SUITS_DIR = REPO_ROOT / "pmoves" / "configs" / "model-suits"

#: Reserved role key meaning "every role in this harness".
WILDCARD_ROLE = "*"


def load_roles(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """Read the controlled role vocabulary."""
    target = path or ROLES_PATH
    with open(target, encoding="utf-8") as handle:
        doc = yaml.safe_load(handle) or {}
    return doc.get("roles") or {}


def resolve_role(
    name: str, roles: dict[str, dict[str, Any]]
) -> tuple[str | None, str | None]:
    """Resolve a role key to its canonical name.

    Returns ``(canonical, warning)``. A superseded name resolves and warns; an
    unknown name returns ``(None, reason)`` so the caller can fail the gate.
    """
    if name == WILDCARD_ROLE:
        return WILDCARD_ROLE, None
    if name in roles:
        return name, None
    for canonical, body in roles.items():
        if name in (body or {}).get("supersedes", []):
            return canonical, (
                f"role {name!r} is superseded by {canonical!r}; update the fitting"
            )
    return None, f"role {name!r} is not in the vocabulary (pmoves/configs/model-roles.yaml)"


REGISTRY_PATH = REPO_ROOT / "pmoves" / "config" / "agent_registry.yaml"


def load_harnesses(registry_path: Path | None = None) -> set[str]:
    """Registry keys whose entry declares ``kind: harness``.

    A fitting may only name one of these. `cross_agent` deliberately names a wider
    set (agents, a UI, a launcher) because it answers a different question —
    component compatibility, not what a harness costs a model.
    """
    target = registry_path or REGISTRY_PATH
    with open(target, encoding="utf-8") as handle:
        doc = yaml.safe_load(handle) or {}
    return {
        key
        for key, entry in (doc.get("agents") or {}).items()
        if (entry or {}).get("kind") == "harness"
    }


#: Fit verdicts, least to most permissive. Order IS the conservatism ranking.
#: There is deliberately no "untested": an unmeasured pairing has no observation.
FIT_ORDER: tuple[str, ...] = ("none", "delegate", "limited", "full")


def effective_fit(observations: list[dict[str, Any]]) -> str | None:
    """The verdict a router should act on.

    Returns the MOST CONSERVATIVE verdict among observations, so a single credible
    "this is worse than it looks" is never averaged away by a benchmark that did not
    exercise the failing path. Returns ``None`` when nothing has been observed —
    absence is honestly unknown, and is not the same as a recorded null result.
    """
    if not observations:
        return None
    ranks = []
    for obs in observations:
        verdict = (obs or {}).get("verdict")
        if verdict not in FIT_ORDER:
            raise ValueError(
                f"unknown fit verdict {verdict!r}; permitted: {', '.join(FIT_ORDER)}. "
                "An unmeasured pairing must have NO observation rather than a null one."
            )
        ranks.append(FIT_ORDER.index(verdict))
    return FIT_ORDER[min(ranks)]
