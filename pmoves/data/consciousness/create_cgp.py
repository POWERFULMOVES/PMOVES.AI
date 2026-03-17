#!/usr/bin/env python3
"""
Generate CGP (CHIT Geometry Packet) for consciousness categories.

Creates minimal valid CGP with 10 super-nodes (one per consciousness category).
"""

import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def create_consciousness_cgp():
    """Create a CGP packet for consciousness categories."""

    # 10 consciousness categories as super-nodes
    categories = [
        {"id": "materialism", "label": "Materialism Theories", "summary": "Consciousness arises from physical brain processes"},
        {"id": "dualism", "label": "Dualisms", "summary": "Mind and matter are fundamentally distinct"},
        {"id": "idealism", "label": "Idealisms", "summary": "Reality is fundamentally mental"},
        {"id": "panpsychism", "label": "Panpsychisms", "summary": "Consciousness is fundamental and ubiquitous"},
        {"id": "monism", "label": "Monisms", "summary": "Reality consists of one fundamental substance"},
        {"id": "non-reductive-physicalism", "label": "Non-Reductive Physicalism", "summary": "Physicalism without reduction to brain states"},
        {"id": "quantum", "label": "Quantum Theories", "summary": "Quantum mechanical explanations of consciousness"},
        {"id": "iit", "label": "Integrated Information Theory", "summary": "Consciousness as integrated information (Phi)"},
        {"id": "anomalous", "label": "Anomalous Altered States", "summary": "Studies informed by altered states"},
        {"id": "challenge", "label": "Challenge Theories", "summary": "Theories challenging standard assumptions"},
    ]

    # Create super-nodes
    super_nodes = []
    for i, cat in enumerate(categories):
        # Position in a circle
        import math
        angle = (2 * math.pi * i) / 10
        radius = 1.0
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)

        super_nodes.append({
            "id": f"super-{cat['id']}",
            "label": cat['label'],
            "summary": cat['summary'],
            "x": x,
            "y": y,
            "r": 0.3,  # radius
            "meta": {
                "category": cat['id'],
                "namespace": "pmoves.consciousness"
            },
            "constellations": [
                {
                    "id": f"constellation-{cat['id']}",
                    "summary": f"{cat['label']} constellation",
                    "anchor": [x, y, 0],  # 3D anchor vector
                    "points": []
                }
            ]
        })

    # Create CGP packet
    cgp = {
        "spec": "chit.cgp.v0.1",
        "summary": "PMOVES Consciousness Taxonomy - 325 theories across 10 categories",
        "meta": {
            "namespace": "pmoves.consciousness",
            "source": "Kuhn Landscape of Consciousness (2024)",
            "generator": "pmoves.consciousness.cgp",
            "total_theories": 325,
            "total_categories": 10
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
        "super_nodes": super_nodes,
        "constellations": [sn["constellations"][0] for sn in super_nodes],
        "points": []
    }

    return cgp


def publish_cgp_to_hirag(cgp):
    """Publish CGP to Hi-RAG via geometry/import_db endpoint."""

    publish_script = f'''
import requests
import json

cgp = {repr(cgp)}

r = requests.post(
    'http://localhost:8086/geometry/import_db',
    json={{"data": cgp}},
    timeout=30
)
r.raise_for_status()  # Raise exception on HTTP errors
print(f"Status: {{r.status_code}}")
print(f"Response: {{r.text[:500]}}")
'''

    temp_dir = tempfile.gettempdir()
    temp_script = Path(temp_dir) / "publish_cgp.py"
    temp_script.parent.mkdir(parents=True, exist_ok=True)
    temp_script.write_text(publish_script, encoding='utf-8')

    # Copy and execute
    subprocess.run([
        'docker', 'cp', str(temp_script), 'pmoves-hi-rag-gateway-v2-1:/tmp/publish_cgp.py'
    ], check=True)

    result = subprocess.run([
        'docker', 'exec', 'pmoves-hi-rag-gateway-v2-1',
        'python', '/tmp/publish_cgp.py'
    ], capture_output=True, text=True)

    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)

    return result.returncode == 0


def main():
    print("Creating consciousness CGP...")
    cgp = create_consciousness_cgp()

    # Save to file
    output_path = Path("pmoves/data/consciousness/geometry_payload.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(cgp, f, indent=2)
    print(f"CGP saved to {output_path}")

    # Publish to Hi-RAG
    print("\\nPublishing to Hi-RAG...")
    success = publish_cgp_to_hirag(cgp)
    return success


if __name__ == "__main__":
    import sys
    sys.exit(0 if main() else 1)
