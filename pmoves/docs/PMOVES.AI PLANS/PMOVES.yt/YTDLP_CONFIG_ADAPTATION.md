# PMOVES.YT — Adapting external yt-dlp configs

Last updated: 2025-11-10

This note explains how to reuse the helper configs and scripts under `pmoves/docs/PMOVES.AI PLANS/PMOVES.yt/yt-dlp-config/` with the `pmoves-yt` service. The goal is to keep your familiar yt‑dlp flags while flowing downloads through PMOVES.YT so artifacts land in object storage, Supabase rows are written, and events are emitted for downstream automation.

## Quick Start

1) Generate `yt_options` JSON from a classic `config.txt`:

```
python pmoves/services/pmoves-yt/tools/ytdlp_config_to_options.py \
  "pmoves/docs/PMOVES.AI PLANS/PMOVES.yt/yt-dlp-config/config.txt" \
  > /tmp/yt_options.json
```

2) Use the `yt_options` in an API call to pmoves-yt (container default `http://localhost:8091` when `make -C pmoves up-yt` is running):

```
curl -sS -X POST http://localhost:8091/yt/download \
  -H 'content-type: application/json' \
  -d @/tmp/yt_options.json | jq .
```

Replace the scaffolded `url`, `namespace`, and `bucket` fields in the JSON as needed.

## What’s mapped

The converter maps a conservative subset of flags into `yt_options` keys that `pmoves-yt` understands:

- Format: `-f/--format` → `format`; `--merge-output-format` → `merge_output_format`
- Sort: `-S/--format-sort` → `formatsort`
- Subtitles: `--sub-langs` → `subtitle_langs[]`; `--write-auto-subs` → `subtitle_auto`
- SponsorBlock: `--sponsorblock-remove` → `sponsorblock_remove[]`; `--sponsorblock-mark` → `sponsorblock_mark[]`
- Archive & pacing: `--download-archive` (+ enables `use_download_archive`), `--retries`, `--fragment-retries`, `--socket-timeout`, `--sleep-interval`, `--max-sleep-interval`, `--limit-rate`
- Cookies: `--cookies` → `cookiefile`; `--cookies-from-browser` → `cookiesfrombrowser`
- Embedding: `--embed-metadata`, `--embed-thumbnail` add postprocessors (`FFmpegMetadata`, `EmbedThumbnail`).
- Safe toggles: `--keep-video`, `--continue`, `--no-windows-filenames`, `--restrict-filenames`

Unknown flags are ignored by design; you can pass additional keys directly via `yt_options` in the API body if needed.

## Path caveat (Windows)

Classic configs often use drive paths in `-o/--paths` (e.g., `E:/Downloads/...`). PMOVES.YT stores outputs in object storage; local file paths are neither required nor recommended in container runs. The converter omits output templates by default. If you really need them for a workstation-only run, pass `--include-output-template` to emit an `outtmpl` key and ensure the path exists in the container.

## Channel Monitor integration

When using the Channel Monitor, you can attach per-channel `yt_options` in the JSON config so SABR workarounds, subtitles, or archives are tuned per source. Example snippet:

```json
{
  "channels": [
    {
      "url": "https://www.youtube.com/@SomeChannel",
      "namespace": "pmoves",
      "yt_options": {
        "format": "best[height<=1080]+bestaudio/best",
        "subtitle_langs": ["en", "en.*"],
        "use_download_archive": true,
        "download_archive": "/data/yt-dlp/SomeChannel-archive.txt",
        "postprocessors": [{"key": "FFmpegMetadata"}, {"key": "EmbedThumbnail"}]
      }
    }
  ]
}
```

## Why this approach

- Keeps your curated yt‑dlp behavior while leveraging PMOVES orchestration (S3 upload, Supabase rows, events).
- `pmoves-yt` already supports a rich `yt_options` passthrough; this adapter simply bridges familiar config files to that JSON.
- Safer defaults: the service will still apply SABR-aware fallbacks (Invidious/companion, po_token) when yt‑dlp errors match known patterns.

## Next steps

- Expand the converter to cover more flags as they prove useful.
- Add a `make yt-options-from-config` helper and a small end‑to‑end smoke (`make yt-smoke`) that posts to `/yt/download` with generated options.
```

