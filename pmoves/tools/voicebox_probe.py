#!/usr/bin/env python3
"""Probe Voicebox OpenAPI spec and list TTS-related endpoints."""
import json
import sys
from pathlib import Path


def main() -> int:
    """Load and summarize Voicebox OpenAPI spec."""
    spec_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("voicebox_openapi_spec.json")
    if not spec_path.exists():
        print(f"Not found: {spec_path}")
        return 1

    with open(spec_path) as f:
        spec = json.load(f)

    paths = spec.get("paths", {})
    print(f"Voicebox API endpoints: {len(paths)}")
    tts_filter = ("tts", "voice", "synth", "clone", "speaker", "backend", "gen", "audio", "project")
    tts_paths = [p for p in paths if any(x in p for x in tts_filter)]
    print(f"\nTTS/voice endpoints ({len(tts_paths)}):")
    for p in sorted(tts_paths):
        methods = sorted(m.upper() for m in paths[p] if m in ("get", "post", "put", "delete", "patch"))
        print(f"  {','.join(methods):10s} {p}")

    # Also print tags to understand grouping
    tags = set()
    for p_def in paths.values():
        for m_def in p_def.values():
            if isinstance(m_def, dict):
                for tag in m_def.get("tags", []):
                    tags.add(tag)
    if tags:
        print(f"\nTags: {sorted(tags)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
