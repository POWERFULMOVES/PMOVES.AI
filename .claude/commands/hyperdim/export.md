# Hyperdim Export

Export parametric surfaces and CHIT visualizations to various 3D formats.

## Arguments

- `$ARGUMENTS` - Surface specification and export format

## Instructions

1. Render the specified surface
2. Convert to requested format
3. Save to output path or MinIO

## Export Formats

| Format | Extension | Use Case |
|--------|-----------|----------|
| `gltf` | .gltf/.glb | Web, AR/VR, Blender |
| `obj` | .obj | 3D printing, CAD |
| `stl` | .stl | 3D printing |
| `usdz` | .usdz | Apple AR Quick Look |
| `fbx` | .fbx | Game engines, Unity |
| `png` | .png | 2D image capture |
| `svg` | .svg | Vector graphics (2D projections) |

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--format` | gltf | Export format |
| `--output` | ./exports/ | Output directory |
| `--quality` | high | Mesh quality: low, medium, high |
| `--texture` | true | Include textures/materials |
| `--minio` | false | Upload to MinIO bucket |

## Example

```bash
# Export Poincaré disk to GLTF
/hyperdim:export poincare --format gltf --output ./models/

# Export for 3D printing
/hyperdim:export zeta --format stl --quality high

# Export for Apple AR
/hyperdim:export holographic --format usdz --output ./ar/

# Export and upload to MinIO
/hyperdim:export klein --format glb --minio --bucket assets
```

## Storage

Exports can be stored locally or uploaded to MinIO:
- Local: `./exports/` or specified path
- MinIO: `assets` bucket via presign service

## Requires

- Pmoves-hyperdimensions submodule
- three-gltf-exporter for GLTF
- For MinIO: presign service running

## Related

- `/hyperdim:render` - Preview before export
- `/hyperdim:animate` - Animated exports
