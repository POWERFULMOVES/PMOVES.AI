# Hyperdimensions Integration Guide

**Service:** hyperdimensions
**Technology:** Three.js WebGL
**Status:** Production Ready
**Submodule:** Pmoves-hyperdimensions
**Repository:** `Pmoves-hyperdimensions/`

---

## Overview

Hyperdimensions is a WebGL-based 3D shape rendering service that visualizes CHIT Geometry Packets (CGP) as interactive geometric forms. It consumes CGP packets from the GEOMETRY BUS and renders them as manipulatable 3D objects.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Hyperdimensions                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Input                     Processing                   Output             │
│  ┌──────────┐            ┌─────────────┐             ┌──────────┐         │
│  │   CGP    │──▶ Portal  │  Three.js   │──▶ WebGL    │  3D      │         │
│  │ Packets  │   Bridge   │  Renderer   │             │ Shapes   │         │
│  └──────────┘            └─────────────┘             └──────────┘         │
│       │                        │                                         │
│       ▼                        ▼                                         │
│  ┌──────────┐            ┌─────────────┐                                   │
│  │geometry  │            │ Prosodic    │                                   │
│  │.cgp.v1   │            │ Mapping     │                                   │
│  └──────────┘            │ (BPM → XYZ) │                                   │
│                          └─────────────┘                                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Architecture

### Portal Bridge

Hyperdimensions uses a Portal bridge for NATS integration, not direct subscription. The Portal component subscribes to `geometry.cgp.v1` and passes CGP packets to the renderer.

```typescript
// Portal subscription
const portal = new Portal({
  natsUrl: "nats://nats:pmoves@nats:4222",
  subjects: ["geometry.cgp.v1"]
});

portal.on("geometry.cgp.v1", (cgp) => {
  renderer.renderCGP(cgp);
});
```

### Three.js Renderer

The renderer converts CGP packets into Three.js scene objects:

1. **Super Nodes** → Three.js Groups
2. **Constellations** → Sub-groups with positioning
3. **Points** → Mesh objects (sphere, box, etc.)
4. **Spectrums** → Color gradients and visual effects

---

## CGP to 3D Mapping

### Super Node → Scene Group

```typescript
function renderSuperNode(superNode: SuperNode): THREE.Group {
  const group = new THREE.Group();

  // Position from x, y, r (spherical coordinates)
  const phi = superNode.y * Math.PI * 2;
  const theta = superNode.x * Math.PI;
  const radius = superNode.r;

  group.position.set(
    radius * Math.sin(theta) * Math.cos(phi),
    radius * Math.sin(theta) * Math.sin(phi),
    radius * Math.cos(theta)
  );

  return group;
}
```

### Constellation → Sub-group

```typescript
function renderConstellation(constellation: Constellation): THREE.Group {
  const group = new THREE.Group();

  // Anchor determines position
  group.position.fromArray(constellation.anchor);

  // Spectrum determines color
  const color = spectrumToColor(constellation.spectrum);

  return group;
}
```

### Point → Mesh

```typescript
function renderPoint(point: Point): THREE.Mesh {
  // Modality determines geometry
  let geometry: THREE.BufferGeometry;

  switch (point.modality) {
    case "text":
      geometry = new THREE.SphereGeometry(0.5, 32, 32);
      break;
    case "image":
      geometry = new THREE.BoxGeometry(1, 1, 1);
      break;
    case "audio":
      geometry = new THREE.ConeGeometry(0.5, 1, 32);
      break;
    default:
      geometry = new THREE.SphereGeometry(0.5, 32, 32);
  }

  // Confidence determines opacity
  const material = new THREE.MeshStandardMaterial({
    transparent: true,
    opacity: point.conf,
    color: spectrumToColor(point.proj)
  });

  return new THREE.Mesh(geometry, material);
}
```

---

## Prosodic Mapping

Hyperdimensions supports prosodic-to-geometric mapping for voice data:

### BPM to 3D Coordinates

```typescript
function prosodicToGeometry(bpm: number, emphasis: number): number[] {
  // Map BPM (60-180) to radius (5-20)
  const radius = map(bpm, 60, 180, 5, 20);

  // Map emphasis (0-1) to color intensity
  const intensity = emphasis;

  return [radius, intensity];
}
```

### Flute-Gateway Integration

Flute-Gateway publishes prosodic CGP to `geometry.event.v1`:

```json
{
  "event_type": "prosodic_cgp",
  "timestamp": "2026-03-13T12:00:00Z",
  "prosodic": {
    "bpm": 120,
    "emphasis": 0.8,
    "pauses": [1.2, 0.5, 2.0]
  },
  "geometry": {
    "radius": 10.0,
    "color": [1.0, 0.8, 0.6]
  }
}
```

---

## Environment Variables

### Required

| Variable | Purpose | Default |
|----------|---------|---------|
| `NEXT_PUBLIC_NATS_URL` | WebSocket NATS URL | `ws://localhost:9222` |

### Optional

| Variable | Purpose | Default |
|----------|---------|---------|
| `NEXT_PUBLIC_RENDERER` | Renderer type | `webgl` |
| `NEXT_PUBLIC_AUTO_ROTATE` | Auto-rotate camera | `true` |
| `NEXT_PUBLIC_SHOW_LABELS` | Show text labels | `true` |

---

## Usage Examples

### React Component

```typescript
import { CGPViewer } from '@hyperdimensions/viewer';

function ConsciousnessVisualizer() {
  const [cgp, setCGP] = useState<CGPPacket | null>(null);

  useEffect(() => {
    // Subscribe to CGP updates
    const portal = new Portal();
    portal.subscribe('geometry.cgp.v1', setCGP);

    return () => portal.disconnect();
  }, []);

  return (
    <CGPViewer
      cgp={cgp}
      autoRotate={true}
      showLabels={true}
      onPointClick={(point) => console.log(point)}
    />
  );
}
```

### Standalone HTML

```html
<!DOCTYPE html>
<html>
<head>
  <script src="https://unpkg.com/hyperdimensionsviewer"></script>
</head>
<body>
  <div id="viewer"></div>

  <script>
    const viewer = new HyperdimensionsViewer('#viewer', {
      natsUrl: 'ws://localhost:9222',
      subjects: ['geometry.cgp.v1'],
      autoRotate: true
    });

    viewer.on('cgp', (cgp) => {
      console.log('Received CGP:', cgp);
    });
  </script>
</body>
</html>
```

---

## Integration with GEOMETRY BUS

### Subscribing to CGP Packets

```typescript
// Direct NATS subscription (Node.js)
import { connect } from 'nats';

const nc = await connect({
  servers: "ws://localhost:9222"
});

const sub = nc.subscribe("geometry.cgp.v1");
for await (const msg of sub) {
  const cgp = JSON.parse(msg.data.toString());
  await viewer.render(cgp);
}
```

### Publishing Render Events

```typescript
// Publish render completion
await nc.publish("geometry.event.v1", JSON.stringify({
  event_type: "render_completed",
  timestamp: new Date().toISOString(),
  cgp_id: cgp.super_nodes[0].id,
  viewer: "hyperdimensions"
}));
```

---

## BoTZ Skill Integration

### `/hyperdim:render` Skill

Render a CGP packet via BoTZ CLI:

```bash
# Render from file
/hyperdim:render --file cgp.json

# Render from NATS (live)
/hyperdim:render --live --subject "geometry.cgp.v1"

# Animate sequence
/hyperdim:animate --sequence cgps/*.json --duration 5000
```

### `/hyperdim:export` Skill

Export rendered shapes:

```bash
# Export as OBJ
/hyperdim:export --file cgp.json --format obj --output shape.obj

# Export as GLTF
/hyperdim:export --file cgp.json --format gltf --output shape.gltf

# Export as PNG (snapshot)
/hyperdim:export --file cgp.json --format png --output snapshot.png
```

---

## Troubleshooting

### Common Issues

**Issue:** WebSocket connection fails
```
Solution: Verify NATS WebSocket port
- Standalone: 9222
- Docked: 9223
Check: nats server info
```

**Issue:** Shapes not rendering
```
Solution: Check CGP spec version
Must be: "chit.cgp.v1.0"
Verify: console.log(cgp.spec)
```

**Issue:** Performance issues with many points
```
Solution: Use LOD (Level of Detail)
Enable: instancing for repeated geometry
Limit: < 1000 points per constellation
```

### Debug Commands

```bash
# Check NATS WebSocket
wscat -c ws://localhost:9222

# Monitor CGP subjects
nats sub "geometry.cgp.v1" --ws

# Test renderer
/hyperdim:render --test
```

---

## References

- **Main Docs:** [README.md](../README.md)
- **NATS Subjects:** [nats-subjects.md](../nats-subjects.md)
- **Submodule:** `Pmoves-hyperdimensions/`
- **BoTZ Skills:** [botz-skills.md](botz-skills.md)
- **Portal:** `Pmoves-hyperdimensions/packages/portal/`
