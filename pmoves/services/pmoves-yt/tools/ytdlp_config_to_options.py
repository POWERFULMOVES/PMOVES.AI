#!/usr/bin/env python3
"""
Convert a classic yt-dlp config.txt into a pmoves-yt `yt_options` JSON blob.

Notes
- Only a safe, commonly used subset of flags is mapped.
- File-system output templates (`-o/--paths`) are omitted by default since
  pmoves-yt uploads to object storage; pass `--include-output-template` to emit.
- Unknown flags are ignored. This script is intentionally conservative.

Usage
  python ytdlp_config_to_options.py path/to/config.txt > yt_options.json
  python ytdlp_config_to_options.py --include-output-template config.txt | \
      curl -X POST http://localhost:8091/yt/download \
           -H 'content-type: application/json' \
           -d @-  # then add url/namespace/bucket fields manually or pipe through jq
"""
from __future__ import annotations

import argparse
import json
import re
import shlex
from pathlib import Path
from typing import Dict, Any, List


def _append_postprocessor(postprocessors: List[Dict[str, Any]], key: str) -> None:
    if not any(pp.get("key") == key for pp in postprocessors):
        postprocessors.append({"key": key})


def parse_config_lines(lines: List[str], include_output: bool = False) -> Dict[str, Any]:
    opts: Dict[str, Any] = {}
    postprocessors: List[Dict[str, Any]] = []

    # Helpers
    def set_if_not_none(k: str, v: Any) -> None:
        if v is not None:
            opts[k] = v

    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        # Allow "--paths name:value" style – keep whole line tokenization
        try:
            tokens = shlex.split(line)
        except ValueError:
            # Fallback: naive split if quoting is inconsistent
            tokens = line.split()
        if not tokens:
            continue

        flag = tokens[0]
        val = tokens[1] if len(tokens) > 1 else None

        # Core format/merge
        if flag in {"-f", "--format"} and val:
            opts["format"] = val
            continue
        if flag == "--merge-output-format" and val:
            opts["merge_output_format"] = val
            continue

        # Subtitles
        if flag in {"--sub-langs", "--sub-languages"} and val:
            langs = [p.strip() for p in val.split(",") if p.strip()]
            set_if_not_none("subtitle_langs", langs)
            continue
        if flag == "--write-auto-subs":
            opts["subtitle_auto"] = True
            continue

        # SponsorBlock
        if flag == "--sponsorblock-remove" and val:
            remove = [p.strip() for p in val.split(",") if p.strip()]
            set_if_not_none("sponsorblock_remove", remove)
            continue
        if flag == "--sponsorblock-mark" and val:
            mark = [p.strip() for p in val.split(",") if p.strip()]
            set_if_not_none("sponsorblock_mark", mark)
            continue

        # Archive / retries / pacing
        if flag == "--download-archive" and val:
            opts["use_download_archive"] = True
            opts["download_archive"] = val
            continue
        if flag == "--retries" and val:
            opts["retries"] = int(val) if val.isdigit() else val
            continue
        if flag == "--fragment-retries" and val:
            opts["fragment_retries"] = int(val) if val.isdigit() else val
            continue
        if flag == "--socket-timeout" and val:
            opts["socket_timeout"] = float(val) if re.match(r"^\d+(\.\d+)?$", val) else val
            continue
        if flag == "--sleep-interval" and val:
            opts["sleep_interval"] = float(val) if re.match(r"^\d+(\.\d+)?$", val) else val
            continue
        if flag == "--max-sleep-interval" and val:
            opts["max_sleep_interval"] = float(val) if re.match(r"^\d+(\.\d+)?$", val) else val
            continue
        if flag == "--limit-rate" and val:
            opts["ratelimit"] = val
            continue

        # Cookies
        if flag == "--cookies" and val:
            opts["cookiefile"] = val
            continue
        if flag == "--cookies-from-browser" and val:
            opts["cookiesfrombrowser"] = val
            continue

        # Embedding and metadata
        if flag == "--embed-metadata":
            _append_postprocessor(postprocessors, "FFmpegMetadata")
            continue
        if flag == "--embed-thumbnail":
            _append_postprocessor(postprocessors, "EmbedThumbnail")
            continue

        # Output template (optional)
        if include_output and flag == "-o" and val:
            opts["outtmpl"] = val
            continue

        # Conservative passthrough toggles
        if flag in {"--keep-video", "--continue", "--no-windows-filenames", "--restrict-filenames"}:
            opts[flag.lstrip("-").replace("-", "_")] = True
            continue

        # Sorting preference (-S) can be forwarded directly
        if flag in {"-S", "--format-sort"} and val:
            opts["formatsort"] = val
            continue

        # Unknown flag: ignore by design

    if postprocessors:
        opts["postprocessors"] = postprocessors

    return opts


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("config", type=Path, help="Path to yt-dlp config.txt")
    ap.add_argument("--include-output-template", action="store_true", help="Include -o outtmpl mapping")
    args = ap.parse_args()

    text = args.config.read_text(encoding="utf-8")
    yt_options = parse_config_lines(text.splitlines(), include_output=args.include_output_template)

    # Emit a minimal example body for convenience
    body = {
        "url": "https://www.youtube.com/watch?v=BaW_jenozKc",
        "namespace": "pmoves",
        "bucket": "assets",
        "yt_options": yt_options,
    }
    print(json.dumps(body, indent=2))


if __name__ == "__main__":
    main()

