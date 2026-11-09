# LEARNINGS — mcpcli-wireup slice (model cascade wire-up + 4 context docs + find-skills + drift detector)

> Per the 4-bucket taxonomy (missed-signal / fix-pattern / wrong-suggestion / already-addressed).
> Captured during implementation, before any review. Add more buckets as review threads land.

## 1. The slice as a whole

**Goal:** wire the 3 NEW model-cascade submodules from PR #2589 of the 6-repo fold-in into the PMOVES harness v0. The operator flagged: "your minimax cli is installed since all the commands rules already there no need to hand roll just document and store" — so this slice is **docs + wire-up**, not a new CLI implementation.

**11 commits on `feat/mcpcli-wireup` (off `e4e3aabb7` = main @ 2026-08-17, post-fold-in-merge; fast-forwarded to `ad56c9ba3` after the operator's 12+ post-fold-in PRs landed):**

| # | SHA | What |
|---|-----|------|
| 1 | `e6621fe784` | feat(agent-registry): register PMOVES-MiniMax-MCP in registry + mcp.json + BOOTSTRAP.md |
| 2 | `05b8b0ee8b` | feat(cgp): add pmoves-minimax-mcp + services.minimax to bootstrap CGP profile |
| 3 | `1e8e14c2f5` | docs(verifier): add PROVIDER_VERIFIER_GATE.md — the conformance gate how-to |
| 4 | `ee062b1f0b` | docs(cli): add MMX_CLI_SURFACE.md — the 14 commands, the SDK surface, the boundary |
| 5 | `d7420b7512` | docs(skills): add PMOVES_SKILLS_REVIEW.md — the find-skills meta-skill review |
| 6 | `cf658217fe` | docs(agents-md): add AGENTS_MD_FORMAT_REVIEW.md — the open format vs our AGENTS.md |
| 7 | `ea712f44dc` | docs(cipher): store cipher context — encryption, keys, NATS custody, the 3 patterns |
| 8 | `bcf597514a` | docs(hirag): store HiRAG context — wired, pending, the 3 patterns, "NOT" boundary |
| 9 | `9527f920c0` | feat(registry): wire find-skills into cli_tools + skill-pairings |
| 10 | `f6cb315aca` | test(wireup): add 13 drift-detector tests (5 groups, all green) |
| 11 | `2e96cc78b7` | agnote: CLAIM+RELEASE row + (this) LEARNINGS file |

**Acceptance criteria status:**

| # | Criterion | Status |
|---|-----------|--------|
| 1 | `pmoves_minimax_mcp` registered in `agent_registry.yaml` mcp_servers | Done (commit 1) |
| 2 | `pmoves-minimax-mcp` registered in `.claude/mcp.json` | Done (commit 1) |
| 3 | BOOTSTRAP.md MCP Entrypoints table has the new row | Done (commit 1) |
| 4 | CGP `mcps` list has `pmoves-minimax-mcp` | Done (commit 2) |
| 5 | CGP `services.minimax` block names the 3 NEW submodules | Done (commit 2) |
| 6 | PROVIDER_VERIFIER_GATE.md exists (the how-to) | Done (commit 3) |
| 7 | MMX_CLI_SURFACE.md exists (the catalog) | Done (commit 4) |
| 8 | PMOVES_SKILLS_REVIEW.md exists (the review) | Done (commit 5) |
| 9 | AGENTS_MD_FORMAT_REVIEW.md exists (the format diff) | Done (commit 6) |
| 10 | `.claude/context/cipher.md` exists | Done (commit 7) |
| 11 | `.claude/context/hirag.md` exists | Done (commit 8) |
| 12 | `find-skills` + `cli-host-skills` in `skill_pairings.yaml` | Done (commit 9) |
| 13 | `skills` host CLI in `cli_tools.yaml` | Done (commit 9) |
| 14 | 13 drift-detector tests pass | Done (commit 10) |
| 15 | AGNOTE row appended | Done (commit 11) |
| 16 | JSON / YAML parses | Verified with `python -c "import yaml; yaml.safe_load(...)"` and `python -c "import json; json.load(...)"` |

**Out of scope (intentional, lives in other slices):**

- **CI gate for the verifier** — the CI follow-up to run `verify.py` on every PR is documented in `PROVIDER_VERIFIER_GATE.md` §"Gate in CI" but not wired. It's a separate slice.
- **v2 HiRAG gateway promotion** — the v2 is documented as "preferred" but legacy is deployed. The HiRAG context doc captures this as a follow-up.
- **`.claude/mcp.json` HiRAG registration** — the agent registry has `pmoves_hirag_mcp` (status: planned) but `.claude/mcp.json` doesn't have the server. Separate slice.
- **AGENTS.md content edits** (3 adoption items from the format review) — small content changes to `AGENTS.md` itself, not in this PR.
- **The 3 NEW submodules' actual `dist/` or built wheels** — the `mmx` CLI is consumed as-is from the installed npm package; the MCP server is run from the source via `uvx`; the verifier is a `python verify.py` invocation. No build artifacts in PMOVES.AI.

## 2. Patterns / fixes

### 2.1 "Why docs, not a new CLI" — the operator's "no need to hand roll" rule

**The trap:** with `Pmoves-minimax-cli` as a submodule and `minimax-cli` already in `cli_tools.yaml` `service_clis` (added by CRUSH lane #2599), the natural reflex is to write a `pmoves/tools/mini_cli.py` extension or a Python wrapper. That would be over-engineering.

**The decision:** the operator flag is explicit: "your minimax cli is installed since all the commands rules already there no need to hand roll just document and store." So the `mmx` CLI is consumed as-is. The PMOVES-side work is: register the MCP server (so tool-aware agents find it), document the CLI surface (so sidecar apps know the commands), and add the verifier doc (so the gate is useable).

**Rule of thumb:** when an external tool/submodule is already installed and the operator has explicitly said "don't hand-roll", the PMOVES-side work is **wire-up + documentation**, not new code. New code is the trap; documents that point at the existing tool are the right answer.

### 2.2 The 5-surface wire-up pattern (when an MCP server enters the harness)

**The convention:** when a new MCP server lands as a submodule, it gets registered in 5 places. If any of the 5 is missing, the harness v0 has a gap.

  - `pmoves/config/agent_registry.yaml` → `mcp_servers.<key>` (the discovery plane, the registry, the grounding-source flag if it's a cold-start surface)
  - `.claude/mcp.json` → `mcpServers.<name>` (the runtime config, the actual MCP server Claude Code calls)
  - `.claude/BOOTSTRAP.md` → MCP Entrypoints table (the cold-start doc, the human-readable listing)
  - `pmoves/contracts/schemas/pmoves-bootstrap/example.cgp.yaml` → `mcps` list (the CGP bootstrap, so consumer forks inherit the server)
  - `pmoves/contracts/schemas/pmoves-bootstrap/example.cgp.yaml` → `services.<name>` (the CGP service block, with the 3 submodules named by canonical path if it's a tier)

The harness v0 follow-ups (PR #2568) registered the SKILL surface in `pmoves/configs/submodule_skill_registry.json` — that's the 6th surface, but it's the *consumption* side, not the *provisioning* side. The 5 provisioning surfaces above are what makes the server actually start.

**Rule of thumb:** when a new MCP server enters the harness, expect 5 file edits + 1 test file. If you're tempted to do fewer, you're probably skipping a surface and the gap will bite later.

### 2.3 The transport field is not "always SSE"

**The trap:** every existing `mcp_servers` entry in `agent_registry.yaml` is `transport: "sse"` (cipher, e2b, hirag, nats, tailscale, voice). The new PMOVES-MiniMax-MCP server is `transport: "stdio"` (the upstream design). If I'd copied the existing pattern, I'd have written SSE and pointed at a non-existent HTTP endpoint.

**The right answer:** the transport field is **whatever the upstream server actually speaks**, not what the other entries happen to use. The stdio entry uses `command` + `args` + `env` instead of `endpoint`. Both shapes are valid; the schema is `additionalProperties: true` so neither fails validation.

**Rule of thumb:** for stdio MCP servers, the agent_registry entry has `command` (the executable, e.g. `uvx`), `args` (the launch args, e.g. `["minimax-mcp"]`), and `env` (the env vars with `${VAR}` placeholders for the pipeline to fill). The `endpoint` field is SSE-only.

### 2.4 "Grounding source" is a recipe, not a label

**The trap:** the existing entries with `grounding_source: true` (cipher, hirag) read like a feature flag — "yes, this is a grounding source." But that's not what it does. The flag is consumed by the discovery plane: when a cold-start agent loads the bootstrap, it fetches startup grounding from every server with `grounding_source: true`. Without the flag, a cold-start agent won't auto-load the surface.

**The right answer:** the new PMOVES-MiniMax-MCP entry has `grounding_source: true` because **the model surface is a load-bearing part of any Mavis-class agent's cold start** (Mavis needs to know what models are available before planning work that uses them). The other entries with the flag (cipher for memory, hirag for retrieval) follow the same logic: the agent needs this surface on cold start to do its job.

**Rule of thumb:** if a server's surface is something a cold-start agent needs *before* it can plan (memory, retrieval, model surface), it gets `grounding_source: true`. If it's a tool the agent uses *during* a task (file uploads, web search), it doesn't.

### 2.5 The drift detector pattern (test the wire-up, not the runtime)

**The trap:** with 5 file edits across 5 surfaces, the natural reflex is to write a "smoke test" that runs the server. But the server is a subprocess that needs an env var (MINIMAX_API_KEY), a working directory, and a parent process — testing it end-to-end is the wrong unit.

**The right answer:** the test parses the actual files and asserts the load-bearing facts of each wire-up entry. 13 tests in 5 groups:

  - agent_registry: key present, submodule pointer, capabilities
  - mcp.json: key present, command + args
  - BOOTSTRAP.md: substring presence
  - CGP: mcps list, services.minimax block with mcp/cli/verifier
  - cli_tools + skill_pairings: find-skills + cli-host-skills present, paths point at the right submodule

If a future PR removes any of these entries, the test fails. If a future PR renames `pmoves_minimax_mcp` to `pmoves_model_mcp`, the test fails and the commit message has to address why. The test names name the wire-up explicitly.

**Rule of thumb:** wire-up work is best tested by parsing the files and asserting presence/shape, not by running the resulting system. The runtime test is the CI step (out of scope for this slice); the wire-up test is the unit test.

## 3. Wrong-suggestion / Already-addressed (none this slice)

No review threads yet — this is a pre-review LEARNINGS capture. If codex/CodeRabbit surfaces findings, they'll be appended to the 4-bucket taxonomy below.

## 4. Cross-refs

- `AGNOTE4482PHI.t1.md` row `Mavis::MCPCLI-WIREUP-CLAIM-RELEASE::2026-08-18` — the CLAIM
- `.claude/context/cipher.md` — the cipher memory layer doc (this slice, commit 7)
- `.claude/context/hirag.md` — the HiRAG hybrid retrieval doc (this slice, commit 8)
- `pmoves/docs/operations/PROVIDER_VERIFIER_GATE.md` — the conformance gate how-to (this slice, commit 3)
- `pmoves/docs/services/MMX_CLI_SURFACE.md` — the CLI surface catalog (this slice, commit 4)
- `pmoves/docs/skills/PMOVES_SKILLS_REVIEW.md` — the find-skills meta-skill review (this slice, commit 5)
- `pmoves/docs/AGENTS/AGENTS_MD_FORMAT_REVIEW.md` — the open format vs our AGENTS.md (this slice, commit 6)
- `pmoves/contracts/schemas/pmoves-bootstrap/example.cgp.yaml` — the CGP profile update (this slice, commit 2)
- `pmoves/config/agent_registry.yaml` — the MCP server entry (this slice, commit 1)
- `.claude/mcp.json` — the runtime MCP server entry (this slice, commit 1)
- `.claude/BOOTSTRAP.md` — the cold-start entrypoint row (this slice, commit 1)
- `pmoves/configs/cli_tools.yaml` — the `skills` host CLI entry (this slice, commit 9)
- `pmoves/configs/skill-pairings.yaml` — the `find-skills` + `cli-host-skills` entries (this slice, commit 9)
- `pmoves/tests/unit/test_mcpcli_wireup.py` — the drift detector (this slice, commit 10)
- Fold-in PR2: PR #2589 (the 3 NEW submodule gitlinks)
- Fold-in PR1: PR #2586 (skills constellation)
- Fold-in PR3: PR #2590 (PMOVES-agents.md)
- Harness v0 follow-ups: PR #2568 (registered the SKILL surface in `pmoves/configs/submodule_skill_registry.json`)
- CRUSH lane CLI tools registry: PR #2599 (added `minimax-cli` to `cli_tools.yaml` `service_clis`)
- Operator: DARKXSIDE
- Three-body: delivery=Mavis, control=DARKXSIDE, memory=this trail
- CHIT trail: unsigned-local
