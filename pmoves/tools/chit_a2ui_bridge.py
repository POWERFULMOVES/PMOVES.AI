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

    # 1. Map Anchors to Text/Glyph Elements
    anchors = cgp_data.get("anchors", [])
    for idx, anchor in enumerate(anchors):
        agent_id = anchor.get("agent_id", f"agent_{idx}")
        coords   = anchor.get("coordinates", [0, 0, 0])

        x = int((coords[0] + 1) / 2 * 1920) if len(coords) > 0 else 960
        y = int((coords[1] + 1) / 2 * 1080) if len(coords) > 1 else 540

        elements.append({
            "id":      f"anchor_{agent_id}",
            "type":    "text",
            "content": agent_id,
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
                "startFrame":      idx * 10,
                "durationInFrames": 15,
                "easing":         "easeInOut",  # Remotion 4 spring easing
            }]
        })

    # 2. Map Spectral Signatures → Visual Pulses (with @remotion/sfx sync)
    signatures = cgp_data.get("spectral_signatures", [])
    for idx, sig in enumerate(signatures):
        freq = sig.get("frequency_hz", 60)
        amp  = sig.get("amplitude", 1.0)

        pulse_duration = max(5, int(30 * (60 / max(1, freq))))

        # Register as sfx anchor for beat-sync (useAudioData hook in renderer)
        a2ui_spec["sfx_anchors"].append({
            "id":        f"sfx_{idx}",
            "freq_hz":   freq,
            "amplitude": amp,
            "frame_hint": idx * pulse_duration,
            "sfx_type":  "beat_pulse",   # maps to @remotion/sfx useAudioData visualizer
        })

        elements.append({
            "id":     f"spectral_pulse_{idx}",
            "type":   "glyph",
            "symbol": "◈",
            "style":  {
                "x": 960, "y": 540,
                "fontSize": int(100 * amp),
                "color":    "#FF00FF"
            },
            "sfx_anchor_id": f"sfx_{idx}",   # link to audio frame for beat-synced scaling
            "animations": [{
                "property":        "scale",
                "from":            1.0,
                "to":              1.5 + (amp * 0.5),
                "startFrame":      0,
                "durationInFrames": pulse_duration,
                "loop":            True,
                "easing":          "spring",   # Remotion 4 spring()
            }]
        })

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
            json.dump(a2ui_spec, f, indent=2)
            
        print(f"Successfully transpiled {args.input} -> {args.output}")
        
    except Exception as e:
        print(f"Error transpiling CGP to A2UI: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
