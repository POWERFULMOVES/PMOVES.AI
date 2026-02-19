"""Tests for CGP v1.0 runtime support.

Validates that the Pydantic models, version detection, decoder, and
backward compatibility all work correctly with the v1.0 spec additions.
"""

import pytest

from pmoves.services.common.geometry_models import (
    CGP,
    CGP_VERSION_V01,
    CGP_VERSION_V02,
    CGP_VERSION_V10,
    SUPPORTED_VERSIONS,
    Constellation,
    GeometryData,
    HyperbolicEncoding,
    MACAConsensus,
    NATSMetadata,
    Point,
    SuperNode,
    TextFragment,
    detect_cgp_version,
    cgp_dict_to_model,
)
from pmoves.services.common.geometry_decoder import GeometryDecoder


# ---------------------------------------------------------------------------
# Version constant tests
# ---------------------------------------------------------------------------

class TestVersionConstants:
    def test_v10_constant_value(self):
        assert CGP_VERSION_V10 == "chit.cgp.v1.0"

    def test_v10_in_supported_versions(self):
        assert CGP_VERSION_V10 in SUPPORTED_VERSIONS

    def test_all_versions_present(self):
        assert CGP_VERSION_V01 in SUPPORTED_VERSIONS
        assert CGP_VERSION_V02 in SUPPORTED_VERSIONS
        assert CGP_VERSION_V10 in SUPPORTED_VERSIONS


# ---------------------------------------------------------------------------
# Version detection tests
# ---------------------------------------------------------------------------

class TestVersionDetection:
    def test_detect_v10_from_spec(self):
        cgp = {"spec": "chit.cgp.v1.0", "super_nodes": []}
        assert detect_cgp_version(cgp) == "chit.cgp.v1.0"

    def test_detect_v02_still_works(self):
        cgp = {"spec": "chit.cgp.v0.2", "super_nodes": [], "attribution": {}}
        assert detect_cgp_version(cgp) == "chit.cgp.v0.2"

    def test_detect_v01_still_works(self):
        cgp = {"spec": "chit.cgp.v0.1", "super_nodes": [{"id": "sn1", "constellations": []}]}
        assert detect_cgp_version(cgp) == "chit.cgp.v0.1"


# ---------------------------------------------------------------------------
# New model tests
# ---------------------------------------------------------------------------

class TestNewModels:
    def test_hyperbolic_encoding(self):
        enc = HyperbolicEncoding(poincare=[0.3, 0.4], curvature=-1.0)
        assert enc.poincare == [0.3, 0.4]
        assert enc.curvature == -1.0

    def test_hyperbolic_encoding_default_curvature(self):
        enc = HyperbolicEncoding(poincare=[0.0, 0.0])
        assert enc.curvature == -1.0

    def test_maca_consensus(self):
        mc = MACAConsensus(entropy_delta=0.05, votes=[1, 0, 1, 1], confidence=0.87)
        assert mc.entropy_delta == 0.05
        assert mc.votes == [1, 0, 1, 1]
        assert mc.confidence == 0.87

    def test_maca_consensus_default_votes(self):
        mc = MACAConsensus(entropy_delta=0.1, confidence=0.9)
        assert mc.votes == []

    def test_nats_metadata(self):
        nm = NATSMetadata(
            subject="geometry.cgp.v1",
            timestamp="2026-02-18T00:00:00Z",
            publisher_id="tokenism-sim",
            stream="GEOMETRY",
        )
        assert nm.subject == "geometry.cgp.v1"
        assert nm.stream == "GEOMETRY"

    def test_nats_metadata_all_optional(self):
        nm = NATSMetadata()
        assert nm.subject is None
        assert nm.timestamp is None
        assert nm.publisher_id is None
        assert nm.stream is None


# ---------------------------------------------------------------------------
# Extended existing model tests
# ---------------------------------------------------------------------------

class TestExtendedModels:
    def test_point_v10_fields(self):
        p = Point(
            id="p1",
            x=0.1,
            y=0.2,
            text="hello",
            contributor_id="user-42",
            merkle_proof=["abc", "def"],
            weight=0.75,
        )
        assert p.contributor_id == "user-42"
        assert p.merkle_proof == ["abc", "def"]
        assert p.weight == 0.75

    def test_point_v10_fields_optional(self):
        p = Point(id="p2", x=0.5, y=0.5)
        assert p.contributor_id is None
        assert p.merkle_proof is None
        assert p.weight is None

    def test_constellation_v10_fields(self):
        mc = MACAConsensus(entropy_delta=0.02, votes=[1, 1], confidence=0.95)
        c = Constellation(
            id="c1",
            spectrum_zeta=[0.5, 0.3, 0.2],
            maca_consensus=mc,
        )
        assert c.spectrum_zeta == [0.5, 0.3, 0.2]
        assert c.maca_consensus.confidence == 0.95

    def test_constellation_v10_fields_optional(self):
        c = Constellation(id="c2")
        assert c.spectrum_zeta is None
        assert c.maca_consensus is None

    def test_supernode_v10_fields(self):
        hyp = HyperbolicEncoding(poincare=[0.1, 0.2])
        sn = SuperNode(
            id="sn1",
            x=0.3,
            y=0.4,
            r=0.5,
            hyperbolic=hyp,
        )
        assert sn.x == 0.3
        assert sn.y == 0.4
        assert sn.r == 0.5
        assert sn.hyperbolic.poincare == [0.1, 0.2]

    def test_supernode_v10_fields_optional(self):
        sn = SuperNode(id="sn2")
        assert sn.x is None
        assert sn.y is None
        assert sn.r is None
        assert sn.hyperbolic is None

    def test_cgp_nats_field(self):
        nats = NATSMetadata(subject="geometry.cgp.v1")
        cgp = CGP(
            spec="chit.cgp.v1.0",
            super_nodes=[],
            nats=nats,
        )
        assert cgp.nats.subject == "geometry.cgp.v1"

    def test_cgp_nats_optional(self):
        cgp = CGP(spec="chit.cgp.v1.0", super_nodes=[])
        assert cgp.nats is None

    def test_cgp_default_spec_is_v10(self):
        cgp = CGP(super_nodes=[])
        assert cgp.spec == "chit.cgp.v1.0"

    def test_geometry_data_new_flags(self):
        gd = GeometryData(
            version="chit.cgp.v1.0",
            num_super_nodes=1,
            num_constellations=2,
            num_points=5,
            has_attribution=False,
            has_signature=False,
            has_maca_consensus=True,
            has_hyperbolic=True,
        )
        assert gd.has_maca_consensus is True
        assert gd.has_hyperbolic is True

    def test_geometry_data_flags_default_false(self):
        gd = GeometryData(
            version="chit.cgp.v1.0",
            num_super_nodes=0,
            num_constellations=0,
            num_points=0,
            has_attribution=False,
            has_signature=False,
        )
        assert gd.has_maca_consensus is False
        assert gd.has_hyperbolic is False

    def test_text_fragment_v10_fields(self):
        tf = TextFragment(
            text="sample",
            contributor_id="user-7",
            weight=0.5,
        )
        assert tf.contributor_id == "user-7"
        assert tf.weight == 0.5


# ---------------------------------------------------------------------------
# Full CGP model validation with v1.0 packet
# ---------------------------------------------------------------------------

def _make_v10_packet() -> dict:
    """Build a complete v1.0 CGP dict with all new fields populated."""
    return {
        "spec": "chit.cgp.v1.0",
        "meta": {"namespace": "test"},
        "nats": {
            "subject": "geometry.cgp.v1",
            "timestamp": "2026-02-18T12:00:00Z",
            "publisher_id": "test-pub",
            "stream": "GEOMETRY",
        },
        "super_nodes": [
            {
                "id": "sn-1",
                "label": "Test SuperNode",
                "x": 0.3,
                "y": 0.4,
                "r": 0.5,
                "hyperbolic": {
                    "poincare": [0.3, 0.4],
                    "curvature": -1.0,
                },
                "constellations": [
                    {
                        "id": "c-1",
                        "summary": "Test constellation",
                        "anchor": [0.1, 0.2, 0.3],
                        "spectrum": [0.5, 0.5],
                        "spectrum_zeta": [0.6, 0.4],
                        "maca_consensus": {
                            "entropy_delta": 0.03,
                            "votes": [1, 1, 0],
                            "confidence": 0.92,
                        },
                        "points": [
                            {
                                "id": "p-1",
                                "x": 0.1,
                                "y": 0.2,
                                "text": "hello world",
                                "conf": 0.95,
                                "contributor_id": "user-1",
                                "merkle_proof": ["aaa", "bbb"],
                                "weight": 0.8,
                            }
                        ],
                    }
                ],
            }
        ],
    }


class TestFullV10Packet:
    def test_model_validates_v10_packet(self):
        packet = _make_v10_packet()
        cgp = cgp_dict_to_model(packet)
        assert cgp.spec == "chit.cgp.v1.0"
        assert cgp.nats is not None
        assert cgp.nats.subject == "geometry.cgp.v1"

    def test_supernode_v10_fields_parsed(self):
        packet = _make_v10_packet()
        cgp = cgp_dict_to_model(packet)
        sn = cgp.super_nodes[0]
        assert sn.x == 0.3
        assert sn.hyperbolic is not None
        assert sn.hyperbolic.poincare == [0.3, 0.4]

    def test_constellation_v10_fields_parsed(self):
        packet = _make_v10_packet()
        cgp = cgp_dict_to_model(packet)
        const = cgp.super_nodes[0].constellations[0]
        assert const.spectrum_zeta == [0.6, 0.4]
        assert const.maca_consensus is not None
        assert const.maca_consensus.confidence == 0.92

    def test_point_v10_fields_parsed(self):
        packet = _make_v10_packet()
        cgp = cgp_dict_to_model(packet)
        point = cgp.super_nodes[0].constellations[0].points[0]
        assert point.contributor_id == "user-1"
        assert point.merkle_proof == ["aaa", "bbb"]
        assert point.weight == 0.8


# ---------------------------------------------------------------------------
# Backward compatibility tests
# ---------------------------------------------------------------------------

class TestBackwardCompat:
    def test_v02_packet_still_validates(self):
        packet = {
            "spec": "chit.cgp.v0.2",
            "super_nodes": [
                {
                    "id": "sn-1",
                    "constellations": [
                        {
                            "id": "c-1",
                            "anchor": [0.1, 0.2, 0.3],
                            "points": [{"id": "p-1", "x": 0.1, "y": 0.2}],
                        }
                    ],
                }
            ],
            "attribution": {
                "dirichlet_weights": [0.6, 0.4],
            },
        }
        cgp = cgp_dict_to_model(packet)
        assert cgp.spec == "chit.cgp.v0.2"
        assert cgp.nats is None

    def test_v02_shaped_with_v10_spec_validates(self):
        """A minimal v0.2-shaped packet with spec bumped to v1.0 should still validate."""
        packet = {
            "spec": "chit.cgp.v1.0",
            "super_nodes": [
                {
                    "id": "sn-1",
                    "constellations": [
                        {
                            "id": "c-1",
                            "anchor": [0.1, 0.2, 0.3],
                            "points": [],
                        }
                    ],
                }
            ],
        }
        cgp = cgp_dict_to_model(packet)
        assert cgp.spec == "chit.cgp.v1.0"
        # All v1.0 fields should default to None
        assert cgp.nats is None
        sn = cgp.super_nodes[0]
        assert sn.x is None
        assert sn.hyperbolic is None
        const = sn.constellations[0]
        assert const.spectrum_zeta is None
        assert const.maca_consensus is None


# ---------------------------------------------------------------------------
# Decoder tests
# ---------------------------------------------------------------------------

class TestDecoderV10:
    def setup_method(self):
        self.decoder = GeometryDecoder()

    def test_validate_v10_packet(self):
        packet = _make_v10_packet()
        result = self.decoder.validate_cgp(packet)
        assert result.valid is True
        assert result.version == "chit.cgp.v1.0"

    def test_extract_geometry_maca_flag(self):
        packet = _make_v10_packet()
        geo = self.decoder.extract_geometry(packet)
        assert geo.has_maca_consensus is True

    def test_extract_geometry_hyperbolic_flag(self):
        packet = _make_v10_packet()
        geo = self.decoder.extract_geometry(packet)
        assert geo.has_hyperbolic is True

    def test_extract_geometry_spectrum_zeta(self):
        packet = _make_v10_packet()
        geo = self.decoder.extract_geometry(packet)
        assert "c-1:zeta" in geo.spectrum_summary
        assert geo.spectrum_summary["c-1:zeta"] == [0.6, 0.4]

    def test_extract_text_contributor_id(self):
        packet = _make_v10_packet()
        fragments = self.decoder.extract_text(packet)
        assert len(fragments) == 1
        assert fragments[0].contributor_id == "user-1"
        assert fragments[0].weight == 0.8

    def test_decode_full_v10_packet(self):
        packet = _make_v10_packet()
        result = self.decoder.decode_cgp(packet, verify_sig=False)
        assert result.version == "chit.cgp.v1.0"
        assert result.geometry.has_maca_consensus is True
        assert result.geometry.has_hyperbolic is True
        assert len(result.text_fragments) == 1

    def test_decode_v02_packet_backward_compat(self):
        packet = {
            "spec": "chit.cgp.v0.2",
            "super_nodes": [
                {
                    "id": "sn-1",
                    "constellations": [
                        {
                            "id": "c-1",
                            "anchor": [0.1, 0.2, 0.3],
                            "points": [
                                {"id": "p-1", "x": 0.1, "y": 0.2, "text": "old text"},
                            ],
                        }
                    ],
                }
            ],
        }
        result = self.decoder.decode_cgp(packet, verify_sig=False)
        assert result.version == "chit.cgp.v0.2"
        assert result.geometry.has_maca_consensus is False
        assert result.geometry.has_hyperbolic is False
        assert len(result.text_fragments) == 1
        assert result.text_fragments[0].contributor_id is None

    def test_no_maca_no_hyperbolic_flags(self):
        """Packet without MACA/hyperbolic should have flags as False."""
        packet = {
            "spec": "chit.cgp.v1.0",
            "super_nodes": [
                {
                    "id": "sn-1",
                    "constellations": [
                        {
                            "id": "c-1",
                            "anchor": [0.1, 0.2, 0.3],
                            "points": [],
                        }
                    ],
                }
            ],
        }
        geo = self.decoder.extract_geometry(packet)
        assert geo.has_maca_consensus is False
        assert geo.has_hyperbolic is False
