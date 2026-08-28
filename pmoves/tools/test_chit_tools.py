"""Tests for CHIT tools — compute_mhep, kl_divergence_spectrum, CGP integration.

Run from repo root:
    pytest pmoves/tools/test_chit_tools.py -v

Requires: numpy (always), sentence-transformers + scikit-learn + jsonschema (for integration).
"""

import math
import sys
from pathlib import Path

import numpy as np
import pytest

# Ensure sibling modules are importable regardless of cwd
_TOOLS_DIR = str(Path(__file__).resolve().parent)
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

# chit_verify only needs numpy — safe to import unconditionally
import chit_verify  # noqa: E402

# chit_backend pulls heavy deps; gate behind importorskip
chit_backend = pytest.importorskip("chit_backend")  # noqa: E402


# =============================================================================
# Unit: compute_mhep
# =============================================================================


class TestComputeMhep:
    """Mean Harmonic Embedding Perplexity tests."""

    def test_empty_projections(self):
        """No projections → 0.0."""
        assert chit_backend.compute_mhep([]) == 0.0

    def test_single_projection(self):
        """Single proj: softmax([0]) = [1], MHEP = 1/1 = 1.0."""
        assert abs(chit_backend.compute_mhep([0.0]) - 1.0) < 1e-6

    def test_identical_projections(self):
        """[1, 1]: shifted=[0,0], softmax sum=2, MHEP = 1/2 = 0.5."""
        assert abs(chit_backend.compute_mhep([1.0, 1.0]) - 0.5) < 1e-6

    def test_known_three_values(self):
        """[2, 1, 0]: shifted=[0,-1,-2], sum=1+e^-1+e^-2≈1.5032, MHEP≈0.6652."""
        expected = 1.0 / (1.0 + math.exp(-1) + math.exp(-2))
        result = chit_backend.compute_mhep([2.0, 1.0, 0.0])
        assert abs(result - expected) < 1e-6

    def test_peaked_distribution_high_perplexity(self):
        """One dominant projection → softmax_sum≈1, MHEP≈1.0."""
        result = chit_backend.compute_mhep([10.0, 0.0, 0.0])
        assert result > 0.99


# =============================================================================
# Unit: kl_divergence_spectrum
# =============================================================================


class TestKlDivergenceSpectrum:
    """KL(p || uniform) spectrum tests."""

    def test_uniform_distribution_near_zero(self):
        """Uniform spectrum → KL ≈ 0."""
        result = chit_verify.kl_divergence_spectrum([1.0, 1.0, 1.0, 1.0], bins=4)
        assert result < 1e-4

    def test_peaked_distribution_positive(self):
        """Peaked [100,1,1,1] → KL > 0."""
        result = chit_verify.kl_divergence_spectrum([100.0, 1.0, 1.0, 1.0], bins=4)
        assert result > 0.5

    def test_single_bin_zero(self):
        """Single bin: p=u=1, log(1)=0."""
        result = chit_verify.kl_divergence_spectrum([1.0], bins=1)
        assert result < 1e-4

    def test_known_two_bin_value(self):
        """[3,1] bins=2: p≈[0.75,0.25], u=[0.5,0.5].
        KL = 0.75*ln(1.5) + 0.25*ln(0.5) ≈ 0.1308."""
        result = chit_verify.kl_divergence_spectrum([3.0, 1.0], bins=2)
        assert abs(result - 0.1308) < 0.01


# =============================================================================
# Integration: CGP output structure
# =============================================================================


@pytest.fixture
def fixture_chunks():
    """3-line JSONL-style data: 2 in 'awareness', 1 in 'practice'."""
    return [
        {"id": "chunk-1", "content": "Consciousness is the state of being aware.", "category": "awareness"},
        {"id": "chunk-2", "content": "Awareness expands through meditation practice.", "category": "awareness"},
        {"id": "chunk-3", "content": "Meditation deepens the connection to inner self.", "category": "practice"},
    ]


@pytest.fixture
def fake_embeddings():
    """Pre-computed 4-dim fake embeddings matching fixture_chunks."""
    return {
        "awareness": np.array([
            [0.1, 0.2, 0.3, 0.4],
            [0.15, 0.25, 0.35, 0.45],
        ], dtype=np.float64),
        "practice": np.array([
            [0.8, 0.7, 0.6, 0.5],
        ], dtype=np.float64),
    }


class TestCgpIntegration:
    """Integration: build_cgp from fixture → verify CGP structure."""

    def test_required_top_level_keys(self, fixture_chunks, fake_embeddings):
        groups = chit_backend.group_by_category(fixture_chunks)
        cgp = chit_backend.build_cgp(groups, fake_embeddings, k=2, bins=8)
        for key in ("spec", "created_at", "updated_at", "summary", "meta",
                    "super_nodes", "constellations", "points"):
            assert key in cgp, f"Missing top-level key: {key}"

    def test_meta_categories_and_counts(self, fixture_chunks, fake_embeddings):
        groups = chit_backend.group_by_category(fixture_chunks)
        cgp = chit_backend.build_cgp(groups, fake_embeddings, k=2, bins=8)
        meta = cgp["meta"]
        assert set(meta["categories"]) == {"awareness", "practice"}
        assert meta["total_chunks"] == 3
        assert "mhep" in meta
        assert meta["K"] == 2
        assert meta["bins"] == 8

    def test_super_nodes_match_categories(self, fixture_chunks, fake_embeddings):
        groups = chit_backend.group_by_category(fixture_chunks)
        cgp = chit_backend.build_cgp(groups, fake_embeddings, k=2, bins=8)
        assert len(cgp["super_nodes"]) == 2
        labels = {sn["label"] for sn in cgp["super_nodes"]}
        assert labels == {"awareness", "practice"}
        for sn in cgp["super_nodes"]:
            assert "id" in sn
            assert isinstance(sn["constellations"], list)

    def test_constellations_have_required_fields(self, fixture_chunks, fake_embeddings):
        groups = chit_backend.group_by_category(fixture_chunks)
        cgp = chit_backend.build_cgp(groups, fake_embeddings, k=2, bins=8)
        total_points = 0
        for con in cgp["constellations"]:
            for field in ("id", "points", "spectrum", "anchor", "radial_minmax"):
                assert field in con, f"Constellation missing field: {field}"
            assert isinstance(con["spectrum"], list)
            total_points += len(con["points"])
        assert total_points == 3

    def test_points_text_truncated_to_512(self, fixture_chunks, fake_embeddings):
        """Every point's text field must be ≤ 512 chars (backend truncation invariant)."""
        groups = chit_backend.group_by_category(fixture_chunks)
        cgp = chit_backend.build_cgp(groups, fake_embeddings, k=2, bins=8)
        for pt in cgp["points"]:
            assert "text" in pt
            assert "proj" in pt
            assert "id" in pt
            assert "ref_id" in pt
            assert len(pt["text"]) <= 512, (
                f"Point {pt['id']} text length {len(pt['text'])} exceeds 512"
            )
