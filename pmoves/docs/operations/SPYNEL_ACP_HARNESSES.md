# Spynel ACP Harnesses — which PMOVES fork CLIs actually speak ACP v1

**Node measured:** PMOVES-SPARK (`linux-aarch64`) · **Date:** 2026-09-22 ·
**Pre-flight:** `make -C pmoves submodule-integrity` → PASS (81 gitlinks, 0 uninitialized, 0 drifted, 0 conflicts).

Every verdict below cites a command actually run on this node. Nothing here is
inferred from prose.

---

## 1. What "qualifies" means

Spynel's custom-agent slot (`harness.name: acp`) speaks **stable ACP v1: JSON-RPC
over child-process stdio**. A fork qualifies only if the process it launches
answers an `initialize` request with a JSON-RPC `result` on stdout.

An HTTP API does not qualify, however capable the agent is behind it. A CLI that
starts and never completes `initialize` does not qualify.

---

## 2. Verdict table

| Fork / CLI | Verdict | Command run | What came back |
|---|---|---|---|
| **PMOVES-hermes-agent** | ✅ **PASS** | `hermes-acp` (from its venv) | `result.protocolVersion: 1`, `agentInfo.name: hermes-agent`, `version 0.17.0`, 2 `authMethods`. `--check` → `Hermes ACP check OK` |
| **PMOVES-Agent-Zero** | ✅ **PASS** | `a0 acp --check` | `A0 ACP check OK`. Already covered by Spynel's built-in `agent-zero` alias — no custom config needed |
| **Kilo** (`@kilocode/cli`) | ✅ **PASS** | `kilo acp` | `result.protocolVersion: 1`, `agentInfo.name: Kilo`, `version 7.7.5`, 1 `authMethod` |
| **PMOVES-crush** @ `v0.91.1-pmoves.1` | ❌ **NOT ACP-CAPABLE** | `crush acp` | `Unknown command "acp" for "crush"` (exit 1) |
| **PMOVES-ClawZ** | ⚠️ **ACP surface, not runnable here** | — | Real ACP stdio server in source; no build on this node |
| **PMOVES-deepseek-harness** | ⚠️ **ACP surface, not runnable here** | `pnpm run demo:acp` | Starts a 246-project workspace install; not installed on this node |
| `Pmoves-minimax-cli`, `PMOVES-BoTZ`, `PMOVES-surf`, `PMOVES-space-agent` | ❌ **Rejected** | word-boundary ACP grep over `*.py`/`*.ts`/`*.go`/`*.toml` | Zero ACP references — no command surface to test |

### Why Crush is settled, not merely unconfirmed

Four independent lines, so the negative does not rest on one check:

1. `crush acp` → `Unknown command "acp" for "crush"`, exit 1.
2. `go.mod` declares no ACP dependency.
3. `internal/cmd/root.go` registers `run, dirs, projects, update-providers, logs,
   logout, schema, login, stats, session` (+ `server`, `models`) — there is no
   `acp` command to register.
4. `crush server` is TCP/Unix-socket HTTP (`server.ParseHostURL`,
   default `unix:///run/user/1000/crush-1000.sock`) — an endpoint, which the ACP
   v1 rule disqualifies by definition.

An empirical stdio handshake against `crush run` returned **no response within
20 s**.

The single line `internal/backend/backend.go:3` — *"consumed by protocol-specific
layers such as HTTP (server) and ACP"* — is forward-looking prose about an
intended consumer. It is **not** treated as evidence of a command surface.

### The two "surface present, not runnable" cases, named precisely

- **PMOVES-ClawZ** — `src/acp/server.ts` is a genuine ACP **stdio server**
  (`AgentSideConnection`, `ndJsonStream`, `@agentclientprotocol/sdk`) bridging to
  the OpenClaw Gateway, and `src/cli/command-catalog.ts` registers an
  `openclaw acp` command. **Blocker:** no `node_modules`, no `dist`, and no
  `openclaw` on PATH. Needs a build before it can be probed.
- **PMOVES-deepseek-harness** — `packages/acp/` plus
  `packages/examples/acp-demo/src/bin.ts`, described in its own `AGENTS.md` as an
  "automation-only Agent Client Protocol server". **Blocker:** not installed;
  needs a full pnpm workspace install and the `DEEPSEEK_API_KEY` env var.

---

## 3. Working configuration

These values were set in a throwaway workspace and **round-tripped a real prompt**
(`spynel send … "Reply with exactly the word PONG…"` → `PONG`, exit 0).

### hermes-agent

```yaml
harness:
    name: acp
    acp_command: /home/powerfulmoves/.hermes/hermes-agent/venv/bin/hermes-acp
    acp_args: []
```

### Kilo

```yaml
harness:
    name: acp
    acp_command: kilo
    acp_args:
        - acp
```

### The `acp_args` shape gotcha — this will bite you

In `.spynel/config.yaml`, `acp_args` is a **YAML sequence**, not a string.
Writing `acp_args: ""` fails config parsing outright:

```
spynel: parse .spynel/config.yaml: yaml: unmarshal errors:
  line 10: cannot unmarshal !!str `` into []string
```

Use `[]` for no arguments, or one item per line. The one-line,
command-line-style form described in `spynel docs harnesses` is the **command /
TUI input** shape; the file always stores the shell-free string list.

### No shell syntax — checked

Both configurations above were verified to contain no `&&`, no pipes, no
`$VAR` expansion, no globs, and no quoting that depends on a shell. Spynel never
runs `acp_args` through a shell; anything shell-shaped is passed literally to the
process and will not do what it looks like it does.

---

## 4. Prerequisites, by name

**hermes-agent**
- The `hermes-acp` console script from the **installed** Hermes venv
  (`~/.hermes/hermes-agent/venv/`, Python 3.11). The `PMOVES-hermes-agent`
  submodule has **no** `.venv` — pointing `acp_command` at the submodule will not work.
- `agent-client-protocol==0.9.0` (the `hermes-agent[acp]` extra), already present
  in that venv.
- Provider credentials are read from the Hermes dotenv under `HERMES_HOME`
  (default `~/.hermes/`), loaded automatically at adapter startup, plus
  `~/.hermes/config.yaml`. Configure with `hermes-acp --setup`.
  **No credential value belongs in `.spynel/config.yaml`.**
- Optional env vars, by name: `HERMES_HOME` (relocates the Hermes home),
  `HERMES_ACP_SKIP_CONFIGURED_MCP` (set to `1` to skip global MCP discovery at
  ACP startup).

**Kilo**
- Node.js and `@kilocode/cli` on PATH. Authenticate with `kilo auth login`
  (the agent advertises this as its one `authMethod`).
- ⚠️ The binary on PATH here is **upstream npm `@kilocode/cli` 7.7.5**, not a
  build of the `PMOVES-KeYlOkODe` fork. The fork carries the same `acp` command
  in source (`packages/opencode/src/cli/cmd/acp`) but is not built on this node.

**Agent Zero** — nothing. Select the built-in `agent-zero` alias.

---

## 5. Limitations that apply to every ACP agent

These are properties of ACP and of Spynel's adapter, not bugs to file:

- **No reasoning-effort control.** Thought choices arrive only after session
  creation, so ACP cannot expose them at selection time. `/effort` does nothing here.
- **No speed mode.** ACP defines no speed category.
- **Harness swap requires idle state.** Model, effort and service selections can
  be saved during active work and apply at the next dispatch boundary; the
  harness implementation cannot change while work is in flight.
- **`harness.sandbox` is not an OS sandbox.** ACP agents may act without
  requesting permission. `read-only` restricts what the adapter will grant, not
  what the process can do.
- **Session steering is queued, not native.** All ACP agents use the same-session
  queue: adjacent messages accumulate and dispatch together in arrival order.

---

## 6. The registry axis — `../PMOVES-registry` and PR #3097

`POWERFULMOVES/PMOVES-registry` is the ACP registry fork and the launcher catalog
for fleet-relevant coding agents. It is a **sibling clone by design**
(`../PMOVES-registry`), *not* a submodule — commit `d2d8f97d4` stands up that
convention explicitly. Treating its absence from `.gitmodules` as a gap is wrong
in kind.

**On SPARK the sibling clone is present and populated**: 42 agent entries, HEAD
`a5cc072`.

| Artifact | Where it is | State |
|---|---|---|
| `pmoves/configs/acp_registry_map.json` | **on this branch** | 42 entries — 41 `available`, 1 `linked` (kilo), 0 `forked`. Regenerated 2026-09-22 via `make -C pmoves acp-registry-map`; it was stale by **23 version bumps**. Generated — never hand-edit. |
| `make -C pmoves acp-registry-map` | **on this branch** (`pmoves/mk/infra.mk:683`) | works |
| `pmoves/tools/acp_launcher_probe.py` | **only on `origin/feat/acp-registry-bringup` (PR #3097)** | works unchanged on SPARK |
| `make -C pmoves acp-launcher-probe` | **only on PR #3097** | not reachable from this branch |

### Probe result on SPARK (PR #3097 instrument, default fleet-relevant set)

```
platform: linux-aarch64
  PASS  kilo             [npx-installed] auth=1
  PASS  glm-acp-agent    [npx-installed] auth=2
  PASS  minimax-code     [npx-installed] auth=1
  PASS  qwen-code        [npx-installed] auth=2
  PASS  codex-acp        [npx-installed] auth=2
  PASS  claude-acp       [npx-installed] auth=2
```

6/6 registry launchers complete a real ACP handshake on this node.

### Is landing PR #3097 the precondition?

**For wiring fork CLIs into Spynel as harnesses: no.** That works today with
`harness.acp_command` / `harness.acp_args` and needs nothing from #3097 —
demonstrated above with two agents round-tripping prompts.

**For the registry-launcher axis: yes, it is the unblock.** The probe is the
sanctioned instrument, it is correct, and it passes 6/6 here — but today the only
way to run it is `git show` on a PR branch, which is not an operator path. There
is no `make acp-launcher-probe` on main. Landing #3097 is what makes this
reproducible; writing a second handshake tester would be duplication and should
not happen.

### The reconciliation gap worth naming

The 42-entry map and the sibling clone agree exactly on IDs, so the catalog is in
sync. But the map contains **no entry for any PMOVES-native ACP harness** —
hermes-agent (PASS), Agent Zero (PASS), ClawZ, deepseek-harness, crush are all
absent. The map describes *upstream* ACP agents and PMOVES's relationship to
them; it has no row shape for "our own fork that speaks ACP".

That is precisely the gap between what the map records today and the operator's
framing of PMOVES-registry as the home of the PMOVES.AI harnesses for dispatch
and reproducible deploy. Closing it is **registry submission**, a separate
objective from this inventory.
