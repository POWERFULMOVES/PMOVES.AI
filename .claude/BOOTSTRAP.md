# PMOVES.AI Bootstrap

**Flat foundation. Load this always. Load deeper context only when your task needs it.**

You are on a PMOVES.AI node (Z890 / 5090 / 4090 / KVM4-1 / KVM4-2 / KVM2 / Jetson / SPARK / Cloudflare Edge). Per PR #1378 MOF Architecture: **every node is a pore in the lattice — capacity-class, not expertise-lane.** Run PMOVES to your physical capacity. Delegate across nodes via the paths below when a task exceeds your local reach.

## Emperor-CHIT-Humility — disclose at session start

Before editing or non-trivial work, state which you have vs missing:

- [ ] **Cipher MCP** reachable (`http://localhost:8105/health`)
- [ ] **A2A** reachable (`GET /.well-known/agent-card.json` on Agent Zero)
- [ ] **Known Roads** loaded (table below)
- [ ] **CHIT passphrase** set (`$CHIT_PASSPHRASE`; unsigned fallback is acceptable in dev)
- [ ] **Node-peer visibility** (`make -C pmoves fleet-status`)
- [ ] **MCP/service catalog** loaded (see CATALOG.md when needed)

Missing items are not failures — they are operational facts. Disclose them. Never bluff awareness.

## Known Roads — dangerous ops route through Make targets

| Need | Known Road |
|------|------------|
| Start / restart services | `make -C pmoves up-<service>` (never `docker compose up` raw) |
| Apply secrets | `make -C pmoves secrets-funnel` (before any service start after env change) |
| Read-only health | `make -C pmoves health-summary` / `health-dormant` |
| Fleet view | `make -C pmoves fleet-status` (never raw `tailscale status` for public IPs) |
| CHIT-sign provenance | `make -C pmoves sign-trail SUMMARY=... AGENT=...` |
| Refresh living docs | `make -C pmoves docs-reconcile` |
| Cipher memory for any agent / drop-in model | `PATTERNS.md` § Known Road — Cipher memory (roster entry, `agentId`, token, triage) |
| One key in `pmoves/.env.local` (operator-run; agents zero-access) | `make -C pmoves env-local-{has,set,unset} KEY=NAME` |
| Run the provider-verifier static gate | `python pmoves/tools/provider_verifier_gate.py` (no API calls; 6 checks; FAIL blocks merge via merge-gate) |
| Run the provider-verifier full conformance | `cd Pmoves-MiniMax-Provider-Verifier && python verify.py --providers <file> --output-dir /tmp/run` (operator-only, requires real API keys from `env.shared`) |

Full Known Roads catalog lives in `.claude/PATTERNS.md § Known Roads`. When the damage-control hook converts a raw `docker` / `netsh` / `gh workflow run` command to an `ask` prompt, that means a Make target already exists — use it.

## MCP Entrypoints (configured in `.claude/mcp.json`)

| Server | Transport | Purpose |
|--------|-----------|---------|
| `pmoves-cipher` | streamable-http `http://localhost:8105/mcp` | Persistent agent memory lookups + writes |
| `pmoves-minimax-mcp` | stdio `uvx minimax-mcp` | MiniMax model surface (text/image/video/TTS/voice-clone); submodule PMOVES-MiniMax-MCP |
| `pmoves-hirag-mcp` | stdio `uv --directory ./pmoves-hirag-mcp run python -m hirag_mcp.server` | Hi-RAG v2 hybrid vector+graph+full-text retrieval with cross-encoder reranking (launched by the client; no service to reach) |
| `docker` | `mcp/docker` | Container inspection via local Docker socket |
| `hostinger-mcp` | stdio | Hostinger VPS API via `HOSTINGER_API_KEY` |
| `tailscale` | stdio | Tailnet inventory, stale-node cleanup, ACL operations |

## Cross-node delegation — three paths

| Path | When to use |
|------|-------------|
| **Agent Zero MCP** `POST http://localhost:8080/mcp/command` | Orchestration, task delegation, subordinate agent spawn |
| **A2A** `GET /.well-known/agent-card.json` (plumbing wired via PR #1293; activate via `A0_SET_a2a_server_enabled=true`) | Peer discovery, task submission across nodes |
| **NATS** `agent.peer.heartbeat.v1` (Phase D, pending mutual-watching skill) | Continuous peripheral observation of peer nodes |

No task requires all three — pick the narrowest path that delivers. When A2A is disabled (default), say so in your disclosure; don't pretend cross-node delegation is available.

## Where to look next

| You want | Load |
|----------|------|
| Service ports, URLs, health endpoints | [`CATALOG.md`](./CATALOG.md) |
| Full Known Roads, dev patterns, CHIT, skill pairings | [`PATTERNS.md`](./PATTERNS.md) |
| Who's working on what right now | `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` § Active Claim Register |
| Cold-start orientation | `pmoves/docs/AGENTS/AGNOTE4482_SITREP.md` |
| Gateway pointers (audits, waves, Three-Body) | `pmoves/docs/AGENTS/AGNOTE4482.md` |
| Architecture-level thesis | `pmoves/docs/architecture/PMOVES_MOF_ARCHITECTURE.md` + `PMOVES_GRAND_CONVERGENCE.md` |
| Submodule-specific context | That submodule's `CLAUDE.md` — opt-in only, not auto-loaded |

## Rules that survive every session

1. **Leverage existing services, don't rebuild.** Hi-RAG v2 for retrieval, NATS for events, MinIO via Presign for artifacts, Agent Zero `/mcp/*` for orchestration. The catalog exists.
2. **Test before PR.** `/test:pr` + document the Testing section. Docstring coverage ≥80% on new Python.
3. **Never raw docker / tailscale CLI** for operations with Make-target equivalents. The hooks will block and redirect.
4. **Village Rule.** No agent operates alone in production validation. Claim (AGNOTE4482PHI.t1), work, sign, release.
5. **Signing is optional locally, never skipped for session-end provenance.** `sign-trail` emits unsigned if `CHIT_PASSPHRASE` unset — that's fine in dev, still run it.
6. **Prefer the minimum task scope.** If you find adjacent cleanups, open a follow-up; don't expand the current claim.

## When context feels heavy

If this file is all you remember, you can still do the right thing:
- Ask "is there a Make target for this?" — if yes, use it.
- Ask "is this file in `CATALOG.md` or `PATTERNS.md`?" — if yes, load it.
- Ask "have I disclosed what I don't know?" — if no, do that first.

The rest is scaffolding.

## Windows host quirks (POWERFULMOVES / 5090)

These are operational facts about this specific Windows host, not failures — disclose them and route around them.

**Verification status (2026-11-19).** Every repo-backed claim below was re-derived against `origin/main` @ `5dc385b9fa7` and is pinned by `pmoves/tests/tools/test_bootstrap_windows_host_quirks_ratchet.py`. Claims that are HOST state, which the repository cannot see, are tagged **[HOST]**.

**Size (measured 2026-11-19).** This file is past the ≤5k-char budget `.claude/CLAUDE.md` used to state — and it was past it BEFORE this section landed: measured 5,907 chars on `main` @ `5dc385b9fa7` against a documented 5k. That number was never gated, so it was fiction. `.claude/CLAUDE.md` now states the measured budget, and the ratchet above reads that budget FROM that doc and fails when this file grows past it — so the next section cannot grow an always-loaded file without a deliberate, published decision.

### POSIX paths in bash subprocesses

Git-bash on this host cannot resolve Windows absolute paths (`C:\Users\...` becomes `C:Users...` and bash 127s on the resulting path). The operator has standardised on POSIX/relative paths in shell invocations. The repo carries the same note next to its own `bash -n` sweep in `pmoves/tools/tests/test_pmoves_launcher_generator.py`.

**Apply**:
- Never `bash -n "C:\Users\..."` — silently 127s.
- For test files: create a scratch subdir under cwd (e.g. `pmoves/tools/tests/.bash_n_scratch/`), `os.chdir()` into it, run `bash -n <name>` (relative), then `os.chdir()` back. Avoid `tempfile.TemporaryDirectory` here — its cleanup races with the cwd change on Windows. The working example is `pmoves/tools/tests/test_pmoves_launcher_generator.py`.
- Take argv[0] from `resolve_bash()` in `pmoves/tools/bash_resolver.py` (or `find_bash()` for "skip if no bash"), never a bare `"bash"` and never `shutil.which("bash")` — `pmoves/tests/test_no_bare_bash_argv.py` ratchets that, because on Windows `which("bash")` resolves to the WSL stub in `C:\Windows\System32`.
- For other tools (python, pwsh): forward-slash POSIX form (`C:/Users/...`) usually works; bare `C:\Users\...` does not. **[HOST]** — operator practice, not repo-verified.
- `subprocess.run([...])` calls inherit the parent's env; pass `env=` explicitly only when you need to inject a portable PATH.

### `claude-pmoves` roster gate: a degraded header is KEPT; only a normalizer failure is fail-closed

The hand-written `deploy/provision/claude-pmoves.{sh,ps1,cmd}` (NOT touched by the registry-driven generator at `pmoves/tools/pmoves_launcher_generator.py` — `managed="hand"` exclusion) implements an MCP roster gate per PR #2847. Claude Code's documented response to an unresolvable reference is to warn and then use the literal text as the value, so `Bearer ${CIPHER_API_TOKEN}` goes on the wire as that string and 401s — a server that looks configured and never authenticates.

**What the gate actually does — measured against the live normalizer and the live launcher (2026-11-19):**

| path | an unset credential in `headers` or `env` | the session starts? |
|---|---|---|
| normalizer RAN | the server is KEPT and DEGRADED, and the literal `${...}` is left in the header | YES |
| normalizer FAILED | the raw roster still holds a bare `${VAR}` | NO |

Read those two rows as they are, not as one fail-closed story: **the gate is fail-OPEN on a degraded header.** With the normalizer running and `CIPHER_API_TOKEN` unset, `pmoves-cipher` is KEPT, the roster records it DEGRADED, and `Authorization: Bearer ${CIPHER_API_TOKEN}` reaches the wire as that literal — the session starts, and the server 401s. Only an unresolvable reference in a server's `url` field DROPs the server; a **defaulted** reference (`${VAR:-...}`) is not a finding, it renders its default.

The REFUSAL is the OTHER path. `deploy/provision/claude-pmoves.sh` reaches its FAIL CLOSED block ONLY when the normalizer could not run (missing, no interpreter, non-zero exit, or no output); then, and only then, a raw roster still holding a bare `${VAR}` makes the launcher REFUSE to start the session (`PMOVES_ALLOW_RAW_ROSTER=1` overrides it). The transform itself is `pmoves/tools/mcp_roster_normalize.py`.

The roster the gate reads is `.claude/mcp.json` — the launcher fetches it with `git show origin/main:.claude/mcp.json`, not from the working tree. Run `make -C pmoves session-check` for the live verdict list on the current node.

**Servers that WARN on this node (PMOVES_NODE_ID=5090)** — **[HOST]**: which of these actually WARN depends on the node's env, which the repository cannot see. The roster's own references:

| server | env var | roster field | verdict when unset |
|---|---|---|---|
| `pmoves-cipher` | `TS_Z890` | `url` | DROPPED |
| `pmoves-cipher` | `CIPHER_API_TOKEN` | `headers` | DEGRADED |
| `agent-zero` | `TS_Z890` | `url` | DROPPED |
| `agent-zero` | `AGENT_ZERO_MCP_TOKEN` | `url` | DROPPED |
| `pmoves-nats-fleet` | `NATS_URL` | `env` | DEGRADED |
| `pmoves-4090-web` | `MCP_GATEWAY_AUTH_TOKEN` | `headers` | DEGRADED |
| `supabase-db` | `SUPABASE_DB_URI` | `env` | DEGRADED |
| `hostinger` | `HOSTINGER_API_TOKEN` | `env` | DEGRADED |

Notes on the rows:
- `pmoves-nats-fleet` carries `${NATS_CREDS:-}` in `env`, so an unset `NATS_CREDS` is NOT a finding there — a defaulted reference renders its default. Its `_NATS_CREDS_NOTE` documentation now sits at the SERVER level (a `_`-prefixed key beside `_purpose`), OUTSIDE the fields the gate expands (`url`, `headers`, `env`), so the note is not expanded either. MEASURED 2026-11-19 against the live normalizer: while that note was still inside `env`, the server degraded on EVERY launch — the normalizer expanded the prose and recorded BOTH the malformed `${...}` AND a bare `NATS_CREDS` finding, so it was degraded even with every var set. `NATS_URL` is the reference that flags this server now.
- `hostinger` reads `HOSTINGER_API_TOKEN`. The sibling server `hostinger-mcp` is the one that reads `HOSTINGER_API_KEY`; they are not interchangeable.
- `pmoves-4090-web` is in `.claude/mcp.json` only — it has no entry in `pmoves/config/mcp_inventory.json`.
- `pmoves/env.shared.example` says `TS_Z890` gates THREE servers — `pmoves-cipher`, `agent-zero` and `archon`. The roster today carries only the first two; `archon` is not in `.claude/mcp.json`. Trust the roster, not the env template's comment.
- The roster yields findings for more servers than these 8 rows on a node whose other credentials are unset (`cloudflare`, `tailscale`, `huggingface`, `pmoves-cipher-local`, `pmoves-minimax-mcp`, `composio-local`, `hostinger-mcp`).

**Fix paths** (operator decides):
1. Set `TS_Z890` (and the other `TS_<node>` vars) on the host to the Z890 **MagicDNS hostname** (`pmoves-z890`), NOT a raw tailnet IP — `pmoves/env.shared.example` says so explicitly (IPs churn on re-enrolment, and committed IPs are a fleet no-go). `.claude/hooks/damage-control/patterns.yaml` blocks real Tailscale IPs in committed docs, and `make -C pmoves fleet-status` is the hostname-only way to read the fleet.
2. Set `NATS_URL` — the roster reads the bare `${NATS_URL}`. `NATS_PASSWORD` is NOT what the roster reads; `NATS_CREDS` is a path to the `.creds` file and only matters once the funnel materializes it.
3. Populate `SUPABASE_DB_URI` with a HOST-reachable connection string. The roster's own `_setup` note is explicit: `postgresql://pmoves:<SUPABASE_DB_PASSWORD>@<host>:<port>/pmoves` using `localhost`/`host.docker.internal` and the published port — NOT the internal `supabase-db` compose service name, which a host process cannot resolve. `pmoves/env.shared.example` ships it empty.
4. Add `MCP_GATEWAY_AUTH_TOKEN` — the roster reads that name, not `MCP_CLIENT_SECRET` (which `pmoves/env.shared.example` ships empty).
5. Add `HOSTINGER_API_TOKEN` — the roster reads that name. Neither `HOSTINGER_API_TOKEN` nor `HOSTINGER_API_KEY` is in `pmoves/env.shared.example`, so there is no existing key to alias; add the name the roster expects.

### SessionEnd hook: the `remember` plugin

The plugin `remember@claude-plugins-official` (Digital Process Tools) registers four hooks — `SessionStart`, `UserPromptSubmit`, `PostToolUse` and `SessionEnd` — each invoked as `bash "${CLAUDE_PLUGIN_ROOT}/scripts/<name>-hook.sh"`. On this Windows host the plugin runner has been observed NOT substituting `${CLAUDE_PLUGIN_ROOT}`, so the hook is invoked with a literal `${CLAUDE_PLUGIN_ROOT}` in the path and fails with "Hook cancelled". **[HOST]** — not re-verified on 2026-11-19.

The plugin version on this host is **0.43.1** (`~/.claude/plugins/cache/claude-plugins-official/remember/0.43.1/`), and its `hooks/hooks.json` still carries the literal `${CLAUDE_PLUGIN_ROOT}` in all four commands, so the shape above is unchanged. **[HOST]**

**Workarounds** (until upstream fix):
- Disable the plugin: it is enabled in the GLOBAL `~/.claude/settings.json` (`enabledPlugins` -> `remember@claude-plugins-official`), NOT in this repo's `.claude/settings.json` — remove it from the global file. The plugin is non-critical for PMOVES work (memory persistence only).
- Hardcode the path: edit the plugin's `hooks.json` at `~/.claude/plugins/cache/claude-plugins-official/remember/0.43.1/hooks/hooks.json` and replace `${CLAUDE_PLUGIN_ROOT}` with the absolute plugin root. Note: the plugin update overwrites it.

### `claude-pmoves` stays hand-written

The registry-driven generator at `pmoves/tools/pmoves_launcher_generator.py` (PR #3092) deliberately does NOT regenerate `claude-pmoves.{sh,ps1,cmd}` or `crush-pmoves.{sh,ps1,cmd}`. These carry SDK-fixed FAIL-CLOSED MCP roster logic (PR #2847, #2809) that the simple template cannot reproduce. If you need to extend the hand-written launcher surface, edit the file directly + update the matching ratchet at `deploy/provision/tests/test-launcher-root-resolution.sh` (which covers the `.sh` launchers `deploy/provision/claude-pmoves.sh` and `deploy/provision/crush-pmoves.sh`). The generator's `--include-hand` flag is a one-shot escape hatch for drift-pinning, not a normal workflow — the generator's own comment calls rewriting the SDK-fixed files "usually a no-no".
