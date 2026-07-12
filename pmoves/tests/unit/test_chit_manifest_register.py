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
