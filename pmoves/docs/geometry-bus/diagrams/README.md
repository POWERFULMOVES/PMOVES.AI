# GEOMETRY BUS Diagrams

Mermaid diagram source files for GEOMETRY BUS documentation. All diagrams use PMOVES design system colors (primary: `#3ecf8e`, secondary: `#9333ea`).

---

## Diagram Catalog

| Diagram | Type | Description | Used By |
|---------|------|-------------|---------|
| [architecture.mmd](architecture.mmd) | Flowchart | Main GEOMETRY BUS architecture showing publishers, NATS bus, and subscribers | README.md |
| [nats-taxonomy.mmd](nats-taxonomy.mmd) | Graph | NATS subject taxonomy for `geometry.*`, `tokenism.*`, `agentgym.*`, and `research.*` | nats-subjects.md |
| [chr-algorithm.mmd](chr-algorithm.mmd) | Sequence | CHR (Consciousness Holographic Representation) algorithm flow from request to CGP publish | consciousness-service.md |
| [youtube-to-persona.mmd](youtube-to-persona.mmd) | Flowchart | End-to-end pipeline from YouTube ingestion to persona building with CGP output | pipelines/youtube-to-persona.md |
| [chr-to-shapes.mmd](chr-to-shapes.mmd) | Flowchart | Text units → CHR clustering → CGP → Three.js WebGL rendering pipeline | pipelines/chr-to-shapes.md |
| [tokenism-simulation.mmd](tokenism-simulation.mmd) | Flowchart | ToKenism economic simulation with swarm optimization and attribution tracking | tokenism-simulator.md |
| [evo-calibration.mmd](evo-calibration.mmd) | Sequence | EvoController CGP calibration via RL training feedback loop | evo-controller.md |
| [cgp-structure.mmd](cgp-structure.mmd) | Graph | CGP v1.0 packet structure showing all fields and relationships | botz-skills.md |

---

## Rendering Diagrams

### GitHub Native Rendering
All `.mmd` files render natively on GitHub when viewed in the repository.

### PMOVES UI Component
Use the `<Mermaid>` component from `PMOVES-supabase/packages/ui/src/components/Mermaid/Mermaid.tsx`:

```tsx
import { Mermaid } from '@pmoves/ui/components/Mermaid'

// Read diagram content
import architectureDiagram from './diagrams/architecture.mmd'

<Mermaid chart={architectureDiagram} />
```

### CLI Rendering
```bash
# Install mermaid-cli
npm install -g @mermaid-js/mermaid-cli

# Render to PNG
mmdc -i diagrams/architecture.mmd -o architecture.png -t dark -b transparent

# Render to SVG
mmdc -i diagrams/architecture.mmd -o architecture.svg -t dark
```

---

## Design System Colors

All diagrams use PMOVES brand colors:

| Color | Hex | Usage |
|-------|-----|-------|
| Primary (Green) | `#3ecf8e` | Publishers, success states, primary flows |
| Secondary (Purple) | `#9333ea` | Subscribers, processing steps |
| Tertiary (Yellow) | `#fbbf24` | NATS bus, warnings, important elements |
| Dark Gray | `#404040` | Secondary elements, research subjects |
| Red | `#ef4444` | Signatures, security elements |

---

## Creating New Diagrams

### Mermaid Syntax
Use the `%%{init: ...}%%` block at the top of each diagram to set theme variables:

```mermaid
%%{init: {'theme':'base', 'themeVariables': {
  'primaryColor': '#3ecf8e',
  'primaryBorderColor': '#3ecf8e',
  'secondaryColor': '#9333ea',
  'background': 'transparent'
}}}%%
```

### Naming Convention
- Use kebab-case: `service-name-flow.mmd`
- Descriptive names: `youtube-to-persona.mmd` (not `pipeline2.mmd`)
- Include diagram type in filename when ambiguous

### Diagram Types
- **Flowchart (`flowchart TD/LR`)**: Process flows, data pipelines
- **Sequence (`sequenceDiagram`)**: Service interactions, API calls
- **Graph (`graph TD/LR`)**: Taxonomies, hierarchies, structure diagrams

---

## Assets

Generated visual assets (PNG, MP4, WebM) are stored in `../assets/`:

| Asset | Format | Description |
|-------|--------|-------------|
| `constellation.png` | PNG | 3D CGP constellation render via Hyperdimensions |
| `constellation.webm` | WebM | Animated 3D rotation |
| `geometry-bus-overview.mp4` | MP4 | Remotion animation of GEOMETRY BUS |
| `sample_cgp.json` | JSON | Sample CGP packet for testing |

---

## Maintenance

### Updating Diagrams
1. Edit the `.mmd` source file
2. Re-render assets if needed (PNG/MP4)
3. Update this README if adding new diagrams

### Validation
```bash
# Validate Mermaid syntax
npx mermaid-cli --validate diagrams/*.mmd

# Check for broken diagram references
grep -r "diagrams/" ../md | grep -v "README.md"
```

---

## References

- **Mermaid Documentation**: https://mermaid.js.org/
- **PMOVES UI Component**: `PMOVES-supabase/packages/ui/src/components/Mermaid/Mermaid.tsx`
- **A2UI Animation Schema**: `pmoves/contracts/a2ui-animation-schema.json`
- **CGP Schema**: `pmoves/contracts/schemas/chit/cgp.v1.schema.json`
