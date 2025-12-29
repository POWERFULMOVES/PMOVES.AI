# CHIT Visualize

Render a CHIT packet's mathematical structure using Pmoves-hyperdimensions.

## Arguments

- `$ARGUMENTS` - CGP v2 packet, concept name, or visualization type

## Instructions

1. Parse input (CGP v2 packet or concept to visualize)
2. Extract geometric parameters:
   - Hyperbolic coordinates (Poincaré disk position)
   - Spectral signature (zeta zero resonances)
   - Holographic boundary data
3. Generate visualization request for Pmoves-hyperdimensions:
   ```json
   {
     "type": "poincare_disk" | "zeta_resonance" | "holographic_surface",
     "coordinates": {...},
     "animation": false,
     "export_format": "preview"
   }
   ```
4. Launch visualization in browser or export to file

## Visualization Types

| Type | Description |
|------|-------------|
| `poincare` | Poincaré Disk Model showing hierarchical structure |
| `zeta` | Riemann zeta resonance pattern |
| `holographic` | Holographic boundary projection |
| `combined` | All three layers overlaid |

## Example

```bash
# Visualize a concept's geometric embedding
/chit:visualize concept:"machine learning"

# Visualize a CGP v2 packet
/chit:visualize '{"version": "cgp.v2", ...}'

# Show zeta resonance pattern
/chit:visualize zeta --spectral-signature 14.13,21.02,25.01
```

## Requires

- Pmoves-hyperdimensions submodule (Three.js renderer)
- Browser for interactive visualization

## Related

- `/hyperdim:render` - Direct surface rendering
- `/chit:encode` - Create packet to visualize
