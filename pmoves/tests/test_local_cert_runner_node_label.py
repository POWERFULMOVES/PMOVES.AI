"""Node sub-labels must make a lane runner addressable by the workflows that target it.

The assertions here read the REQUIREMENT out of .github/workflows/sync-secrets-local.yml
rather than restating it. A test that hardcoded ``["self-hosted", "ai-lab", "4090"]``
would still pass if someone renamed the lane in the workflow, which is precisely the
drift worth catching: the runner would register fine and simply never be selected.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "sync-secrets-local.yml"


def _load_module():
    path = _REPO_ROOT / "pmoves" / "tools" / "local_cert_runners.py"
    spec = importlib.util.spec_from_file_location("local_cert_runners", path)
    module = importlib.util.module_from_spec(spec)
    # dataclass() resolves annotations through sys.modules; without this the
    # frozen RunnerLane definition raises on import.
    sys.modules["local_cert_runners"] = module
    spec.loader.exec_module(module)
    return module


lcr = _load_module()


def _workflow_runs_on() -> list[str]:
    """Extract the self-hosted `runs-on` list the sync job actually declares."""
    text = _WORKFLOW.read_text(encoding="utf-8")
    match = re.search(r"^\s*runs-on:\s*\[self-hosted,\s*(.+?)\]\s*$", text, re.M)
    assert match, "sync-secrets-local.yml no longer declares a self-hosted runs-on list"
    parts = ["self-hosted"] + [p.strip().strip('"\'') for p in match.group(1).split(",")]
    # The last element is the matrix expression standing in for the node label.
    assert "${{ matrix.target }}" in parts[-1], (
        f"expected the final runs-on entry to be the per-node matrix target, got {parts[-1]!r}"
    )
    return parts


def test_node_label_satisfies_the_workflow_runs_on():
    """A node-labelled ai-lab runner carries every label the sync job selects on."""
    parts = _workflow_runs_on()
    lane_labels = parts[1:-1]  # between 'self-hosted' and the matrix target
    node = "4090"

    lanes = lcr._apply_node_label(lcr._selected_lanes(["ai-lab"]), node)
    have = set(lanes[0].labels.split(","))

    required = {"self-hosted", *lane_labels, node}
    missing = required - have
    assert not missing, (
        f"runner labels {sorted(have)} cannot satisfy runs-on {required}; missing {sorted(missing)}"
    )


def test_node_label_is_additive_not_replacing():
    """Adding a node label must not stop the runner matching the bare lane."""
    base = lcr._selected_lanes(["ai-lab"])[0]
    tagged = lcr._apply_node_label((base,), "4090")[0]
    assert set(base.labels.split(",")) < set(tagged.labels.split(","))


def test_runner_name_is_suffixed_so_two_nodes_do_not_collide():
    """GitHub requires unique runner names; this tool sets RUNNER_ALLOW_RUNNER_REUSE,
    so a collision silently REPLACES the other node rather than erroring."""
    lane = lcr._selected_lanes(["ai-lab"])
    a = lcr._apply_node_label(lane, "4090")[0].runner_name
    b = lcr._apply_node_label(lane, "b850")[0].runner_name
    assert a != b, "two nodes on the same lane would register the same runner name"


@pytest.mark.parametrize("bad", ["-4090", "AI-Lab", "", "a,b", "4090 --privileged"])
def test_invalid_node_labels_are_rejected(bad):
    """The label reaches a docker `-e LABELS` value and a GitHub runner name;
    it is validated to the same shape the workflow input validates."""
    with pytest.raises(ValueError):
        lcr._apply_node_label(lcr._selected_lanes(["ai-lab"]), bad)
