# `pmoves/tools/test_all_tts_engines` — TTS engine test harness

> **Lane 4 redo (2026-08-01)** — refactored to use Pinokio's `pterm` CLI primitives
> + a gepeto-style launcher, with per-engine review READMEs. The hand-rolled
> `_resolve_pterm` / `_run_pterm` / `_parse_pterm_status` / `pterm_preflight`
> subprocess wrappers are gone; we now call real pterm subcommands
> (`list`, `status`, `start`, `running`, `push`, `clipboard`) and let pterm's
> own JSON output do the talking.

## What this lane ships

| Artifact | Path | Purpose |
|---|---|---|
| **Test runner** | `pmoves/tools/test_all_tts_engines.py` | Drives all 14 engines via `gradio_client` |
| **14 per-engine review READMEs** | `pmoves/tools/test_all_tts_engines/engines/*.md` | Per-engine contract: kwargs, voices, hardware, failure modes |
| **Gepeto launcher** | `pmoves/tools/test_all_tts_engines/pinokio/` | 1-click Pinokio UI for the harness |
| **TAC rail 6** | `pmoves/configs/tac_trees/voice-engines-integration.tac.yaml` | "GRADIO MCP contract" — codifies test+implement protocol |

## How to actually test (the no-guess recipe)

### Quick: from a host with the harness on it

```powershell
# From the worktree root (or any checkout of main)
python pmoves/tools/test_all_tts_engines.py
```

The harness auto-resolves TTS Studio: if `pterm` is on PATH, it asks pterm to
start Ultimate-TTS-Studio and waits for readiness via `pterm running`. If pterm
isn't available, it falls back to direct connection at `http://127.0.0.1:7860/`
(the Pinokio app's default port per the curated YAML).

### Per-engine: target one

```powershell
python pmoves/tools/test_all_tts_engines.py --engine kitten_tts
python pmoves/tools/test_all_tts_engines.py --engine fish_s2
python pmoves/tools/test_all_tts_engines.py --engine vibevoice --load-only
```

### From the gepeto launcher (1-click)

If Pinokio is installed and the launcher is registered:

```powershell
# Install the launcher (idempotent)
pterm start "pmoves\tools\test_all_tts_engines\pinokio\install.js"

# Run all 14 engines
pterm start "pmoves\tools\test_all_tts_engines\pinokio\start.js"

# Or run a single engine — Pinokio UI prompts for which one
pterm start "pmoves\tools\test_all_tts_engines\pinokio\start-one.js"
```

When the run finishes the launcher:
1. `pterm push "TTS test complete: 13/14 pass" --title "PMOVES"` — desktop notification
2. `pterm clipboard write <summary.md>` — the run summary is on the clipboard
3. Returns a non-zero exit code if any engine failed (Pinokio UI shows red)

### Direct gradio_client (debugging a specific engine)

For deep dives, every per-engine README has a copy-paste gradio_client recipe
that mirrors exactly what the harness does internally. See e.g.
`engines/kitten_tts.md`, `engines/fish_s2.md`, `engines/vibevoice.md`.

## Why pterm + gepeto (and not hand-rolled)

The original `_resolve_pterm` / `_run_pterm` / `_parse_pterm_status` /
`pterm_preflight` was a 180-line hand-rolled wrapper that:
- Called `pterm search "ultimate tts"` — **a subcommand that does not exist**
- Called `pterm run <id>` — **also fake**
- Had a 50-line fallback parser that tried JSON → key=value → colon-separated
  text, because the author wasn't sure what pterm would return

The refactor follows the wrap-don't-reinvent rule from `pmoves/AGENTS.md`:

| Old (hand-rolled) | New (pterm primitive) |
|---|---|
| `_resolve_pterm()` (3-platform candidate list) | `shutil.which("pterm")` — same logic pterm itself uses |
| `_run_pterm(["search", ...])` | `pterm list` — the real discovery subcommand |
| `_parse_pterm_status()` (50 lines, JSON→kv→text) | `json.loads(result.stdout)` — pterm outputs JSON for `status` |
| `_run_pterm(["run", ...])` + 180s polling loop | `pterm start <id>` (daemon) + `pterm running <id>` (truthful polling) |
| (none) | `pterm push "msg" --title "..."` for completion notification |
| (none) | `pterm clipboard write <summary>` for result sharing |

Net effect: 180 lines of fragile wrapper → ~30 lines of pterm calls, plus
the gepeto launcher that gives a 1-click UX layer on top.

## Architecture (how the pieces fit)

```
                   ┌──────────────────────────────┐
                   │  PMOVES Operator (or agent)  │
                   └──────────────┬───────────────┘
                                  │ "test all 14 engines"
                                  ▼
                ┌────────────────────────────────────┐
                │ gepeto launcher (pinokio/)        │
                │   start.js → runs harness         │
                │   install.js → uv pip install     │
                │   pinokio.js → UI menu            │
                │   pinokio.json → metadata         │
                └────────────────┬───────────────────┘
                                 │
                                 │  python pmoves/tools/test_all_tts_engines.py
                                 ▼
       ┌────────────────────────────────────────────────────┐
       │ test_all_tts_engines.py (the harness)              │
       │  ┌────────────────────────────────────────────┐    │
       │  │ pterm pre-flight:                          │    │
       │  │   1. pterm list            → find app      │    │
       │  │   2. pterm status <app>    → ready?        │    │
       │  │   3. pterm start <app>     → boot it       │    │
       │  │   4. pterm running <app>  → poll ready    │    │
       │  └────────────────────────────────────────────┘    │
       │  ┌────────────────────────────────────────────┐    │
       │  │ gradio_client per engine:                  │    │
       │  │   for engine in ENGINES:                    │    │
       │  │     client.predict(setup_api?)             │    │
       │  │     client.predict(load_api, **kwargs)     │    │
       │  │     client.predict(/generate_unified_tts)  │    │
       │  │     client.predict(unload_api)             │    │
       │  │     validate_wav() + copy                  │    │
       │  └────────────────────────────────────────────┘    │
       │  ┌────────────────────────────────────────────┐    │
       │  │ notify:                                    │    │
       │  │   pterm push "13/14 pass" --title "PMOVES" │    │
       │  │   pterm clipboard write <summary.md>       │    │
       │  └────────────────────────────────────────────┘    │
       └────────────────────────┬───────────────────────────┘
                                │ gradio_client SSE over HTTP
                                ▼
                ┌────────────────────────────────────┐
                │ Ultimate-TTS-Studio (Gradio app)   │
                │ 14 engines exposed as /api routes  │
                │ https://ultimate-tts-studio.pmoves │
                └────────────────────────────────────┘
```

## Per-engine review READMEs

Every engine has a dedicated review README. Each one captures the contract an
implementer or reviewer needs to know without re-reading `launch.py`:

- **Upstream attribution** — where the engine comes from, license, paper/repo
- **`gradio_client` test recipe** — copy-pasteable 5-line script
- **Canonical synth kwargs** — exact values from `test_all_tts_engines.py` (single source of truth)
- **Voice list** — the `*_VOICES` registry in `flute-gateway/providers/ultimate_tts.py`
- **Hardware requirements** — VRAM, latency, CUDA/CPU, setup_api prerequisites
- **Reviewer checklist** — concrete yes/no items a reviewer can tick
- **Common failure modes** — symptom / cause / fix table
- **File locations** — the 4 files an implementer will touch
- **Reviewer notes** — free-form field for things learned during review

| Engine | README |
|---|---|
| KittenTTS | `engines/kitten_tts.md` |
| Kokoro TTS | `engines/kokoro.md` |
| F5-TTS | `engines/f5_tts.md` |
| IndexTTS | `engines/indextts.md` |
| IndexTTS2 | `engines/indextts2.md` |
| Fish Speech S1 | `engines/fish.md` |
| Fish Speech S2 Pro | `engines/fish_s2.md` |
| ChatterboxTTS | `engines/chatterbox.md` |
| Chatterbox Turbo | `engines/chatterbox_turbo.md` |
| Chatterbox Multilingual | `engines/chatterbox_multilingual.md` |
| VoxCPM | `engines/voxcpm.md` |
| Higgs Audio | `engines/higgs.md` |
| Qwen Voice Design | `engines/qwen.md` |
| VibeVoice | `engines/vibevoice.md` |

## TAC rail 6 — GRADIO MCP contract

The test+implement protocol is codified in
`pmoves/configs/tac_trees/voice-engines-integration.tac.yaml` as a new rail
("vei.gradio-mcp"). It asserts:

1. The gradio_client end-to-end path works (no mocks)
2. Per-engine review READMEs exist in `engines/` for all 14 engines
3. The gepeto launcher (pinokio/) is present and self-contained
4. The harness itself uses real pterm subcommands (not hand-rolled wrappers)
5. A repo-level README documents the lane

A reviewer can run `make -C pmoves tac-check vei.gradio-mcp` and the rail
returns the same status across CI, the operator's host, and a fresh local
clone — the no-guess guarantee.

## Related

- `pmoves/tools/test_all_tts_engines.py` — the test runner
- `pmoves/tools/test_all_tts_engines/pinokio/` — the gepeto launcher
- `pmoves/configs/tac_trees/voice-engines-integration.tac.yaml` — rail 6
- `pmoves/services/flute-gateway/providers/ultimate_tts.py` — the Flute provider
- `pmoves/configs/pinokio-apps/curated/ultimate-tts-studio.yaml` — the Pinokio app manifest
- `pmoves/docs/voice/VOICE_ENGINES_INTEGRATION.md` — the no-guess framework doc
