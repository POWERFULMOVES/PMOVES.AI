"""
Unit tests for CGP Auto-Mapper.

Tests the Constellation Geometry Protocol mapper including:
- Theory-to-constellation transformation
- Spherical-to-Cartesian coordinate conversion
- Metric calculations
- Constellation anchoring
"""

import math
import pytest
from unittest import mock

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from cgp_mapper import CGPMapper


class TestCGPMapper:
    """Tests for CGPMapper class."""

    @pytest.fixture
    def mapper(self):
        """Create CGPMapper instance for testing."""
        return CGPMapper()

    def test_mapper_initialization(self, mapper):
        """Mapper initializes with HTTP client."""
        assert mapper.client is not None

    def test_theory_to_constellation_basic(self, mapper):
        """Generate CGP packet from theory."""
        theory = {
            "name": "Integrated Information Theory",
            "category": "computational",
            "subcategory": "iit",
            "description": "Consciousness is integrated information measured by phi.",
            "proponents": ["Giulio Tononi", "Christof Koch"]
        }

        packet = mapper.theory_to_constellation(theory)

        # Check packet structure
        assert packet["version"] == "cgp.v1"
        assert "timestamp" in packet
        assert "theory" in packet
        assert "geometry" in packet
        assert "metadata" in packet

        # Check theory info
        assert packet["theory"]["name"] == "Integrated Information Theory"
        assert packet["theory"]["category"] == "computational"

        # Check geometry coordinates
        coords = packet["geometry"]["coordinates"]
        assert "cartesian" in coords
        assert "spherical" in coords
        assert all(k in coords["cartesian"] for k in ["x", "y", "z"])
        assert all(k in coords["spherical"] for k in ["radius", "phi", "theta"])

        # Check dimensions
        dims = packet["geometry"]["dimensions"]
        assert 0 <= dims["empirical_support"] <= 1
        assert 0 <= dims["philosophical_coherence"] <= 1
        assert 0 <= dims["integration_potential"] <= 1

    def test_theory_to_constellation_minimal(self, mapper):
        """Generate CGP packet with minimal theory data."""
        theory = {
            "name": "Unknown Theory",
            "category": "unknown"
        }

        packet = mapper.theory_to_constellation(theory)

        assert packet["theory"]["name"] == "Unknown Theory"
        assert packet["geometry"] is not None

    def test_theory_id_generation(self, mapper):
        """Theory ID is formatted correctly."""
        theory = {
            "name": "Global Workspace Theory",
            "category": "computational"
        }

        packet = mapper.theory_to_constellation(theory)

        assert packet["theory"]["id"] == "computational:global_workspace_theory"

    def test_coordinate_conversion(self, mapper):
        """Spherical to Cartesian conversion is correct."""
        # Test with known values
        theory = {
            "name": "Test Theory",
            "category": "test",
            "description": "A theory with predictable metrics.",
            "proponents": []
        }

        packet = mapper.theory_to_constellation(theory)

        coords = packet["geometry"]["coordinates"]
        r = coords["spherical"]["radius"]
        phi = coords["spherical"]["phi"]
        theta = coords["spherical"]["theta"]

        # Verify Cartesian coordinates match spherical
        expected_x = r * math.sin(theta) * math.cos(phi)
        expected_y = r * math.sin(theta) * math.sin(phi)
        expected_z = r * math.cos(theta)

        assert abs(coords["cartesian"]["x"] - round(expected_x, 4)) < 0.0001
        assert abs(coords["cartesian"]["y"] - round(expected_y, 4)) < 0.0001
        assert abs(coords["cartesian"]["z"] - round(expected_z, 4)) < 0.0001


class TestEmpiricalSupportCalculation:
    """Tests for empirical support metric calculation."""

    @pytest.fixture
    def mapper(self):
        return CGPMapper()

    def test_base_score(self, mapper):
        """Base score is 0.5."""
        score = mapper._calculate_empirical_support("Theory", [], "")
        assert score >= 0.5

    def test_proponents_increase_score(self, mapper):
        """More proponents increases score."""
        score_none = mapper._calculate_empirical_support("Theory", [], "Desc")
        score_some = mapper._calculate_empirical_support("Theory", ["A", "B", "C"], "Desc")

        assert score_some > score_none

    def test_keywords_increase_score(self, mapper):
        """Empirical keywords increase score."""
        score_plain = mapper._calculate_empirical_support("Theory", [], "Plain description")
        score_empirical = mapper._calculate_empirical_support(
            "Theory", [],
            "Experimental evidence from neural data and brain measurement"
        )

        assert score_empirical > score_plain

    def test_score_capped_at_one(self, mapper):
        """Score never exceeds 1.0."""
        score = mapper._calculate_empirical_support(
            "Theory",
            ["A", "B", "C", "D", "E", "F", "G", "H"],
            "Experimental evidence with neural brain measurement data observation empirical neuroscience"
        )

        assert score <= 1.0


class TestPhilosophicalCoherenceCalculation:
    """Tests for philosophical coherence metric calculation."""

    @pytest.fixture
    def mapper(self):
        return CGPMapper()

    def test_base_score(self, mapper):
        """Base score is 0.5."""
        score = mapper._calculate_philosophical_coherence("Short", "cat")
        assert score >= 0.5

    def test_longer_description_increases_score(self, mapper):
        """Longer descriptions increase score."""
        short_desc = "Brief."
        long_desc = "A " * 100  # 200 chars

        score_short = mapper._calculate_philosophical_coherence(short_desc, "cat")
        score_long = mapper._calculate_philosophical_coherence(long_desc, "cat")

        assert score_long > score_short

    def test_rigor_keywords_increase_score(self, mapper):
        """Philosophical rigor keywords increase score."""
        score_plain = mapper._calculate_philosophical_coherence("Plain description", "cat")
        score_rigorous = mapper._calculate_philosophical_coherence(
            "A coherent theory with systematic framework and logical principles",
            "cat"
        )

        assert score_rigorous > score_plain


class TestIntegrationPotentialCalculation:
    """Tests for integration potential metric calculation."""

    @pytest.fixture
    def mapper(self):
        return CGPMapper()

    def test_base_score(self, mapper):
        """Base score is 0.5."""
        score = mapper._calculate_integration_potential("unknown", "")
        assert score >= 0.5

    def test_integrative_categories(self, mapper):
        """Integrative categories increase score."""
        score_unknown = mapper._calculate_integration_potential("unknown", "")
        score_relational = mapper._calculate_integration_potential("relational", "")
        score_quantum = mapper._calculate_integration_potential("quantum", "")

        assert score_relational > score_unknown
        assert score_quantum > score_unknown

    def test_computational_categories(self, mapper):
        """Computational categories get bonus."""
        score_unknown = mapper._calculate_integration_potential("unknown", "")
        score_computational = mapper._calculate_integration_potential("computational", "")

        assert score_computational > score_unknown


class TestConstellationAnchor:
    """Tests for constellation anchor calculation."""

    @pytest.fixture
    def mapper(self):
        return CGPMapper()

    def test_anchor_format(self, mapper):
        """Anchor has correct format."""
        anchor = mapper._calculate_constellation_anchor(1.5, 2.5, 3.5, "test")
        assert anchor.startswith("test_")

    def test_anchor_bucketing(self, mapper):
        """Coordinates are bucketed correctly."""
        # Values in same bucket should produce same anchor
        anchor1 = mapper._calculate_constellation_anchor(0.5, 0.5, 0.5, "cat")
        anchor2 = mapper._calculate_constellation_anchor(1.0, 1.0, 1.0, "cat")

        assert anchor1 == anchor2  # Both round to 0_0_0

        # Different buckets
        anchor3 = mapper._calculate_constellation_anchor(3.0, 3.0, 3.0, "cat")
        assert anchor3 != anchor1


class TestPublishToHirag:
    """Tests for Hi-RAG v2 publishing."""

    @pytest.fixture
    def mapper(self):
        return CGPMapper()

    @pytest.mark.asyncio
    async def test_publish_success(self, mapper):
        """Successful publish returns result."""
        packet = {
            "version": "cgp.v1",
            "theory": {"id": "test:theory"},
            "geometry": {}
        }

        with mock.patch.object(mapper.client, 'post') as mock_post:
            mock_response = mock.Mock()
            mock_response.json.return_value = {"status": "indexed"}
            mock_response.raise_for_status = mock.Mock()
            mock_post.return_value = mock_response

            result = await mapper.publish_to_hirag(packet)

            assert result["status"] == "indexed"
            mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_failure(self, mapper):
        """Failed publish raises exception."""
        import httpx

        packet = {"version": "cgp.v1", "theory": {"id": "test"}}

        with mock.patch.object(mapper.client, 'post') as mock_post:
            mock_post.side_effect = httpx.HTTPError("Connection failed")

            with pytest.raises(httpx.HTTPError):
                await mapper.publish_to_hirag(packet)


class TestBatchPublish:
    """Tests for batch publishing."""

    @pytest.fixture
    def mapper(self):
        return CGPMapper()

    @pytest.mark.asyncio
    async def test_batch_publish_success(self, mapper):
        """Batch publish processes all theories."""
        theories = [
            {"name": "Theory 1", "category": "cat1"},
            {"name": "Theory 2", "category": "cat2"},
        ]

        with mock.patch.object(mapper, 'publish_to_hirag') as mock_publish:
            mock_publish.return_value = {"status": "indexed"}

            results = await mapper.batch_publish(theories)

            assert len(results) == 2
            assert all(r["status"] == "success" for r in results)

    @pytest.mark.asyncio
    async def test_batch_publish_partial_failure(self, mapper):
        """Batch publish continues on individual failures."""
        theories = [
            {"name": "Theory 1", "category": "cat1"},
            {"name": "Theory 2", "category": "cat2"},
        ]

        with mock.patch.object(mapper, 'publish_to_hirag') as mock_publish:
            # First succeeds, second fails
            mock_publish.side_effect = [
                {"status": "indexed"},
                Exception("Network error")
            ]

            results = await mapper.batch_publish(theories)

            assert len(results) == 2
            assert results[0]["status"] == "success"
            assert results[1]["status"] == "error"
