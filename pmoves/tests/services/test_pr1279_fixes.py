"""Tests for PR #1279 review fixes.

Covers: C1 (max_bytes int), C2 (TAC subject coverage),
I1 (sign_trail path), I2 (cataclysm schema), I3 (media imports), I4 (shared SubjectEntry).
"""

import importlib.util
import yaml
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]  # pmoves/


class TestMeshGpuStreamsYaml:
    """C1 + C2: JetStream stream config validity."""

    def _load(self):
        p = BASE / "nats" / "mesh_gpu_streams.yaml"
        with open(p) as f:
            return yaml.safe_load(f)

    def test_parses_as_valid_yaml(self):
        data = self._load()
        assert "streams" in data

    def test_max_bytes_is_integer(self):
        """C1: max_bytes must be integer bytes, not string like '256MB'."""
        data = self._load()
        for stream in data["streams"]:
            if "max_bytes" in stream:
                assert isinstance(stream["max_bytes"], int), (
                    f"Stream {stream['name']} max_bytes is {type(stream['max_bytes']).__name__}, expected int"
                )

    def test_tac_subjects_covered_by_stream_wildcards(self):
        """C2: All DGX Spark TAC mesh.gpu.* subjects must match a stream wildcard."""
        tac_subjects = [
            "mesh.gpu.command.v1",
            "mesh.gpu.status.v1",
            "mesh.gpu.model.loaded.v1",
            "mesh.gpu.model.unloaded.v1",
            "mesh.gpu.command.result.v1",
        ]
        data = self._load()
        wildcards = []
        for stream in data["streams"]:
            for subj in stream.get("subjects", []):
                wildcards.append(subj)

        def matches(subject, wildcard):
            if wildcard.endswith(">"):
                prefix = wildcard[:-1]  # e.g. "mesh.gpu.command."
                return subject.startswith(prefix)
            return subject == wildcard

        for tac_subj in tac_subjects:
            assert any(matches(tac_subj, w) for w in wildcards), (
                f"TAC subject '{tac_subj}' not covered by any stream wildcard: {wildcards}"
            )


class TestCataclysmTacTreeSchema:
    """I2: Cataclysm TAC tree uses canonical schema."""

    def _load(self):
        p = BASE / "configs" / "tac_trees" / "cataclysm-studios.tac.yaml"
        with open(p) as f:
            return yaml.safe_load(f)

    def test_has_root_key(self):
        data = self._load()
        assert "root" in data, "Top-level 'root' key missing"

    def test_no_tac_tree_key(self):
        data = self._load()
        assert "tac_tree" not in data, "Legacy 'tac_tree' key still present"

    def test_no_phases_key(self):
        data = self._load()
        assert "phases" not in data, "Legacy 'phases' key still present"

    def test_root_has_children(self):
        data = self._load()
        assert "children" in data["root"], "root must have 'children'"


class TestMediaStubImports:
    """I3: Media stubs load without raising NotImplementedError."""

    def _load_module(self, pkg_dir_name):
        p = BASE / "services" / pkg_dir_name / "__init__.py"
        spec = importlib.util.spec_from_file_location("_test_mod", p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_media_audio_imports(self):
        self._load_module("media-audio")

    def test_media_video_imports(self):
        self._load_module("media-video")


class TestNatsRegistryImports:
    """I4: Both registries import shared SubjectEntry without error."""

    def test_graphiti_registry_imports(self):
        from pmoves.services.graphiti.nats_subject_registry import SubjectEntry, SUBJECT_REGISTRY
        assert len(SUBJECT_REGISTRY) > 0
        assert "stage" in SubjectEntry.__dataclass_fields__
        assert "publisher" in SubjectEntry.__dataclass_fields__

    def test_voice_relay_registry_imports(self):
        p = BASE / "services" / "voice-relay" / "nats_subject_registry.py"
        spec = importlib.util.spec_from_file_location("_test_voice_relay", p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert len(mod.SUBJECT_REGISTRY) > 0
        for entry in mod.SUBJECT_REGISTRY:
            assert "stage" in type(entry).__dataclass_fields__
            assert "publisher" in type(entry).__dataclass_fields__

    def test_shared_subject_entry_is_same_class(self):
        from pmoves.services.graphiti.nats_subject_registry import SubjectEntry as GraphitiEntry
        # voice-relay uses hyphenated dir — load via importlib
        p = BASE / "services" / "voice-relay" / "nats_subject_registry.py"
        spec = importlib.util.spec_from_file_location("_test_vr_cls", p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert GraphitiEntry is mod.SubjectEntry

    def test_sign_trail_path_is_correct(self):
        """I1: sign_trail.py path points to pmoves/tools/sign_trail.py."""
        from pmoves.services.graphiti.nats_subject_registry import SUBJECT_REGISTRY
        sign_entry = [e for e in SUBJECT_REGISTRY if "sign_trail" in e.subscriber_file][0]
        assert sign_entry.subscriber_file == "pmoves/tools/sign_trail.py", (
            f"Wrong path: {sign_entry.subscriber_file}"
        )
