"""Tests for consciousness demo module functions.

These tests validate the internal functions of the consciousness demo module
without requiring the full FastAPI app to be running (avoiding import issues
with nested dependencies like neo4j, nats, etc.).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

# Stub heavy dependencies that chit.py might import
if "neo4j" not in sys.modules:
    neo4j_stub = ModuleType("neo4j")
    neo4j_stub.GraphDatabase = MagicMock()
    sys.modules["neo4j"] = neo4j_stub

# Mock the chit module's ingest_cgp function
_mock_chit = ModuleType("services.gateway.gateway.api.chit")
_mock_chit.ingest_cgp = MagicMock(return_value="mock_shape_id")
sys.modules["services.gateway.gateway.api.chit"] = _mock_chit

# Now import our module functions
from services.gateway.gateway.api.consciousness import (
    _load_taxonomy,
    _extract_theories,
    _theory_to_cgp,
    _spectrum_for_category,
    TheoryInfo,
)


class TestLoadTaxonomy:
    """Tests for _load_taxonomy function."""

    def test_load_taxonomy_returns_dict(self):
        """Test that taxonomy loads and returns a dictionary."""
        taxonomy = _load_taxonomy()
        assert isinstance(taxonomy, dict)
        assert "categories" in taxonomy

    def test_taxonomy_has_source_info(self):
        """Test taxonomy includes source metadata."""
        taxonomy = _load_taxonomy()
        assert "source" in taxonomy
        source = taxonomy["source"]
        assert "author" in source
        assert "Kuhn" in source["author"]


class TestExtractTheories:
    """Tests for _extract_theories function."""

    def test_extract_theories_returns_list(self):
        """Test extracting theories returns a list."""
        taxonomy = _load_taxonomy()
        theories, categories = _extract_theories(taxonomy)
        assert isinstance(theories, list)
        assert isinstance(categories, list)
        assert len(theories) > 0

    def test_extract_theories_respects_max(self):
        """Test max_theories limit is respected."""
        taxonomy = _load_taxonomy()
        theories, _ = _extract_theories(taxonomy, max_theories=5)
        assert len(theories) <= 5

    def test_extract_theories_filters_by_category(self):
        """Test category filtering works."""
        taxonomy = _load_taxonomy()
        theories, _ = _extract_theories(taxonomy, category_filter="materialism", max_theories=20)
        for theory in theories:
            assert theory.category == "materialism"

    def test_theory_info_has_required_fields(self):
        """Test TheoryInfo objects have all required fields."""
        taxonomy = _load_taxonomy()
        theories, _ = _extract_theories(taxonomy, max_theories=1)
        theory = theories[0]
        assert isinstance(theory, TheoryInfo)
        assert theory.name
        assert theory.category
        assert isinstance(theory.proponents, list)


class TestTheoryToCgp:
    """Tests for _theory_to_cgp function."""

    def test_cgp_has_correct_spec(self):
        """Test CGP packet has correct specification."""
        theory = TheoryInfo(
            name="Test Theory",
            description="A test theory about consciousness",
            proponents=["Alice", "Bob"],
            category="materialism",
            subcategory="1.1_Test"
        )
        cgp = _theory_to_cgp(theory, idx=0)
        assert cgp["spec"] == "chit.cgp.v0.1"

    def test_cgp_has_super_nodes(self):
        """Test CGP packet contains super_nodes."""
        theory = TheoryInfo(
            name="Test Theory",
            description="A test theory",
            proponents=["Alice"],
            category="materialism",
            subcategory="1.1_Test"
        )
        cgp = _theory_to_cgp(theory, idx=0)
        assert "super_nodes" in cgp
        assert len(cgp["super_nodes"]) > 0

    def test_cgp_constellation_has_points(self):
        """Test constellation contains points from proponents."""
        theory = TheoryInfo(
            name="Test Theory",
            description="A test theory",
            proponents=["Alice", "Bob", "Charlie"],
            category="materialism",
            subcategory="1.1_Test"
        )
        cgp = _theory_to_cgp(theory, idx=0)
        constellation = cgp["super_nodes"][0]["constellations"][0]
        assert "points" in constellation
        assert len(constellation["points"]) == 3  # One per proponent


class TestSpectrumForCategory:
    """Tests for _spectrum_for_category function."""

    def test_known_category_returns_specific_spectrum(self):
        """Test known categories return their specific spectrum."""
        spectrum = _spectrum_for_category("materialism")
        assert spectrum[0] == 0.8  # Materialism has high red channel

    def test_unknown_category_returns_default(self):
        """Test unknown categories return default uniform spectrum."""
        spectrum = _spectrum_for_category("unknown_category")
        assert spectrum == [0.125] * 8

    def test_spectrum_has_eight_bins(self):
        """Test all spectrums have 8 bins."""
        for category in ["materialism", "dualism", "panpsychism", "unknown"]:
            spectrum = _spectrum_for_category(category)
            assert len(spectrum) == 8
