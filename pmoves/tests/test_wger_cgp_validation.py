"""
Unit tests for CHIT CGP validation in PMOVES Health integration.

Tests CGP schema compliance and validation tool functionality.
"""

import json
import pytest
from pathlib import Path

# Add integrations directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "integrations" / "health-wger" / "tools"))

from validate_cgp import validate_cgp, load_schema, create_test_payload


class TestCGPSchemaValidation:
    """Test CGP v1.0 schema validation."""

    @pytest.fixture
    def schema_path(self):
        """Path to CGP schema."""
        return Path(__file__).parent.parent / "integrations" / "health-wger" / "chit_schemas" / "chit.cgp.v1.0.schema.json"

    @pytest.fixture
    def schema(self, schema_path):
        """Load and return CGP schema."""
        return load_schema(schema_path)

    def test_schema_exists(self, schema_path):
        """Test that schema file exists."""
        assert schema_path.exists(), f"Schema file not found: {schema_path}"

    def test_schema_valid_json(self, schema):
        """Test that schema is valid JSON."""
        assert isinstance(schema, dict)
        assert "$schema" in schema
        assert schema["$schema"] == "http://json-schema.org/draft-07/schema#"

    def test_schema_spec_version(self, schema):
        """Test that schema enforces CGP v1.0 spec."""
        assert schema["properties"]["spec"]["const"] == "chit.cgp.v1.0"

    def test_valid_test_payload(self, schema):
        """Test validation of valid test payload."""
        payload = create_test_payload()
        assert validate_cgp(payload, schema) is True

    def test_missing_spec_field(self, schema):
        """Test that missing 'spec' field fails validation."""
        payload = create_test_payload()
        del payload["spec"]
        assert validate_cgp(payload, schema) is False

    def test_invalid_spec_version(self, schema):
        """Test that wrong spec version fails validation."""
        payload = create_test_payload()
        payload["spec"] = "chit.cgp.v0.2"
        assert validate_cgp(payload, schema) is False

    def test_missing_meta_field(self, schema):
        """Test that missing 'meta' field fails validation."""
        payload = create_test_payload()
        del payload["meta"]
        assert validate_cgp(payload, schema) is False

    def test_missing_super_nodes(self, schema):
        """Test that missing 'super_nodes' field fails validation."""
        payload = create_test_payload()
        del payload["super_nodes"]
        assert validate_cgp(payload, schema) is False

    def test_invalid_source_enum(self, schema):
        """Test that invalid source enum fails validation."""
        payload = create_test_payload()
        payload["meta"]["source"] = "invalid_source"
        assert validate_cgp(payload, schema) is False

    def test_valid_source_types(self, schema):
        """Test all valid source types."""
        valid_sources = ["docx", "text", "latent", "image", "audio", "video"]
        for source in valid_sources:
            payload = create_test_payload()
            payload["meta"]["source"] = source
            assert validate_cgp(payload, schema), f"Failed for source: {source}"

    def test_invalid_units_mode(self, schema):
        """Test that invalid units_mode fails validation."""
        payload = create_test_payload()
        payload["meta"]["units_mode"] = "invalid_mode"
        assert validate_cgp(payload, schema) is False

    def test_valid_units_modes(self, schema):
        """Test all valid units modes."""
        valid_modes = ["paragraphs", "sentences", "tokens", "frames", "samples"]
        for mode in valid_modes:
            payload = create_test_payload()
            payload["meta"]["units_mode"] = mode
            assert validate_cgp(payload, schema), f"Failed for mode: {mode}"

    def test_missing_required_constellation_fields(self, schema):
        """Test that missing required constellation fields fail validation."""
        payload = create_test_payload()

        # Remove anchor
        payload["super_nodes"][0]["constellations"][0].pop("anchor", None)
        assert validate_cgp(payload, schema) is False

    def test_signature_structure(self, schema):
        """Test optional signature field structure."""
        payload = create_test_payload()
        payload["sig"] = {
            "alg": "HMAC-SHA256",
            "kid": "key-identifier-16chars",
            "ts": 1739001600,
            "hmac": "base64-encoded-hmac"
        }
        assert validate_cgp(payload, schema) is True

    def test_invalid_signature_algorithm(self, schema):
        """Test that invalid signature algorithm fails validation."""
        payload = create_test_payload()
        payload["sig"] = {
            "alg": "INVALID-ALG",
            "kid": "key-id",
            "ts": 1739001600,
            "hmac": "base64-hmac"
        }
        assert validate_cgp(payload, schema) is False

    def test_encryption_structure(self, schema):
        """Test optional anchor encryption field structure."""
        payload = create_test_payload()
        payload["super_nodes"][0]["constellations"][0]["anchor_enc"] = {
            "alg": "AES-GCM",
            "iv": "base64-iv",
            "salt": "base64-salt",
            "ct": "base64-ciphertext"
        }
        assert validate_cgp(payload, schema) is True

    def test_nats_metadata(self, schema):
        """Test optional NATS metadata field."""
        payload = create_test_payload()
        payload["nats"] = {
            "subject": "tokenism.geometry.event.v1",
            "timestamp": "2026-03-13T12:00:00Z",
            "publisher_id": "health-wger-publisher",
            "stream": "GEOMETRY_CGP"
        }
        assert validate_cgp(payload, schema) is True

    def test_content_points_optional(self, schema):
        """Test that content points are optional (geometry-only mode)."""
        payload = create_test_payload()
        # Remove points field if exists
        payload["super_nodes"][0]["constellations"][0].pop("points", None)
        assert validate_cgp(payload, schema) is True

    def test_minimal_valid_payload(self, schema):
        """Test minimal valid CGP payload (geometry-only mode)."""
        payload = {
            "spec": "chit.cgp.v1.0",
            "meta": {
                "source": "text",
                "units_mode": "sentences",
                "K": 1,
                "bins": 5,
                "backend": "test-model"
            },
            "super_nodes": [
                {
                    "id": "super_0",
                    "constellations": [
                        {
                            "id": "const_0_0",
                            "anchor": [0.5, 0.5],
                            "radial_minmax": [0.0, 1.0],
                            "spectrum": [0.2, 0.2, 0.2, 0.2, 0.2]
                        }
                    ]
                }
            ]
        }
        assert validate_cgp(payload, schema) is True


class TestHealthConstellationExamples:
    """Test health-specific constellation examples."""

    @pytest.fixture
    def schema(self):
        """Load CGP schema."""
        schema_path = Path(__file__).parent.parent / "integrations" / "health-wger" / "chit_schemas" / "chit.cgp.v1.0.schema.json"
        return load_schema(schema_path)

    def test_workout_constellation_example(self, schema):
        """Test example workout constellation CGP."""
        payload = {
            "spec": "chit.cgp.v1.0",
            "meta": {
                "source": "latent",
                "units_mode": "workouts",
                "K": 3,
                "bins": 8,
                "backend": "sentence-transformers/all-MiniLM-L6-v2",
                "created_at": "2026-03-13T12:00:00Z"
            },
            "super_nodes": [
                {
                    "id": "workout_intensity",
                    "label": "Workout Intensity",
                    "summary": "Exercise intensity clustering",
                    "constellations": [
                        {
                            "id": "high_intensity",
                            "label": "High Intensity",
                            "summary": "Vigorous exercise sessions",
                            "anchor": [0.2, -0.4, 0.7, 0.5],
                            "radial_minmax": [-0.3, 0.8],
                            "spectrum": [0.05, 0.1, 0.15, 0.25, 0.2, 0.15, 0.08, 0.02]
                        },
                        {
                            "id": "moderate_intensity",
                            "label": "Moderate Intensity",
                            "summary": "Moderate exercise sessions",
                            "anchor": [0.1, 0.3, -0.2, 0.9],
                            "radial_minmax": [-0.5, 0.5],
                            "spectrum": [0.1, 0.12, 0.15, 0.18, 0.18, 0.15, 0.08, 0.04]
                        },
                        {
                            "id": "low_intensity",
                            "label": "Low Intensity",
                            "summary": "Light exercise sessions",
                            "anchor": [-0.3, 0.5, 0.2, 0.8],
                            "radial_minmax": [-0.6, 0.3],
                            "spectrum": [0.15, 0.18, 0.2, 0.18, 0.15, 0.08, 0.04, 0.02]
                        }
                    ]
                }
            ]
        }
        assert validate_cgp(payload, schema) is True

    def test_weight_progression_constellation(self, schema):
        """Test example weight progression constellation CGP."""
        payload = {
            "spec": "chit.cgp.v1.0",
            "meta": {
                "source": "text",
                "units_mode": "measurements",
                "K": 2,
                "bins": 6,
                "backend": "sentence-transformers/all-MiniLM-L6-v2"
            },
            "super_nodes": [
                {
                    "id": "weight_trends",
                    "label": "Weight Progression",
                    "summary": "Weight change patterns over time",
                    "constellations": [
                        {
                            "id": "weight_loss",
                            "label": "Weight Loss",
                            "summary": "Periods of weight reduction",
                            "anchor": [0.4, -0.6, 0.7],
                            "radial_minmax": [0.0, 0.9],
                            "spectrum": [0.1, 0.15, 0.25, 0.25, 0.15, 0.1]
                        },
                        {
                            "id": "weight_gain",
                            "label": "Weight Gain",
                            "summary": "Periods of weight increase",
                            "anchor": [-0.5, 0.4, 0.7],
                            "radial_minmax": [-0.2, 0.7],
                            "spectrum": [0.15, 0.2, 0.25, 0.2, 0.15, 0.05]
                        }
                    ]
                }
            ]
        }
        assert validate_cgp(payload, schema) is True
