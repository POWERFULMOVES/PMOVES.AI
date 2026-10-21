"""Pipeline-bypass hook messages name the single-service road, with its potholes,
identically in the .claude/ and .kilo/ damage-control patterns.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
FILES = [REPO_ROOT / ".claude" / "hooks" / "damage-control" / "patterns.yaml",
         REPO_ROOT / ".kilo" / "hooks" / "damage-control" / "patterns.yaml"]
BYPASS_HEADS = ("PIPELINE BYPASS: 'docker compose up -d'", "PIPELINE BYPASS: 'docker compose -d up'",
                "PIPELINE BYPASS: 'docker compose restart'")


def _bypass_reasons(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    found = {}

    def walk(node):
        if isinstance(node, dict):
            reason = node.get("reason")
            if isinstance(reason, str):
                for head in BYPASS_HEADS:
                    if reason.startswith(head):
                        found[head] = reason
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(data)
    return found


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.parts[-4])
def test_every_bypass_message_names_the_road_and_its_potholes(path):
    reasons = _bypass_reasons(path)
    assert set(reasons) == set(BYPASS_HEADS)
    for head, reason in reasons.items():
        assert "recreate-svc SVC=<name>" in reason and "rebuild-svc SVC=<name>" in reason, head
        assert "INCLUDE_ENV_LOCAL_IN_COMPOSE=1" in reason, head
        assert "bounce kong" in reason, head


def _road(reason: str) -> str:
    """The single-service paragraph: from 'ONE service only' to the next '---'."""
    return reason[reason.index("ONE service only"):].split("---", 1)[0].strip()


def test_claude_and_kilo_road_text_is_identical():
    # The rest of each message differs between harnesses on purpose; the road must not.
    claude, kilo = (_bypass_reasons(p) for p in FILES)
    assert {h: _road(r) for h, r in claude.items()} == {h: _road(r) for h, r in kilo.items()}
