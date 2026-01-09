# Hyperdim Render

Render a parametric surface using the Pmoves-hyperdimensions Three.js visualizer.

## Arguments

- `$ARGUMENTS` - Surface type and parameters

## Instructions

1. Parse surface specification
2. Generate Three.js scene configuration
3. Launch renderer (browser or headless)
4. Display or save output

## Surface Types

| Type | Parameters | Description |
|------|------------|-------------|
| `sphere` | radius, segments | Standard sphere |
| `torus` | R, r, segments | Torus (donut) |
| `klein` | scale | Klein bottle (non-orientable) |
| `mobius` | width, turns | Möbius strip |
| `poincare` | curvature, points | Poincaré disk model |
| `hyperbolic` | k, domain | Hyperbolic paraboloid |
| `zeta` | zeros[], scale | Riemann zeta surface |
| `holographic` | boundary_data | Holographic projection |

## Example

```bash
# Render a Poincaré disk
/hyperdim:render poincare --curvature -1 --points 100

# Render a Klein bottle
/hyperdim:render klein --scale 2

# Render zeta surface with first 3 zeros
/hyperdim:render zeta --zeros 14.13,21.02,25.01

# Render from CHIT packet coordinates
/hyperdim:render hyperbolic --from-cgp '{"hyperbolic_coords": {...}}'
```

## Output

- Interactive: Opens in browser at `file://Pmoves-hyperdimensions/index.html`
- Headless: Renders to PNG/WebP

## Requires

- Pmoves-hyperdimensions submodule
- Browser or headless Chrome for rendering

## Related

- `/hyperdim:animate` - Create animations
- `/hyperdim:export` - Export to 3D formats
- `/chit:visualize` - CHIT-specific visualization
