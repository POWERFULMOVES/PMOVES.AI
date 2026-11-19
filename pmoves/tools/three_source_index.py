#!/usr/bin/env python3
"""Build the 3-source reconciliation index: playlist videos x 82 beats x models.

Sources (per the ROADMAP_4LANE_RESEARCH_DRYRUN 3-source plan, twin verdict d):
  1. Videos  — yt-dlp --flat-playlist JSON of the DARKXSIDE AI playlist
               (the /yt/playlist API hangs at ~2.4k scale; flat listing does not).
  2. Beats   — pmoves/data/beats/playlists/groups_summary.json (82 SoundCloud
               tracks grouped by tempo/timbre clusters).
  3. Models  — live `ollama list` (passed via --ollama-list file or stdin) plus
               static registry rows when Supabase is unreachable.

Output: pmoves/data/research/three_source_index.json — the join substrate for
the model x beat x video capability matrix and the remix graph. The artifact
is committed so a fresh clone inherits the crawl without re-auth (the OAuth
refresh token was measured revoked 2026-11-19; flat listing needs only the
cookie vault).

Usage:
    yt-dlp --flat-playlist -J <playlist_url> > playlist.json
    ollama list > ollama.txt
    python3 pmoves/tools/three_source_index.py \
        --playlist playlist.json --ollama-list ollama.txt \
        --out pmoves/data/research/three_source_index.json
"""

import argparse
import gzip
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GROUPS_SUMMARY = REPO_ROOT / "pmoves/data/beats/playlists/groups_summary.json"

# Lane 3 filter: provisioning-script videos are the actionable subset for the
# Jetson combiner update lane (firmware/compose diffs come from these).
PROVISIONING_RE = re.compile(
    r"\b(jetson|jetpack|orin|reflash|provision|flash|sdk.?manager|docker|compose|install|setup)\b",
    re.IGNORECASE,
)


def load_playlist(path: Path) -> list[dict]:
    data = json.loads(gzip.open(path).read() if path.suffix == ".gz" else path.read_text())
    entries = data.get("entries") or []
    out = []
    for e in entries:
        if not e or not e.get("id"):
            continue
        out.append(
            {
                "id": e["id"],
                "title": e.get("title") or "",
                "channel": e.get("channel") or e.get("uploader") or None,
                "duration_s": e.get("duration"),
                "url": f"https://www.youtube.com/watch?v={e['id']}",
            }
        )
    return out


def load_beats() -> list[dict]:
    groups = json.loads(GROUPS_SUMMARY.read_text())
    beats = []
    for g in groups:
        for track in g["tracks"]:
            beats.append({"track": track, "group": g["group"], "count_in_group": g["count"]})
    return beats


def load_models(ollama_list: str | None) -> list[dict]:
    models = []
    if ollama_list:  # narrows Optional for the loop below
        for line in ollama_list.splitlines():
            parts = line.split()
            if not parts or parts[0] == "NAME":
                continue
            models.append(
                {
                    "name": parts[0],
                    "size": parts[2] if len(parts) > 2 else None,
                    "host": "spark-ollama-local",
                }
            )
    # Approved cloud coding-plan lanes per MODEL_FABRIC_CONTRACT (static
    # declarations — capability rows, not runtime claims).
    models += [
        {"name": "glm-5.3", "host": "zai-coding-plan", "size": None},
        {"name": "glm-5.2", "host": "zai-coding-plan", "size": None},
        {"name": "minimax-m3", "host": "minimax-token-plan", "size": None},
    ]
    return models


def main() -> int:
    p = argparse.ArgumentParser(description=("three_source_index: build the videos x beats x models reconciliation index"))
    p.add_argument("--playlist", type=Path, required=True, help="yt-dlp --flat-playlist -J output (.json or .json.gz)")
    p.add_argument("--ollama-list", help="path to `ollama list` output (or '-' for stdin)")
    p.add_argument("--out", type=Path, default=REPO_ROOT / "pmoves/data/research/three_source_index.json")
    args = p.parse_args()

    videos = load_playlist(args.playlist)
    beats = load_beats()
    ollama_txt: str | None = None
    if args.ollama_list:
        src = sys.stdin.read() if args.ollama_list == "-" else Path(args.ollama_list).read_text()
        ollama_txt = src
    models = load_models(ollama_txt)

    provisioning = [v for v in videos if PROVISIONING_RE.search(v["title"] or "")]
    channels = Counter(v["channel"] or "(unknown)" for v in videos)

    index = {
        "schema": "three_source_index/v1",
        "generated": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "videos": {
                "playlist_title": "DARKXSIDE AI (PLGupOT04oMfok7S8W8Js7lZZIlhM8ufc8)",
                "count": len(videos),
                "top_channels": channels.most_common(20),
                "provisioning_candidates": provisioning,
            },
            "beats": {"origin": "soundcloud/darkxside 82-track set", "count": len(beats), "tracks": beats},
            "models": {"count": len(models), "entries": models},
        },
        "notes": [
            "OAuth refresh token measured revoked 2026-11-19 (invalid_grant); Supabase playlist",
            "upsert via yt_playlist_crawl.py is blocked until operator re-runs the OAuth flow.",
            "Flat listing requires only the cookie vault; re-crawl with yt-dlp --flat-playlist.",
            "Capability matrix (model x beat x video) derives from this index; see remix-graph",
            "plan in ROADMAP_4LANE_RESEARCH_DRYRUN Lane 3 / twin verdict (d).",
        ],
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(index, indent=1, ensure_ascii=False) + "\n")
    print(f"three_source_index: {len(videos)} videos ({len(provisioning)} provisioning candidates), "
          f"{len(beats)} beats, {len(models)} models -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
