# BoTZ CHIT Skills Integration Guide

**Service:** BoTZ (Battle of the Zealots) Skills
**Purpose:** CHIT tools and skills for GEOMETRY BUS
**Repository:** `PMOVES-BoTZ/`

---

## Overview

BoTZ provides CLI skills for CHIT (Compressed Hierarchical Information Transfer) encoding, CGP manipulation, and GEOMETRY BUS interaction. These skills enable agents to create, sign, and publish CGP packets.

```mermaid
%%{init: {'theme':'base', 'themeVariables': {
  'primaryColor': '#3ecf8e',
  'primaryBorderColor': '#3ecf8e',
  'secondaryColor': '#9333ea',
  'secondaryBorderColor': '#a855f7',
  'tertiaryColor': '#fbbf24',
  'tertiaryBorderColor': '#d97706',
  'background': 'transparent'
}}}%%
graph TD
    classDef root fill:#3ecf8e,stroke:#2db380,color:#000
    classDef super fill:#9333ea,stroke:#7c2d12,color:#fff
    classDef const fill:#fbbf24,stroke:#d97706,color:#000
    classDef point fill:#404040,stroke:#525252,color:#ededed
    classDef sig fill:#ef4444,stroke:#dc2626,color:#fff

    CGP["📦 CGP Packet<br/>spec: chit.cgp.v1.0"]:::root
    CGP --> SUMMARY["summary: string"]:::point
    CGP --> CREATED["created_at: string"]:::point
    CGP --> NODES["super_nodes: array"]:::point
    NODES --> SUP["🔷 Super Node<br/>id, label, x, y, r"]:::super
    SUP --> CONSTS["constellations: array"]:::point
    CONSTS --> CONST["🌟 Constellation<br/>id, anchor, spectrum"]:::const
    CONST --> PTS["points: array"]:::point
    PTS --> PT["📍 Point<br/>id, modality, proj, conf"]:::point
    CGP -.->|"optional"| SIG["🔐 sig: object<br/>HMAC-SHA256"]:::sig
```

> **📊 Diagram Source:** [diagrams/cgp-structure.mmd](../diagrams/cgp-structure.mmd)

---

## Available Skills

### `/chit:encode`

Encode data into a CHIT Geometry Packet.

```bash
/chit:encode --data "key1=value1,key2=value2" \
             --namespace "pmoves.test" \
             --description "Test CGP packet"
```

**Output:**
```json
{
  "version": "chit.cgp.v1.0",
  "namespace": "pmoves.test",
  "description": "Test CGP packet",
  "points": [
    {
      "label": "key1",
      "value": "value1",
      "anchor": [0.123, 0.456, 0.789],
      "encoding": "cleartext"
    },
    {
      "label": "key2",
      "value": "value2",
      "anchor": [0.234, 0.567, 0.890],
      "encoding": "cleartext"
    }
  ]
}
```

**Options:**
- `--data`: Key-value pairs (format: `key=value,key2=value2`)
- `--namespace`: CGP namespace (default: `pmoves.secrets`)
- `--description`: Human-readable description
- `--output`: Output file path
- `--sign`: Sign with CHIT passphrase (requires `CHIT_PROD_PASSPHRASE`)
- `--publish`: Publish to NATS (`geometry.packet.encoded.v1`)

---

### `/chit:decode`

Decode a CHIT Geometry Packet back to data.

```bash
/chit:decode --file cgp.json
```

**Output:**
```
key1=value1
key2=value2
```

**Options:**
- `--file`: Input CGP file path
- `--format`: Output format (`text`, `json`)

---

### `/chit:tokenism`

Process CGP packets through Tokenism attribution.

```bash
/chit:tokenism --input cgp.json \
               --agent-id "claude-opus-4-6" \
               --contribution-type "theory_generation"
```

**Output:**
```json
{
  "attribution_id": "attr_20260313_120000",
  "timestamp": "2026-03-13T12:00:00Z",
  "agent_id": "claude-opus-4-6",
  "cgp_id": "cgp_20260313_120000",
  "contribution_type": "theory_generation",
  "contribution_weight": 0.35,
  "geometry_hash": "sha256:abc123..."
}
```

**Options:**
- `--input`: Input CGP file
- `--agent-id`: Agent identifier
- `--contribution-type`: `theory_generation`, `cgp_construction`, `calibration`
- `--publish`: Publish attribution to NATS (`tokenism.attribution.recorded.v1`)

---

### `/chit:sign-trail`

Sign a Graphiti trail entry with CHIT HMAC for provenance.

```bash
/chit:sign-trail --summary "Completed CONCH pipeline implementation" \
                 --agent-id "claude-opus-4-6" \
                 --phase "Phase H"
```

**Output:**
```json
{
  "agent_id": "claude-opus-4-6",
  "agent_glyph": "#7C3AED",
  "agent_voice": "purple",
  "phase": "Phase H",
  "timestamp": "2026-03-13T12:00:00Z",
  "summary": "Completed CONCH pipeline implementation",
  "resonance": ["security", "architecture"],
  "signature": {
    "alg": "HMAC-SHA256",
    "hmac": "base64-encoded-signature",
    "key_id": "CHIT_PROD_PASSPHRASE"
  }
}
```

**Options:**
- `--summary`: One-line summary
- `--agent-id`: Agent identifier (default: auto-detect)
- `--phase`: Phase identifier
- `--resonance`: Comma-separated tags
- `--publish`: Publish to NATS (`agent.graphiti.signed.v1`)

---

### `/chit:visualize`

Visualize CGP packets as geometric shapes.

```bash
/chit:visualize --input cgp.json \
                --format "text" \
                --output visualization.txt
```

**Output (text format):**
```
CGP: chit.cgp.v1.0
Namespace: pmoves.consciousness

Super Nodes: 1
├── consciousness_materialism
│   Position: (2.5, 3.2, 5.0)
│   Constellations: 2
│   ├── constellation-0 (Materialist theories)
│   │   Anchor: [0.5, 0.3, 0.8]
│   │   Points: 3
│   │   └── point-001: "Physicalism is..." (conf: 0.9)
│   └── constellation-1 (Dualist theories)
│       Anchor: [0.3, 0.7, 0.4]
│       Points: 2
```

**Options:**
- `--input`: Input CGP file
- `--format`: `text`, `json`, `html`
- `--output`: Output file path

---

## NATS Integration

### Publishing CGP

```bash
# Encode and publish
/chit:encode --data "theory=Materialism" \
             --publish \
             --subject "geometry.cgp.v1"

# Publish existing CGP
/chit:encode --input cgp.json \
             --publish \
             --subject "geometry.cgp.v1"
```

### Subscribing to CGP

```bash
# Monitor CGP packets
/chit:bus --subscribe "geometry.cgp.v1"

# Monitor all geometry subjects
/chit:bus --subscribe "geometry.>"
```

---

## Environment Variables

### Required for Signing

| Variable | Purpose | Default |
|----------|---------|---------|
| `CHIT_PROD_PASSPHRASE` | CGP signing key | (required for signing) |

### Optional

| Variable | Purpose | Default |
|----------|---------|---------|
| `NATS_URL` | NATS connection | `nats://nats:pmoves@nats:4222` |
| `CGP_OUTPUT_DIR` | CGP file output | `./cgps` |
| `CGP_NAMESPACE` | Default namespace | `pmoves.secrets` |

---

## Skill Pairings

BoTZ CHIT skills participate in these pipelines (see `skill-pairings.yaml`):

| Pairing | Skills | Agents | NATS Subject |
|---------|--------|--------|--------------|
| `ingest-chit-index` | extract → chit-encode → hirag-index | extract-worker → tokenism → hirag | `skills.pipeline.ingest-chit-index.v1` |
| `chit-3d-viz` | chit-encode → threejs-render | tokenism → hyperdimensions | `skills.pipeline.chit-3d-viz.v1` |

### Ingest-CHIT-Index Pipeline

```
1. Extract Worker (8083)
   └─> Text embeddings

2. /chit:encode
   ├─> CGP packet construction
   ├─> CHIT signing (if passphrase available)
   └─> geometry.packet.encoded.v1

3. Hi-RAG v2 (8086)
   ├─> Vector search integration
   ├─> Neo4j graph traversal
   └─> Full-text keyword matching
```

### CHIT-3D-Viz Pipeline

```
1. /chit:encode
   └─> CGP packet generation

2. Hyperdimensions
   ├─> Three.js WebGL rendering
   └─> Interactive 3D visualization
```

---

## Usage Examples

### Python Integration

```python
import subprocess
import json

# Encode data to CGP
result = subprocess.run([
    "/chit:encode",
    "--data", "theory=Materialism,category=materialism",
    "--namespace", "pmoves.consciousness",
    "--output", "cgp.json"
], capture_output=True, text=True)

# Load CGP
with open("cgp.json") as f:
    cgp = json.load(f)

# Visualize
subprocess.run([
    "/chit:visualize",
    "--input", "cgp.json",
    "--format", "text"
])
```

### CLI Workflow

```bash
# 1. Create CGP from data
/chit:encode \
  --data "name=Materialism,category=materialism" \
  --namespace "pmoves.consciousness" \
  --output theory.json

# 2. Sign with CHIT
/chit:encode \
  --input theory.json \
  --sign \
  --output theory_signed.json

# 3. Publish to GEOMETRY BUS
/chit:encode \
  --input theory_signed.json \
  --publish \
  --subject "geometry.cgp.v1"

# 4. Visualize
/chit:visualize \
  --input theory_signed.json \
  --format "text"
```

---

## Troubleshooting

### Common Issues

**Issue:** `CHIT_PROD_PASSPHRASE not set`
```
Solution: Set environment variable or skip signing
For signing: export CHIT_PROD_PASSPHRASE=your-passphrase
For unsigned: omit --sign flag
```

**Issue:** NATS publish fails
```
Solution: Verify NATS_URL includes credentials
Check: nats://nats:pmoves@nats:4222
```

**Issue:** CGP spec version mismatch
```
Solution: BoTZ uses canonical version "chit.cgp.v1.0"
Verify with: /chit:decode --file cgp.json
```

### Debug Commands

```bash
# Check CHIT module
python -c "from pmoves.chit import CGP_SPEC_VERSION; print(CGP_SPEC_VERSION)"

# Test encoding
/chit:encode --data "test=value" --output test.json

# Test visualization
/chit:visualize --input test.json

# Monitor NATS
/chit:bus --subscribe "geometry.>"
```

---

## References

- **Main Docs:** [README.md](../README.md)
- **NATS Subjects:** [nats-subjects.md](../nats-subjects.md)
- **CHIT Module:** `pmoves/chit/__init__.py`
- **BoTZ Repository:** `PMOVES-BoTZ/`
- **Skill Pairings:** `pmoves/configs/skill-pairings.yaml`
