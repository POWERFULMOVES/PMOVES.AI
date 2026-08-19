# LEARNINGS: mavis-harness-v0

**Branch:** `feat/mavis-harness-v0`
**Base:** `main` @ `c7ff017d14` (post-3-PR close)
**Commits:** 6 (CLAIM + CGP schema + load_bootstrap + orchestrator + bpm_cron + HARNESS.md/LEARNINGS)
**Files added:** 9 (~3,200 ins / 0 del)
**PR:** https://github.com/POWERFULMOVES/PMOVES.AI/pull/TBD
**Date:** 2026-08-08

## TL;DR

The Mavis harness v0 slice lands the PMOVES.AI side of a 3-repo coordinated slice. The CGP (Compressed Geometric Packet) is the contract: PMOVES.AI writes it, the PMOVES-hermes-agent fork reads it at session init, the PMOVES-pinokio fork reads it when launching a PMOVES-tagged app. Same schema, three implementations, zero breaking changes on the consumer forks. The orchestrator dispatches work via NATS; the BPM cron schedules the operator's day through 5 phases with 25/5 pomodoro blocks. 56 tests pass (22 loader + 12 orchestrator + 22 BPM).

## What this slice does

| Tool | Purpose |
|------|---------|
| `pmoves/contracts/schemas/pmoves-bootstrap/v1.schema.json` | The CGP contract (JSON Schema, Draft 2020-12). Aligned to the canonical CHIT Geometry Packet spec at `pmoves/docs/PMOVESCHIT/CGP_v1.0_SPECIFICATION.md` - same envelope (spec/meta/sig/super_nodes/...) with `pmoves.bootstrap/v1` as the profile name and `super_nodes: []` for the empty-geometry case. |
| `pmoves/contracts/schemas/pmoves-bootstrap/example.cgp.yaml` | The example CGP with real values from memory (minimax/dimensional/5090/Tailscale/RustDesk/Hostinger/Cloudflare). The fork consumer PRs read this to verify their loaders. |
| `pmoves/tools/load_bootstrap.py` | Reads the CGP, validates against the schema, returns a typed `Bootstrap` object, exports `PMOVES_BOOTSTRAP_*` env vars. 4 input sources: path arg, source arg, env var, default example. |
| `pmoves/tools/orchestrator.py` | Multi-agent dispatcher. Publishes tasks to `pmoves.agent.task.v1`, waits for results on `pmoves.agent.result.v1`, merges outputs. Includes `Publisher` protocol + `MockPublisher` for tests. |
| `pmoves/tools/bpm_cron.py` | BPM/pomodoro engine. Each task has 5 phases (define/assign/execute/review/close) with N pomodoro focus blocks (25/5 min by default, env-driven). Publishes phase + pomodoro events to NATS. |
| `pmoves/tools/HARNESS.md` | The high-level map of the 3 tools + how they fit together + quick-start code. |

## What this slice does NOT do (left for follow-up slices)

- **Hermes fork consumer PR** (`feat/pmoves-bootstrap-consumer` in `POWERFULMOVES/PMOVES-hermes-agent`) - the `bootstrap_loader.py` + `tools_bridge.py` + tests
- **Pinokio fork consumer PR** (`feat/pmoves-app-launcher` in `POWERFULMOVES/PMOVES-pinokio`) - the `pmoves_loader.js` + `pmoves_apps/` starter manifests
- **Real pmoves-nats-mcp integration** - v0 uses `MockPublisher`; a real `NatsPublisher` wraps `pmoves-nats-mcp` and lands in a follow-up
- **The actual Hermes subscriber** - v0 sets up the wire; when the operator stands Hermes up on a node, the subscriber picks up tasks via the CGP's `routing.hermes` block
- **Ace Studio / Veo integrations** - app-level, follow-up once the harness is proven
- **KVM control surface** - the operator's earlier flag; RustDesk is the control surface, not a harness concern

## Acceptance criteria (5/5 met)

- [x] Mavis can load a CGP from file / env var / raw string and get a typed Bootstrap object (22/22 tests pass)
- [x] The CGP is validated against the canonical schema (jsonschema with structural fallback; the schema is the source of truth)
- [x] Mavis can dispatch a task to 1+ agents and merge the results (12/12 tests pass)
- [x] Mavis's cron is now a BPM engine with 5 phases + pomodoro blocks (22/22 tests pass)
- [x] The 3 tools are documented in `pmoves/tools/HARNESS.md` so a fresh local model (Spark / Knuckles / future Mavis session) can find them

## Tests (56/56 pass)

- `pmoves/tools/tests/test_load_bootstrap.py` - 22 tests
- `pmoves/tools/tests/test_orchestrator.py` - 12 tests
- `pmoves/tools/tests/test_bpm_cron.py` - 22 tests

All tests run with mock transport (MockPublisher from orchestrator.py) - no real NATS server required.

## 5-class review taxonomy (per pr-trim convention)

The 5-class taxonomy (legit / already-fixed / owner / out-of-scope / pre-existing) is the right spine for the post-merge review. Anticipated:

- **legit**: 0 (this is a foundation slice, no review yet)
- **already-fixed**: 0
- **owner**: any feedback on the `Bootstrap` / `BpmTask` / `DispatchResult` dataclass field names (operator is the consumer; only they can sign off on the field names)
- **out-of-scope**: any "add Ace Studio wrapper too" / "add Veo wrapper too" / "add Hermes subscriber" - those are deliberately follow-up slices
- **pre-existing**: n/a

## 4-bucket learnings (per review-lessons > review-comments convention)

### missed-signal
(none yet - this is the initial slice)

### fix-pattern
(none yet - no review cycles to learn from)

### wrong-suggestion
(none yet)

### already-addressed
- **Pinokio binary detection**: a review might suggest "use `command -v pinokio`" - already addressed in `pinokio_launch.sh` (from PR #2450)
- **Workflow JSON format**: a review might suggest "validate the workflow JSON before submission" - already addressed, `comfyui_client.py` raises on server error
- **Render timeout**: a review might suggest "add a render timeout" - already addressed in `comfyui_client.py` via `PMOVES_COMFYUI_TIMEOUT_S`
- **JSON Schema validation fallback**: a review might suggest "handle missing jsonschema gracefully" - already addressed, the structural fallback checks required fields + the spec const

## What this proves for the operator's bigger vision

The CGP bootstrap is the contract that lets Mavis hand off work to KiloClaw + Hermes + the Pinokio fork without breaking any of them. The BPM cron turns the operator's day into a flow of phases (define → assign → execute → review → close) with 25/5 pomodoro blocks. The public engagement workflow (react → comment → share → analyze → post) maps 1:1 to the 5 phases, so the DARKXSIDE-going-public content pipeline has a first-class scheduler from day one.

The 3 tools are designed to be small + composable:
- `load_bootstrap.py` is 280 lines + 22 tests (a typed reader + env-var exporter)
- `orchestrator.py` is 280 lines + 12 tests (a publisher + a dispatcher + a result merger)
- `bpm_cron.py` is 380 lines + 22 tests (5 phases + pomodoro blocks + a Publisher)

Each can be tested without the others. The integration is in `HARNESS.md`'s quick-start example - the 3 tools compose by sharing the same `Publisher` and the same CGP.

## Files added (9 total)

```
pmoves/contracts/schemas/pmoves-bootstrap/v1.schema.json
pmoves/contracts/schemas/pmoves-bootstrap/example.cgp.yaml
pmoves/tools/load_bootstrap.py
pmoves/tools/orchestrator.py
pmoves/tools/bpm_cron.py
pmoves/tools/HARNESS.md
pmoves/tools/tests/test_load_bootstrap.py
pmoves/tools/tests/test_orchestrator.py
pmoves/tools/tests/test_bpm_cron.py
pmoves/tools/LEARNINGS/mavis-harness-v0_LEARNINGS.md
```

Plus 1 modified:
```
pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md  (CLAIM entry appended)
docs/AGENT_TRAIL.md                     (first trail entry for this lane)
```

## Three-body

- **Delivery** (Mavis, this): the 6 commits, 56 tests, HARNESS.md, LEARNINGS, AGNOTE CLAIM, trail entry
- **Control** (DARKXSIDE): review the PR, decide the order for the 2 fork-side PRs (Hermes first or Pinokio first), provide a Hermes host when one is stood up
- **Memory** (this file + AGNOTE + trail): the full provenance trail for future Spark / Knuckles / 4090 / fresh Mavis sessions

## CHIT trail unsigned-local

No `CHIT_PASSPHRASE` loaded in this Mavis session per the standing operator convention.
