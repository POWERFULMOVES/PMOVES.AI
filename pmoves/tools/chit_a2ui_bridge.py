import json
import argparse
import sys
from typing import Dict, Any

def transpile_cgp_to_a2ui(cgp_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transpiles a Consciousness Geometry Protocol (CGP) JSON payload into an
    a2ui.animation.v1 specification for Remotion 4.0.436 rendering.

    Remotion 4.x changes reflected:
    - Mandatory `defaultProps` on every composition
    - `calculateMetadata` function stub for dynamic duration/fps from audio
    - `schema` field pointing to @remotion/zod-types definitions
    - `sfx_anchors` list for @remotion/sfx beat-sync audio hooks
    - New `colorSpace: "bt601"` for correct audio-visual colour grading

    Acts as the bridge for BoTZ CHIT skills, translating mathematical
    "Holographic Blocks" into visual orchestrations (scenes, elements, animations).
    """

    metadata   = cgp_data.get("metadata", {})
    namespace  = metadata.get("namespace", "CGP Visualization")
    subject    = metadata.get("subject", "unknown.cgp")
    event_id   = metadata.get("event_id", "unknown")
    source     = cgp_data.get("source", "cipher_beats_analyst")

    # Detect audio source from CGP (beats pipeline sets file path in metadata)
    audio_file = metadata.get("audio_file", None)

    # Duration: use CGP duration hint, fall back to 300 frames @ 30fps (10s)
    duration_frames = int(metadata.get("duration_frames", 300))
    fps             = int(metadata.get("fps", 30))

    a2ui_spec = {
        "_remotion_version": "4.0.436",
        "version": "a2ui.animation.v2",  # v2: Remotion 4.x compliant
        "metadata": {
            "title":          namespace,
            "origin_subject": subject,
            "durationInFrames": duration_frames,
            "fps":    fps,
            "width":  1920,
            "height": 1080,
            "colorSpace": "bt601",           # Remotion 4.x alias for 'default' — better broadcast compat
        },
        # ── Remotion 4.x mandatory fields ────────────────────────────────────
        "defaultProps": {
            "cgp_id":       event_id,
            "source":       source,
            "audio_file":   audio_file,
            "playbackRate": 1.0,
        },
        # calculateMetadata stub — the a2ui-renderer fills in actual duration
        # from audio file length when audio_file is present
        "calculateMetadata": {
            "_note": "Implemented in a2ui-renderer src/remotion/A2UIComposition.tsx",
            "resolves": ["durationInFrames", "fps"],
            "audio_driven": audio_file is not None,
        },
        # Zod schema reference for @remotion/zod-types prop validation
        "schema": {
            "_type": "zod",
            "_ref":  "A2UIProps",
            "_pkg":  "@remotion/zod-types",
            "fields": {
                "cgp_id":     "z.string()",
                "source":     "z.string()",
                "audio_file": "z.string().nullable()",
                "playbackRate": "z.number().min(0.1).max(4.0)",
            }
        },
        # ── @remotion/sfx beat anchors ────────────────────────────────────────
        # When audio_file is available, these become sync points for
        # useAudioData() / visualizeAudio() hooks in the renderer
        "sfx_anchors": [],
        "scenes": [
            {
                "id":             "scene_01_cgp_topology",
                "startFrame":     0,
                "durationInFrames": duration_frames,
                "elements":       []
            }
        ],
        "data_bindings": {
            "cgp_source": event_id
        }
    }

    elements = a2ui_spec["scenes"][0]["elements"]

    # 1-2. Traverse canonical CGP nested path: super_nodes[*].constellations[*]
    #      Each constellation has anchor (3D coords), spectrum, and points (tracks).
    element_idx = 0
    for sn in cgp_data.get("super_nodes", []):
        for constellation in sn.get("constellations", []):
            # Map constellation anchor → Text/Glyph Element
            anchor_coords = constellation.get("anchor", [0, 0, 0])
            c_label = constellation.get("label", f"constellation_{element_idx}")

            x = int((anchor_coords[0] + 1) / 2 * 1920) if len(anchor_coords) > 0 else 960
            y = int((anchor_coords[1] + 1) / 2 * 1080) if len(anchor_coords) > 1 else 540

            elements.append({
                "id":      f"anchor_{c_label}",
                "type":    "text",
                "content": c_label,
                "style": {
                    "x": x, "y": y,
                    "fontSize": 48,
                    "color": "#00FFCC",
                    "fontFamily": "Inter, sans-serif"
                },
                "animations": [{
                    "property":        "opacity",
                    "from":            0,
                    "to":              1,
                    "startFrame":      element_idx * 10,
                    "durationInFrames": 15,
                    "easing":         "easeInOut",
                }]
            })

            # Map constellation spectrum → Visual Pulse (with @remotion/sfx sync)
            spectrum = constellation.get("spectrum", [])
            freq = spectrum[0] * 8000 if len(spectrum) > 0 else 60  # Hz back from normalized
            amp  = spectrum[1] if len(spectrum) > 1 else 1.0

            pulse_duration = max(5, int(30 * (60 / max(1, freq))))

            a2ui_spec["sfx_anchors"].append({
                "id":        f"sfx_{element_idx}",
                "freq_hz":   freq,
                "amplitude": amp,
                "frame_hint": element_idx * pulse_duration,
                "sfx_type":  "beat_pulse",
            })

            elements.append({
                "id":     f"spectral_pulse_{element_idx}",
                "type":   "glyph",
                "symbol": "◈",
                "style":  {
                    "x": 960, "y": 540,
                    "fontSize": int(100 * max(amp, 0.1)),
                    "color":    "#FF00FF"
                },
                "sfx_anchor_id": f"sfx_{element_idx}",
                "animations": [{
                    "property":        "scale",
                    "from":            1.0,
                    "to":              1.5 + (amp * 0.5),
                    "startFrame":      0,
                    "durationInFrames": pulse_duration,
                    "loop":            True,
                    "easing":          "spring",
                }]
            })

            # Map each point (track) → sub-element
            for pt in constellation.get("points", []):
                pt.get("label", f"point_{element_idx}")
                proj = pt.get("proj", [0.5, 0.5, 0.5])
                conf = pt.get("conf", 1.0)
                elements.append({
                    "id":      f"point_{pt['id']}" if "id" in pt else f"point_{element_idx}",
                    "type":    "glyph",
                    "symbol":  "●",
                    "style": {
                        "x": int(proj[0] * 1920) if len(proj) > 0 else 960,
                        "y": int(proj[1] * 1080) if len(proj) > 1 else 540,
                        "fontSize": 24,
                        "color": f"rgba(0, 255, 204, {conf:.2f})",
                    },
                    "animations": [{
                        "property":        "opacity",
                        "from":            0,
                        "to":              conf,
                        "startFrame":      element_idx * 5,
                        "durationInFrames": 10,
                        "easing":          "easeInOut",
                    }]
                })

            element_idx += 1

    # 3. Topology Edges → geometry_mesh element
    geometry = cgp_data.get("geometry", {})
    edges    = geometry.get("edges", [])
    if edges:
        elements.append({
            "id":          "topology_mesh",
            "type":        "geometry_mesh",
            "edges_count": len(edges),
            "style": {
                "strokeColor": "rgba(255, 255, 255, 0.5)",
                "strokeWidth": 2
            }
        })

    return a2ui_spec


def main():
    parser = argparse.ArgumentParser(description="Bridge CHIT CGP JSON to Remotion A2UI spec.")
    parser.add_argument("-i", "--input", required=True, help="Input CGP JSON file")
    parser.add_argument("-o", "--output", required=True, help="Output A2UI JSON file")
    
    args = parser.parse_args()
    
    try:
        with open(args.input, "r") as f:
            cgp_data = json.load(f)
            
        a2ui_spec = transpile_cgp_to_a2ui(cgp_data)
        
        with open(args.output, "w") as f:
            json.dump({"spec": a2ui_spec}, f, indent=2)
            
        print(f"Successfully transpiled {args.input} -> {args.output}")
        
    except Exception as e:
        print(f"Error transpiling CGP to A2UI: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
