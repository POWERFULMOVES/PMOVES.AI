"""Dependabot Ollama lane (#3380): Ollama bumps never auto-merge, and the gate fails closed.

The auto-merge step's `if:` is evaluated here with a small translator for the
subset of GitHub expression syntax it uses (==, !=, &&, ||, !, contains), so the
test checks behaviour, not spelling.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

REPO = Path(__file__).resolve().parents[2]
WORKFLOW = REPO / ".github" / "workflows" / "dependabot-auto-merge.yml"
DEPENDABOT = REPO / ".github" / "dependabot.yml"


def _auto_merge_condition() -> str:
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    for step in doc["jobs"]["dependabot-auto-merge"]["steps"]:
        if "gh pr merge --auto" in str(step.get("run", "")):
            return step["if"]
    raise AssertionError("auto-merge step not found")


def _evaluate(expr: str, outputs: dict[str, str]) -> bool:
    py = re.sub(r"steps\.meta\.outputs\.([\w-]+)", lambda m: repr(outputs.get(m.group(1), "")), expr)
    py = py.replace("!=", " <NE> ").replace("!", " not ").replace(" <NE> ", " != ")
    py = py.replace("&&", " and ").replace("||", " or ")

    def contains(haystack: str, needle: str) -> bool:  # GitHub's contains() is case-insensitive
        return needle.lower() in haystack.lower()

    return bool(eval(py, {"__builtins__": {}}, {"contains": contains}))  # noqa: S307 - test-local, repo text


@pytest.mark.parametrize("names,update_type,merges", [
    ("requests", "version-update:semver-minor", True),
    ("requests", "version-update:semver-patch", True),
    ("requests", "version-update:semver-major", False),
    ("ollama/ollama", "version-update:semver-minor", False),
    ("ollama/ollama", "version-update:semver-patch", False),
    ("", "version-update:semver-minor", False),  # metadata missing: fail closed
    ("", "version-update:semver-patch", False),
])
def test_auto_merge_gate(names, update_type, merges):
    outputs = {"dependency-names": names, "update-type": update_type}
    assert _evaluate(_auto_merge_condition(), outputs) is merges


def test_ollama_entry_is_scoped_to_ollama_and_labelled():
    doc = yaml.safe_load(DEPENDABOT.read_text(encoding="utf-8"))
    entries = [u for u in doc["updates"] if u["package-ecosystem"] == "docker-compose"]
    assert len(entries) == 1
    entry = entries[0]
    assert entry["allow"] == [{"dependency-name": "ollama/ollama"}]
    assert "ollama" in entry["labels"]
