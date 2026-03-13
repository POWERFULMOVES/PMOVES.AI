#!/usr/bin/env python3
"""
CHIT CGP Validation Tool for PMOVES Health Integration

Validates CGP (CHIT Geometry Packet) payloads against the v1.0 schema.
Used for ensuring health constellation data complies with PMOVES.AI's
mathematical framework standards.

Usage:
    python validate_cgp.py <payload.json>
    python validate_cgp.py --test  # Run with test payload

Exit codes:
    0 - Validation successful
    1 - Validation failed
    2 - File/IO error
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict

try:
    import jsonschema
    from jsonschema import validate, ValidationError
except ImportError:
    print("Error: jsonschema not installed. Run: pip install jsonschema")
    sys.exit(2)


def load_schema(schema_path: Path) -> Dict[str, Any]:
    """Load the CGP v1.0 JSON schema."""
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema not found: {schema_path}")

    with open(schema_path, 'r') as f:
        return json.load(f)


def validate_cgp(payload: Dict[str, Any], schema: Dict[str, Any]) -> bool:
    """
    Validate a CGP payload against the schema.

    Args:
        payload: CGP payload dictionary
        schema: JSON schema for validation

    Returns:
        True if validation passes, False otherwise
    """
    try:
        validate(instance=payload, schema=schema)
        return True
    except ValidationError as e:
        print(f"Validation Error: {e.message}")
        print(f"Path: {'.'.join(str(p) for p in e.path)}")
        print(f"Schema path: {'.'.join(str(p) for p in e.schema_path)}")
        return False


def create_test_payload() -> Dict[str, Any]:
    """Create a minimal valid CGP payload for testing."""
    return {
        "spec": "chit.cgp.v1.0",
        "meta": {
            "source": "text",
            "units_mode": "sentences",
            "K": 2,
            "bins": 8,
            "backend": "sentence-transformers/all-MiniLM-L6-v2",
            "created_at": "2026-03-13T12:00:00Z",
            "encoder_version": "1.0.0"
        },
        "super_nodes": [
            {
                "id": "super_0",
                "label": "Workout Intensity",
                "summary": "Exercise intensity clusters",
                "x": -100.0,
                "y": 50.0,
                "constellations": [
                    {
                        "id": "const_0_0",
                        "label": "High Intensity",
                        "summary": "Vigorous exercise sessions",
                        "anchor": [0.1, -0.3, 0.8, 0.5],
                        "radial_minmax": [-0.5, 0.9],
                        "spectrum": [0.1, 0.15, 0.2, 0.15, 0.12, 0.1, 0.1, 0.08]
                    }
                ]
            }
        ]
    }


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate CGP payloads against CHIT v1.0 schema"
    )
    parser.add_argument(
        "payload",
        nargs="?",
        help="Path to CGP payload JSON file"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run validation with test payload"
    )
    parser.add_argument(
        "--schema",
        type=str,
        default=None,
        help="Custom schema path (default: ../chit_schemas/chit.cgp.v1.0.schema.json)"
    )

    args = parser.parse_args()

    # Determine schema path
    if args.schema:
        schema_path = Path(args.schema)
    else:
        script_dir = Path(__file__).parent
        schema_path = script_dir.parent / "chit_schemas" / "chit.cgp.v1.0.schema.json"

    # Load schema
    try:
        schema = load_schema(schema_path)
        print(f"Loaded schema: {schema_path}")
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)

    # Load or create payload
    if args.test:
        print("Using test payload...")
        payload = create_test_payload()
    elif args.payload:
        payload_path = Path(args.payload)
        try:
            with open(payload_path, 'r') as f:
                payload = json.load(f)
            print(f"Loaded payload: {payload_path}")
        except FileNotFoundError:
            print(f"Error: Payload file not found: {payload_path}", file=sys.stderr)
            sys.exit(2)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in payload: {e}", file=sys.stderr)
            sys.exit(2)
    else:
        parser.print_help()
        sys.exit(2)

    # Validate
    print("\nValidating CGP payload...")
    if validate_cgp(payload, schema):
        print("[OK] Validation PASSED")
        print(f"  - spec: {payload.get('spec')}")
        print(f"  - source: {payload.get('meta', {}).get('source')}")
        print(f"  - K: {payload.get('meta', {}).get('K')} constellations")
        print(f"  - super_nodes: {len(payload.get('super_nodes', []))}")
        sys.exit(0)
    else:
        print("[FAIL] Validation FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
