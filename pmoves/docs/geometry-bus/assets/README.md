# GEOMETRY BUS Visual Assets

Visual assets for GEOMETRY BUS documentation including Remotion animations, Three.js renders, and sample data.

---

## Asset Catalog

| Asset | Type | Format | Description | Status |
|-------|------|--------|-------------|--------|
| `geometry-bus-overview.json` | A2UI Spec | JSON | Remotion animation spec for GEOMETRY BUS overview | ✅ Created |
| `geometry-bus-overview.mp4` | Animation | MP4 | Rendered 15-second overview animation (1080p, 30fps) | ⏳ Pending |
| `constellation.png` | 3D Render | PNG | Static 3D CGP constellation visualization | ⏳ Pending |
| `constellation.webm` | 3D Animation | WebM | Rotating 3D constellation (5 seconds, loop) | ⏳ Pending |
| `sample_cgp.json` | Sample Data | JSON | Sample CGP v1.0 packet with 8 constellations | ✅ Created |

---

## Generating Assets

### Remotion Animation (Overview)

**Prerequisites:**
- A2UI Renderer service running: `http://localhost:8105`
- Remotion skill available: `/remotion-render`

**Command:**
```bash
# Render using BoTZ skill
/remotion-render --file pmoves/docs/geometry-bus/assets/geometry-bus-overview.json \
                  --format mp4 \
                  --quality high \
                  --output pmoves/docs/geometry-bus/assets/geometry-bus-overview.mp4
```

**Expected output:**
- Duration: 15 seconds
- Resolution: 1920x1080 (1080p)
- FPS: 30
- Codec: H.264

---

### Three.js Renders (Constellation)

**Prerequisites:**
- Hyperdimensions skill available: `/hyperdim:render`
- Sample CGP: `sample_cgp.json`

**Static PNG Render:**
```bash
/hyperdim:render --file pmoves/docs/geometry-bus/assets/sample_cgp.json \
                 --format png \
                 --output pmoves/docs/geometry-bus/assets/constellation.png \
                 --width 1920 \
                 --height 1080 \
                 --background "#0a0a0f"
```

**Animated WebM:**
```bash
/hyperdim:animate --file pmoves/docs/geometry-bus/assets/sample_cgp.json \
                  --duration 5000 \
                  --output pmoves/docs/geometry-bus/assets/constellation.webm \
                  --auto-rotate \
                  --loop true
```

**GLTF Export (for 3D editing):**
```bash
/hyperdim:export --file pmoves/docs/geometry-bus/assets/sample_cgp.json \
                 --format gltf \
                 --output pmoves/docs/geometry-bus/assets/constellation.gltf
```

---

## Sample CGP Data

The `sample_cgp.json` file contains a complete CGP v1.0 packet with:

- **8 constellations** representing consciousness theory categories:
  1. Reductive Physicalism
  2. Property Dualism
  3. Panpsychism
  4. Functionalism
  5. Identity Theory
  6. Epiphenomenalism
  7. Biological Naturalism
  8. Higher-Order Theories

- **24 points** (3 per constellation) with:
  - Proper `modality` values (`text`)
  - `proj` (projection) values 0.72-0.95
  - `conf` (confidence) values 0.7-0.9
  - `summary` descriptions
  - `ref_id` citations

- **CGP structure following** `chit.cgp.v1.0` schema

**Usage:**
```bash
# Load in Python
import json
with open('sample_cgp.json') as f:
    cgp = json.load(f)

# Validate with CHIT module
from pmoves.chit import validate_cgp
validate_cgp(cgp)  # Returns (valid, errors)

# Render with Hyperdimensions
/hyperdim:render --file sample_cgp.json
```

---

## A2UI Animation Schema Reference

The `geometry-bus-overview.json` follows the A2UI animation schema:

```json
{
  "version": "a2ui.animation.v1",
  "canvas": {"width": 1920, "height": 1080, "fps": 30},
  "animation": {"engine": "remotion", "duration_ms": 15000},
  "scenes": [
    {
      "id": "intro",
      "duration_ms": 2000,
      "elements": [
        {"type": "text", "content": "...", "animation": {...}}
      ]
    }
  ]
}
```

**Supported Element Types:**
- `text` - Text content with position and style
- `metric_card` - Data card with title, value, items
- `code_block` - Syntax-highlighted code
- `timeline` - Sequential events display
- `chart` - Data visualization (bar, line, pie, radar)

**Animation Properties:**
- `keyframes` - Array of {at_ms, properties} for animation
- `easing` - "linear", "ease-in", "ease-out", "ease-in-out", "spring"

---

## Asset Maintenance

### Regenerating Assets

When diagrams or data change, regenerate assets:

```bash
# 1. Update sample data (if needed)
# Edit sample_cgp.json

# 2. Re-render 3D visualization
/hyperdim:render --file sample_cgp.json --format png --output constellation.png

# 3. Re-create animation
/remotion-render --file geometry-bus-overview.json --format mp4 --quality high
```

### Version Control

**Commit to Git:**
- ✅ JSON spec files: `geometry-bus-overview.json`, `sample_cgp.json`
- ✅ Generated renders: `*.png`, `*.mp4`, `*.webm`
- ❌ Temporary files: `*.tmp`, `render_*.log`

**Git LFS (if needed):**
```bash
# Track large binary files with Git LFS
git lfs track "*.mp4"
git lfs track "*.webm"
git lfs track "*.png"
```

---

## References

- **A2UI Schema:** `pmoves/contracts/a2ui-animation-schema.json`
- **CGP Schema:** `pmoves/contracts/schemas/chit/cgp.v1.schema.json`
- **Mermaid Diagrams:** `../diagrams/README.md`
- **Main Docs:** `../README.md`
