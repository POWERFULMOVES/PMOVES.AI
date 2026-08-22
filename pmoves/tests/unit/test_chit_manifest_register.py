"""Tests for pmoves.tools.chit_manifest_register (additive v2-manifest registrar)."""

from __future__ import annotations

from pathlib import Path

import yaml
import pytest

from pmoves.tools import chit_manifest_register as reg


def write_manifest(path: Path, entries: list) -> None:
    path.write_text(
        yaml.dump(
            {"version": 2, "tier_layout": True, "entries": entries},
            default_flow_style=False,
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def entry_for(label: str, tier: str = "llm") -> dict:
    return reg.build_entry(label, {"tier": tier, "required": False})


def load_entries(path: Path) -> list:
    return yaml.safe_load(path.read_text(encoding="utf-8"))["entries"]


class TestBuildEntry:
    def test_shape_matches_house_schema(self):
        entry = reg.build_entry(
            "HF_TOKEN", {"tier": "llm", "required": False}
        )
        assert entry["id"] == "hf_token"
        assert entry["source"] == {"type": "cgp", "label": "HF_TOKEN"}
        assert {"file": "env.tier-llm", "key": "HF_TOKEN"} in entry["targets"]
        assert {"file": ".env.generated", "key": "HF_TOKEN"} in entry["targets"]
        assert {"github_secret": "HF_TOKEN"} in entry["targets"]
        assert {"docker_secret": "pmoves_hf_token"} in entry["targets"]
        assert entry["required"] is False
        assert entry["tier"] == "llm"

    def test_aliases_carried_into_source(self):
        entry = reg.build_entry(
            "AGENT_ZERO_MCP_TOKEN",
            {"tier": "agent", "required": False, "aliases": ["MCP_SERVER_TOKEN"]},
        )
        assert entry["source"]["aliases"] == ["MCP_SERVER_TOKEN"]


class TestApply:
    def test_adds_missing_registry_labels(self, tmp_path):
        manifest = tmp_path / "m.yaml"
        write_manifest(manifest, [entry_for("Z_AI_API_KEY")])
        assert reg.main(["--manifest", str(manifest)]) == 0
        labels = {e["source"]["label"] for e in load_entries(manifest)}
        assert set(reg.REGISTRY) <= labels

    def test_idempotent_second_run(self, tmp_path):
        manifest = tmp_path / "m.yaml"
        write_manifest(manifest, [])
        assert reg.main(["--manifest", str(manifest)]) == 0
        first = manifest.read_text(encoding="utf-8")
        assert reg.main(["--manifest", str(manifest)]) == 0
        assert manifest.read_text(encoding="utf-8") == first

    def test_existing_entry_never_modified(self, tmp_path):
        manifest = tmp_path / "m.yaml"
        custom = entry_for("HF_TOKEN")
        custom["tier"] = "media"  # deliberately different from REGISTRY
        write_manifest(manifest, [custom])
        assert reg.main(["--manifest", str(manifest)]) == 0
        hf = [e for e in load_entries(manifest) if e["source"]["label"] == "HF_TOKEN"]
        assert len(hf) == 1
        assert hf[0]["tier"] == "media"

    def test_alias_presence_counts_as_existing(self, tmp_path):
        manifest = tmp_path / "m.yaml"
        aliased = entry_for("SOME_CANONICAL", tier="agent")
        aliased["source"]["aliases"] = ["AGENT_ZERO_MCP_TOKEN"]
        write_manifest(manifest, [aliased])
        assert reg.main(["--manifest", str(manifest)]) == 0
        labels = [e["source"]["label"] for e in load_entries(manifest)]
        assert "AGENT_ZERO_MCP_TOKEN" not in labels

    def test_alphabetical_insertion(self, tmp_path):
        manifest = tmp_path / "m.yaml"
        write_manifest(
            manifest, [entry_for("AAA_KEY"), entry_for("ZZZ_KEY")]
        )
        assert reg.main(["--manifest", str(manifest)]) == 0
        ids = [e["id"] for e in load_entries(manifest)]
        assert ids == sorted(ids)


class TestCheck:
    def test_check_reports_without_writing(self, tmp_path):
        manifest = tmp_path / "m.yaml"
        write_manifest(manifest, [])
        before = manifest.read_text(encoding="utf-8")
        assert reg.main(["--manifest", str(manifest), "--check"]) == 1
        assert manifest.read_text(encoding="utf-8") == before

    def test_check_passes_on_complete_manifest(self, tmp_path):
        manifest = tmp_path / "m.yaml"
        write_manifest(manifest, [])
        reg.main(["--manifest", str(manifest)])
        assert reg.main(["--manifest", str(manifest), "--check"]) == 0


class TestErrors:
    def test_missing_file_returns_4(self, tmp_path):
        assert reg.main(["--manifest", str(tmp_path / "nope.yaml")]) == 4

    def test_entries_not_a_list_returns_4(self, tmp_path):
        manifest = tmp_path / "m.yaml"
        manifest.write_text("entries: {}\n", encoding="utf-8")
        assert reg.main(["--manifest", str(manifest)]) == 4


# --- constraint drift on entries that ALREADY exist ---------------------------
#
# The registrar keys pending work on `label not in known`, so a registry entry
# that gains a new CONSTRAINT is invisible to it: the label is already present,
# nothing is pending, and it prints "manifest complete" while the constraint
# never reaches the emitted YAML. That is a gate that cannot reach the file it
# gates. `reconcile_entry` closes it -- narrowly, over RECONCILED_FIELDS only.


def test_reconcile_adds_a_newly_declared_constraint():
    entry = {"id": "skb", "source": {"type": "cgp", "label": "SECRET_KEY_BASE"}}
    changes = reg.reconcile_entry(entry, {"tier": "supabase", "min_length": 64})
    assert entry["min_length"] == 64
    assert changes == ["min_length: (unset) -> 64"]


def test_reconcile_updates_a_changed_constraint():
    entry = {"id": "skb", "min_length": 48, "source": {"type": "cgp", "label": "X"}}
    changes = reg.reconcile_entry(entry, {"tier": "supabase", "min_length": 64})
    assert entry["min_length"] == 64
    assert changes == ["min_length: 48 -> 64"]


def test_reconcile_removes_a_withdrawn_constraint():
    entry = {"id": "skb", "min_length": 64, "source": {"type": "cgp", "label": "X"}}
    changes = reg.reconcile_entry(entry, {"tier": "supabase"})
    assert "min_length" not in entry
    assert changes == ["min_length: 64 -> (removed)"]


def test_reconcile_is_idempotent_and_silent_when_aligned():
    entry = {"id": "skb", "min_length": 64, "source": {"type": "cgp", "label": "X"}}
    assert reg.reconcile_entry(entry, {"tier": "supabase", "min_length": 64}) == []
    assert entry["min_length"] == 64


def test_reconcile_leaves_operator_tuned_fields_alone():
    """`required` and `targets` are deliberately NOT reconciled -- a node may tune
    them, and reverting them to the registry's view would be a new bug."""
    tuned = [{"file": "tier-custom", "key": "SECRET_KEY_BASE"}]
    entry = {
        "id": "skb",
        "required": False,
        "targets": tuned,
        "source": {"type": "cgp", "label": "X"},
    }
    reg.reconcile_entry(entry, {"tier": "supabase", "required": True, "min_length": 64})
    assert entry["required"] is False
    assert entry["targets"] == tuned


def test_entry_label_survives_malformed_entries():
    assert reg.entry_label({"source": {"label": "A"}}) == "A"
    assert reg.entry_label({"source": "not-a-mapping"}) == ""
    assert reg.entry_label("not-a-dict") == ""
    assert reg.entry_label({}) == ""


def test_build_entry_omits_min_length_when_unconstrained():
    """Every other registered secret must emit exactly as before."""
    assert "min_length" not in reg.build_entry("FOO", {"tier": "llm"})
    assert reg.build_entry("BAR", {"tier": "llm", "min_length": 64})["min_length"] == 64


# --- constraints must survive the v1 derivation (review on #2688) ------------
#
# `secrets-funnel-sync` derives the v1 manifest from v2 and hands the DERIVED
# file to secrets_sync.py (codex.mk:114-115). _build_v1_entry copied only
# id/source/targets/required, so a constraint declared in v2 was invisible to
# load_manifest() on the canonical path -- enforced by nothing, while both files
# looked correct.

from pmoves.tools import chit_manifest_sync as sync  # noqa: E402


def _v2(**extra):
    base = {
        "id": "secret_key_base",
        "source": {"type": "cgp", "label": "SECRET_KEY_BASE"},
        "targets": [{"file": "env.tier-supabase", "key": "SECRET_KEY_BASE"}],
        "required": True,
    }
    base.update(extra)
    return base


def test_v1_derivation_carries_min_length():
    assert sync._build_v1_entry(_v2(min_length=64))["min_length"] == 64


def test_v1_derivation_omits_it_when_unconstrained():
    assert "min_length" not in sync._build_v1_entry(_v2())


@pytest.mark.parametrize("bad", [0, -1, True, "64", None, 1.5])
def test_v1_derivation_ignores_non_positive_or_non_int_values(bad):
    """True is an int in Python; a bool constraint is a mistake, not a length."""
    assert "min_length" not in sync._build_v1_entry(_v2(min_length=bad))
