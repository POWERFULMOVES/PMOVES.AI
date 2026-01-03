# Hyperdim Animate

Create animated visualizations of parametric surfaces and CHIT geometric transformations.

## Arguments

- `$ARGUMENTS` - Animation type and parameters

## Instructions

1. Parse animation specification
2. Configure keyframes and transitions
3. Render animation frames
4. Compile to video or GIF

## Animation Types

| Type | Description |
|------|-------------|
| `rotate` | Rotate surface around axis |
| `morph` | Morph between two surfaces |
| `flow` | Animate flow along surface |
| `pulse` | Pulsing/breathing effect |
| `trajectory` | Animate point trajectory |
| `zeta_walk` | Walk along Riemann zeta critical line |

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--duration` | 5s | Animation duration |
| `--fps` | 30 | Frames per second |
| `--loop` | false | Loop animation |
| `--easing` | linear | Easing function |
| `--output` | preview | Output: preview, gif, mp4, webm |

## Example

```bash
# Rotate a torus
/hyperdim:animate rotate torus --axis y --duration 10s --output gif

# Morph sphere to klein bottle
/hyperdim:animate morph sphere klein --duration 5s

# Animate zeta walk along critical line
/hyperdim:animate zeta_walk --from 14 --to 30 --output mp4

# Pulse a holographic boundary
/hyperdim:animate pulse holographic --frequency 2hz --duration 3s
```

## Output Formats

| Format | Use Case |
|--------|----------|
| `preview` | Interactive browser preview |
| `gif` | Documentation, README |
| `mp4` | High-quality video |
| `webm` | Web embedding |
| `frames` | Individual PNG frames |

## Requires

- Pmoves-hyperdimensions submodule
- FFmpeg for video encoding

## Related

- `/hyperdim:render` - Static rendering
- `/hyperdim:export` - Export 3D models
