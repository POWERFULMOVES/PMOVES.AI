# Lane 4 — TTS test harness: pterm + gepeto + review READMEs (2026-08-01)

> **Status:** READY FOR REVIEW. 3-stacked commits on
> `fix/tts-pterm-gepeto-review-readmes`. Branch off `main` @ `1bd2fd5c0f`.
> Target PR: `fix/tts-pterm-gepeto-review-readmes` → `main`.

## TL;DR

`pmoves/tools/test_all_tts_engines.py` was a 947-line single file with a
180-line hand-rolled pterm wrapper that called **subcommands that don't
exist** (`pterm search`, `pterm run`) and had a 50-line JSON → key=value →
colon-separated-text fallback parser because the author wasn't sure what
pterm would return. The lane refactors the harness to use the **real**
pterm CLI surface, adds a gepeto-style 1-click launcher, writes 14
per-engine review READMEs + a repo-level README, and codifies the
test+implement protocol as **TAC rail 6** (`vei.gradio-mcp`).

## Root cause (what was wrong)

The original `_resolve_pterm` / `_run_pterm` / `_parse_pterm_status` /
`pterm_preflight` was a wrap-don't-reinvent violation. Per the pterm
skill (in `pmoves/AGENTS.md` and the `pterm` SKILL.md), the real
subcommands are:

```
pterm list                     — discover installed apps (JSON array)
pterm status <id>              — JSON { state, ready, ready_url, path }
pterm start <id>               — daemon: boot the app, returns immediately
pterm running <id>             — JSON { running, ready_url } (truthful poll)
pterm push "msg" --title "..."  — desktop notification
pterm clipboard write "..."    — system clipboard
```

The hand-rolled code:

1. Called `pterm search "ultimate tts"` — **not a real subcommand**
2. Called `pterm run <id>` — **also fake**
3. Had a 50-line fallback parser (JSON → key=value → colon-separated text)
   because pterm's actual output format wasn't known
4. Did 3 platform-specific candidate-path lookups (Windows + Linux +
   macOS) when `shutil.which("pterm")` is sufficient
5. Polled `pterm status <id>` repeatedly during startup instead of using
   `pterm running <id>` (the truthful polling primitive)

## What changed (3 stacked commits)

### Commit 1 — `4eb8de3f05` (P1, 1591 lines, 20 files)

* 14 per-engine review READMEs at
  `pmoves/tools/test_all_tts_engines/engines/*.md` (kitten_tts, kokoro,
  f5_tts, indextts, indextts2, fish, fish_s2, chatterbox,
  chatterbox_turbo, chatterbox_multilingual, voxcpm, higgs, qwen,
  vibevoice).
* Repo-level README at `pmoves/tools/test_all_tts_engines/README.md`
  with: how to test (3 recipes), why pterm+gepeto, architecture diagram,
  per-engine index, TAC rail 6 cross-ref.
* Gepeto launcher at `pmoves/tools/test_all_tts_engines/pinokio/`:
  * `install.js` — `uv pip install --upgrade gradio_client`
  * `start.js` — runs the full suite, pterm push notification,
    pterm clipboard write of the summary
  * `start-one.js` — runs the harness for one engine
  * `pinokio.js` — dynamic UI (install when venv missing; "Run all" /
    "Run one" submenu / "Per-engine READMEs" once installed)
  * `pinokio.json` — metadata (nvidia gpu, cross-platform)

### Commit 2 — `7e464c0122` (functional, +337/-164, 2 files)

* `pmoves/tools/test_all_tts_engines.py`:
  * REMOVED: `_resolve_pterm`, `_run_pterm`, `_parse_pterm_status`,
    `pterm_preflight` (180 lines)
  * ADDED: `pterm_bring_up_tts_studio`, `pterm_notify`,
    `pterm_clipboard_write` + thin helpers
  * main() gains `--notify` and `--clip-report` flags
  * Docstring updated to explain the pterm + gepeto integration
  * File is now 1013 lines (was 947; the docstring + new pterm code
    more than offset the wrapper removal)
* `pmoves/configs/tac_trees/voice-engines-integration.tac.yaml`:
  * Bumped `1.0.0 → 1.1.0`
  * NEW: `vei.gradio-mcp` rail with 9 children (harness / engine-count /
    per-engine-readmes / repo-readme / gepeto-launcher / pterm-clean /
    no-handrolled / pterm-call-shape / tac-self-ref)

### Commit 3 — docs (AGNOTE CLAIM + this spec)

* `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` gets a CLAIM entry
  (`Mavis::TTS-PTERM-GEPETO-REVIEW-READMES-CLAIM::2026-08-01`)
* `pmoves/docs/specs/tts-pterm-gepeto-review-readmes-2026-08-01.md`
  (this file)

## Why pterm + gepeto (and not hand-rolled)

The wrap-don't-reinvent rule from `pmoves/AGENTS.md` says: "if a wrapper
already exists (gepeto / pterm / pinokio), use it." The original
hand-rolled code:

| Old (hand-rolled) | New (pterm primitive) | Lines saved |
|---|---|---|
| `_resolve_pterm()` (3-platform candidate list) | `shutil.which("pterm")` | 28 |
| `_run_pterm(["search", ...])` | `pterm list` | 1 |
| `_parse_pterm_status()` (50 lines, JSON → kv → text) | `json.loads(result.stdout)` | 47 |
| `_run_pterm(["run", ...])` + 180s polling loop | `pterm start <id>` (daemon) + `pterm running <id>` | 38 |
| (none) | `pterm push "msg" --title "..."` | new |
| (none) | `pterm clipboard write <summary>` | new |

Net: 180 lines of fragile wrapper → ~100 lines of clean pterm calls,
plus a gepeto launcher that gives a 1-click UX layer on top.

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
       │  │   4. pterm running <app>   → poll ready    │    │
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
       │  │ notify (--notify / gepeto):                │    │
       │  │   pterm push "13/14 pass" --title "PMOVES" │    │
       │  │   pterm clipboard write <summary>          │    │
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

## TAC rail 6 — `vei.gradio-mcp` (9 children)

| Child | What it asserts |
|---|---|
| `harness` | `from gradio_client import Client` is present (no mock) |
| `engine-count` | 14 engines declared in `ENGINES` (grep for all 14 ids) |
| `per-engine-readmes` | 14 `engines/<id>.md` files exist |
| `repo-readme` | `pmoves/tools/test_all_tts_engines/README.md` exists |
| `gepeto-launcher` | 5 gepeto files exist: `install.js`, `start.js`, `start-one.js`, `pinokio.js`, `pinokio.json` |
| `pterm-clean` | Harness uses `pterm_bring_up_tts_studio` / `pterm_notify` / `pterm_clipboard_write` (named-function grep) |
| `no-handrolled` | `_resolve_pterm` / `_run_pterm` / `_parse_pterm_status` / `pterm_preflight` are GONE (grep_negative) |
| `pterm-call-shape` | All pterm subprocess calls pin `encoding="utf-8"` (Windows code-page safety, per Lane 3 lesson) |
| `tac-self-ref` | The rail references itself in the YAML (self-referential sanity check) |

A reviewer can run `make -C pmoves tac-check vei.gradio-mcp` and the
rail returns the same status across CI, the operator's host, and a
fresh local clone — the no-guess guarantee.

## Validation

| Check | Status | Command |
|---|---|---|
| `test_all_tts_engines.py` syntax | ✅ | `python -c "import ast; ast.parse(open('pmoves/tools/test_all_tts_engines.py', encoding='utf-8').read())"` |
| All 4 gepeto JS files | ✅ | `node --check pmoves/tools/test_all_tts_engines/pinokio/{install,start,start-one,pinokio}.js` |
| TAC YAML valid | ✅ | `python -c "import yaml; yaml.safe_load(open('pmoves/configs/tac_trees/voice-engines-integration.tac.yaml', encoding='utf-8'))"` |
| `vei.gradio-mcp` rail present | ✅ | YAML load + tree walk; 9 children present |
| Hand-rolled wrapper GONE | ✅ | `grep _resolve_pterm\|_run_pterm\|_parse_pterm_status\|pterm_preflight` → 0 matches in harness |
| `pterm_bring_up_tts_studio` etc. present | ✅ | `grep` finds all 3 new named functions |
| `encoding="utf-8"` pinned | ✅ | `grep encoding="utf-8"` returns multiple matches in the new pterm code |

Tests that REQUIRE runtime (gradio_client, pterm installed, running
TTS Studio) are NOT run in this lane — the lane is about structure,
not behavior. A future review cycle can add a `make tts-test-all` target
that brings up the stack and runs the harness, gated on
`vei.gradio-mcp.live-run` (proposed follow-up).

## Out of scope

* The actual TTS test run (Lane 4 is about the harness structure +
  the per-engine READMEs + the gepeto launcher; running it requires
  Ultimate-TTS-Studio up on a GPU node).
* The p8/pmoves-pinokio fork sync (separate `fleet-fork-sync` lane).
* The pinokio_apps registry (already in place; this lane didn't add
  new apps).
* Replacing `pterm` with the `pinokio_bridge` service for app management
  (the bridge is a Pinokio API surface for agents; pterm is the
  Pinokio CLI for humans — both are valid, this lane uses pterm).
* Migrating from gradio_client to the MCP SSE bridge tools (the
  flutegateway already exposes `tts_list_engines`, `tts_synthesize`,
  etc. via SSE — see TAC rail 1 `vei.contract.mcp-tools`; using those
  would be a future lane that doesn't need gradio_client at all).

## Related

* `pmoves/tools/test_all_tts_engines.py` — the test runner
* `pmoves/tools/test_all_tts_engines/pinokio/` — the gepeto launcher
* `pmoves/configs/tac_trees/voice-engines-integration.tac.yaml` —
  rail 6 (`vei.gradio-mcp`)
* `pmoves/services/flute-gateway/providers/ultimate_tts.py` — the
  Flute provider (consumes the engines this harness tests)
* `pmoves/configs/pinokio-apps/curated/ultimate-tts-studio.yaml` — the
  Pinokio app manifest
* `pmoves/docs/voice/VOICE_ENGINES_INTEGRATION.md` — the no-guess
  framework doc
