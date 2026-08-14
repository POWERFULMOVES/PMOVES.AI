# yt-research-lane

Ingest the PMOVES YouTube corpus (channel-monitor surfaced + operator playlist)
into transcripts, extract the **anchor / receipt references** surrounding the
economic-identity + missing-link work, and emit a structured research doc that
feeds the **(b) decision spec** (see [[project_ship_missing_link]]). This is a
RESEARCH lane — it produces a doc, it does NOT build anything for Fordham.

## Arguments

- `source` (enum, required): `channel-monitor` | `playlist` | `both` (default `both`)
  — `channel-monitor` = pull the video set the running PMOVES.YT channel monitor
  has already surfaced; `playlist` = an explicit playlist/URL list from the operator.
- `playlist_url` (string, optional): playlist URL or newline-separated video links
  when `source` includes `playlist`. If absent and `source=playlist`, STOP and ask.
- `since` (string, optional): only videos published on/after this ISO date (default: all).
- `out_dir` (string, optional): research output root
  (default `pmoves/docs/research/yt-corpus/`).

## Implementation

Runs on the node that hosts **PMOVES.YT** (env.tier-worker) — that's where
`yt_dlp`, the channel monitor, and the compose service live. Do NOT run the batch
from the 4090/OneDrive tree (slow + env-guard friction).

1. **Resolve the video set.**
   - `channel-monitor`: read the monitor's surfaced-video list (PMOVES.YT
     `pmoves_yt_service` runtime / `docker-compose.pmoves.yml` service). Confirm
     the monitor is up before pulling.
   - `playlist`: expand `playlist_url` with `yt-dlp --flat-playlist -J` to video IDs.
2. **Transcribe each video** via the `transcribe-and-fetch` path (handles the
   videos that are NOT web-fetchable, incl. the still-un-ingested `uHl0P2Jy16I`).
   Prefer existing captions; fall back to Whisper. Write `<id>.transcript.txt` +
   `<id>.meta.json` (title, url, published, description-links) under `out_dir`.
3. **Extract anchors/receipts.** For each transcript, pull the passages where the
   operator references concrete data/work (the "wax-poetic → map to actual data"
   seam): quote + timestamp + the referenced artifact (repo, PR, doc, dataset).
   This is the CHIT deterministic-anchor material — semantic-match candidates, not
   a verdict.
4. **Emit** `out_dir/YT_RESEARCH_INDEX.md`: per-video row (title, url, date,
   anchor-count) + a consolidated anchor table (claim ↔ referenced artifact ↔
   confidence). Flag anything that reads like a **stake/attribution or payout**
   claim for the (b) decision-spec reviewers.
5. **Do NOT** publish, comment, or post anything to YouTube — read/transcribe only.

## Related

- `PMOVES.YT/` — yt-dlp fork + `pmoves_yt_service` (channel monitor host, env.tier-worker)
- `PMOVES-transcribe-and-fetch/` — transcription path for non-fetchable videos
- [[project_ship_missing_link]] — the (b) decision this research feeds; `uHl0P2Jy16I` ref
- [[project_youtube_commenter_bot]] — the channel/YouTube-monitor lane (parked)
- `pmoves/docs/research/yt-corpus/` — output root

## Notes

- Privacy: transcripts + anchor tables stay **LOCAL / private** (research inputs
  for the design), same class as the SHIP_READINESS assessment — not public main.
- The anchor extraction is the **deterministic-grounding half** (tool grounds,
  model judges) — surface candidate matches with citations; humans/counsel judge.
- Legal/tax verification of any receipt is NOT this lane — that routes to
  PMOVES-Mike + the Melchor/Hermes-awaken node.
- Batch runs where the data lives; the 4090 lane only consumes the finished index.
