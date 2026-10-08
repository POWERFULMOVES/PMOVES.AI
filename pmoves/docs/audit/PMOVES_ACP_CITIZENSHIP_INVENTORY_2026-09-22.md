# PMOVES ACP v1 Citizenship Inventory — 2026-09-22

**Node:** PMOVES-SPARK (`/home/powerfulmoves/agent-zero/PMOVES.AI`) · **Branch:** `feat/comfyui-ui-to-api` · **Operating surface:** OpenRoom
**Task:** `t-20260922T123842Z-8c5e1b93da70` (goal `g-20260922T123542Z-cb95b8fe02be7bfa`, round 1, criterion **SC-2**)
**Sibling evidence consumed:** `t-20260922T123510Z-4d6ce8d214e2` — cited inline as **[SIB]**

---

## 1. The bar

A **completed JSON-RPC `initialize` handshake over child-process stdio**, answered by the process itself.

- An HTTP API does **not** qualify, however capable.
- **A2A does not qualify** (§5).
- A process that launches but never answers `initialize` does **not** qualify.
- File presence, a pinned dependency, a source comment, or a vendor's self-check (`--check`) are **not** `acp_conformant` evidence on their own.

This document authors no manifest, changes no configuration, and opens no pull request. It exists to answer one question: *what may we truthfully declare in a public registry manifest?*

---

## 2. Candidate list — recorded before results

Enumerated two ways, so the negatives are on the record:

**(a) Every submodule/service declaring an ACP SDK dependency** — `grep -rlE 'agent-client-protocol|@agentclientprotocol/sdk|@zed-industries/agent-client-protocol' --include=package.json --include=pyproject.toml --include=go.mod --include=Cargo.toml PMOVES-* pmoves/services`:

1. `PMOVES-hermes-agent/pyproject.toml`
2. `PMOVES-ClawZ/package.json`
3. `PMOVES-KeYlOkODe/packages/opencode/package.json`
4. `PMOVES-deepseek-harness/package.json` (+ `packages/acp/acp`, `packages/subagent/subagent-acp`, `packages/test-support/acp-snapshot`)
5. `PMOVES-composio/ts/packages/cli/package.json`

**(b) Named in the task or by [SIB] without an SDK dependency**, carried anyway so the negative is recorded:

6. `PMOVES-crush` @ `v0.91.1-pmoves.1`
7. `PMOVES-Agent-Zero` @ `a83e74f1`
8. `PMOVES-BoTZ`, `PMOVES-surf`, `PMOVES-space-agent`, `Pmoves-minimax-cli` — rejected by [SIB]'s word-boundary grep with no ACP surface at all
9. `PMOVES-BotZ-gateway` @ `43b95f2` — carried because the task names it as an A2A implementation (§5)

No further PMOVES fork shipping an agent CLI was found.

---

## 3. Verdict table

| # | Candidate | Pin / version inspected | Verdict | Basis |
|---|---|---|---|---|
| 1 | **PMOVES-hermes-agent** | `4595a54987f34ab04dcc9f0bec64257f23c12e42` | **`acp_conformant`** | §4.1 — `initialize` answered from the **pinned submodule tree** |
| 2 | **Agent Zero ACP connector** (`a0 acp`) | installed `a0` CLI **2.12**; submodule pin `a83e74f1` = `v2.11-180-ga83e74f18` | **`acp_conformant` — for the installed CLI only** | §4.2 — `initialize` answered; the stdio connector is **not** in the submodule, so this is *not* a pinned-fork claim |
| 3 | **PMOVES-crush** | `v0.91.1-pmoves.1` (`da922dd8`) | **`not_acp`** | §4.3 |
| 4 | **PMOVES-KeYlOkODe** (`kilo acp`) | fork pin `503b8602` | **`indeterminate`** | §4.4 — the PASS on this node is **upstream npm `@kilocode/cli` 7.7.5**, not a build of our fork |
| 5 | **PMOVES-ClawZ** | `913b53ad808` | **`indeterminate`** | §4.5 — real `AgentSideConnection` stdio server; no build artifacts, build = environment mutation |
| 6 | **PMOVES-deepseek-harness** | `50f1201` | **`indeterminate`** | §4.6 — `packages/acp` present; needs pnpm workspace install + `DEEPSEEK_API_KEY` |
| 7 | **PMOVES-composio** | `027b773` | **`not_acp`** (as an agent) | §4.7 — `ClientSideConnection`: an ACP **consumer**, never answers `initialize` |
| 8 | **PMOVES-BoTZ** | at [SIB]'s inspection | **`not_acp`** | [SIB] word-boundary grep — no ACP surface |
| 9 | **PMOVES-surf** | at [SIB]'s inspection | **`not_acp`** | [SIB] word-boundary grep — no ACP surface |
| 10 | **PMOVES-space-agent** | at [SIB]'s inspection | **`not_acp`** | [SIB] word-boundary grep — no ACP surface |
| 11 | **Pmoves-minimax-cli** | at [SIB]'s inspection | **`not_acp`** | [SIB] word-boundary grep — no ACP surface |
| 12 | **PMOVES-BotZ-gateway** | `43b95f2` | **`not_acp`** | §5 — no ACP surface; also no A2A surface at this pin (see correction) |

---

## 4. Per-candidate evidence

### 4.1 PMOVES-hermes-agent — `acp_conformant` at pin `4595a549`

[SIB] settled hermes as PASS but explicitly recorded that it ran *"from the installed venv `hermes-acp` console script, **not** from the submodule (submodule has no venv)"*. That leaves the question this task actually has to answer — **does our pin conform?** — open. Settled here, with no environment mutation: the installed venv's interpreter was pointed at the pinned tree via `PYTHONPATH`, installing nothing.

Provenance check first:

```
$ PYTHONPATH=$SM $V/bin/python -c "import acp_adapter, acp_adapter.entry as e; print(acp_adapter.__file__); print(e.__file__)"
/home/powerfulmoves/agent-zero/PMOVES.AI/PMOVES-hermes-agent/acp_adapter/__init__.py
/home/powerfulmoves/agent-zero/PMOVES.AI/PMOVES-hermes-agent/acp_adapter/entry.py
```

Handshake (`$SM` = the pinned submodule, `$V` = `~/.hermes/hermes-agent/venv`):

```
PYTHONPATH=$SM  PROBE_CWD=$SM  $V/bin/python -m acp_adapter
→ {"jsonrpc":"2.0","id":1,"method":"initialize",
   "params":{"protocolVersion":1,"clientCapabilities":{...}}}
```

Observed response, verbatim:

```json
{"jsonrpc":"2.0","id":1,"result":{"agentCapabilities":{"loadSession":true,"promptCapabilities":{"image":true},"sessionCapabilities":{"fork":{},"list":{},"resume":{}}},"agentInfo":{"name":"hermes-agent","version":"0.20.0"},"authMethods":[{"description":"Authenticate Hermes using the currently configured minimax runtime credentials.","id":"minimax","name":"minimax runtime credentials"},{"args":["--setup"],"description":"Open Hermes' interactive model/provider setup in a terminal. Use this when Hermes has not been configured on this machine yet.","id":"hermes-setup","name":"Configure Hermes provider","type":"terminal"}],"protocolVersion":1}}
```

stderr confirms the server side: `acp_adapter.server: ACP client connected` / `acp_adapter.server: Initialize from unknown (protocol v1)`.

**Version discrimination — this is the load-bearing detail.** The pinned tree reports `agentInfo.version` **`0.20.0`**. The installed copy at `~/.hermes/hermes-agent` (commit `5ecf3bf0e0`, `v2026.6.19-436-g5ecf3bf0e`) reports **`0.17.0`**, confirmed by a separate run of `$V/bin/hermes-acp`. The two differ, which proves the `0.20.0` handshake was served by **our pin**, not by the installed copy leaking onto `sys.path`.

**Prerequisite, stated honestly:** the pin declares ACP as an *optional extra* — `pyproject.toml:252: acp = ["agent-client-protocol==0.9.0"]` — and the pinned tree has no venv. The runtime `acp` module came from the installed venv at exactly the pinned version (`0.9.0`, verified via `importlib.metadata`). So the truthful claim is: **PMOVES-hermes-agent @ `4595a549` answers ACP v1 `initialize` when `agent-client-protocol==0.9.0` is present.** The adapter code is ours and it conforms; the SDK is a declared dependency that must be installed. Declaring conformance without that prerequisite in the manifest would overstate it.

Entry points at the pin: `pyproject.toml:361: hermes-acp = "acp_adapter.entry:main"`, and `acp_adapter/__main__.py` → `from .entry import main` — so `python -m acp_adapter` is a real module entry point. **Verified, not assumed.**

### 4.2 Agent Zero — `acp_conformant` for the installed CLI 2.12; **not** a claim about our pin

**The task's premise is wrong and is corrected here.** The task records `plugins/_a0_acp` as *"existing only on a branch tip roughly 329 commits ahead of our pin and **absent locally**."* It is **present at our actual pin**:

```
$ git -C PMOVES-Agent-Zero rev-parse HEAD
a83e74f1845e974004ceb14250216fc903e6d989
$ git -C PMOVES-Agent-Zero ls-tree -r --name-only HEAD | grep _a0_acp
plugins/_a0_acp/README.md
plugins/_a0_acp/api/session.py
plugins/_a0_acp/default_config.yaml
plugins/_a0_acp/extensions/python/message_loop_prompts_after/_50_acp_mode.py
plugins/_a0_acp/extensions/python/startup_migration/_10_migrate_legacy_acp.py
plugins/_a0_acp/plugin.yaml
plugins/_a0_acp/tests/test_migration.py
plugins/_a0_acp/tests/test_session.py
plugins/_a0_acp/webui/config.html
plugins/_a0_acp/webui/thumbnail.webp
```

**But that does not make the submodule an ACP citizen**, and this is the distinction a registry manifest would get wrong. `plugins/_a0_acp/plugin.yaml` describes it as *"Connect ACP-capable editors through the local A0 CLI connector"*, and its README states the client invocation is `a0 acp --host http://localhost:32081`. The plugin is the **runtime-side** half — it owns ACP session metadata, history, modes, model settings. **The stdio connector that actually answers `initialize` is the `a0` CLI, which is not in this submodule.**

[SIB] recorded `a0 acp --check` → `A0 ACP check OK`. That is a vendor self-check, below this document's bar, so a full `initialize` was run here (non-mutating):

```
$ a0 acp --no-docker-discovery
→ {"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":1,...}}
```

```json
{"jsonrpc":"2.0","id":1,"result":{"agentCapabilities":{"loadSession":true,"promptCapabilities":{"embeddedContext":true},"sessionCapabilities":{"close":{},"fork":{},"list":{},"resume":{}}},"agentInfo":{"name":"agent-zero","title":"Agent Zero","version":"2.12"},"authMethods":[],"protocolVersion":1}}
```

Provenance of the binary: `/home/powerfulmoves/.local/bin/a0` is a uv-tool shim executing `/home/powerfulmoves/.local/share/uv/tools/a0/bin/python -m agent_zero_cli`. `a0 --version` → **2.12**. Our submodule pin is **`v2.11-180-ga83e74f18`** — a different, earlier line.

**Therefore:** the handshake is real and reproducible, but the truthful declaration is *"the installed `a0` CLI 2.12 is ACP v1 conformant"*, **not** *"PMOVES-Agent-Zero @ `a83e74f1` is ACP v1 conformant"*. A registry manifest that pins the fork commit and claims ACP conformance from it would be making a claim this evidence does not support. Separately, Spynel already ships a built-in `agent-zero` harness alias ([SIB]), so a registry entry adds no capability here.

### 4.3 PMOVES-crush — `not_acp` at pin `v0.91.1-pmoves.1` (`da922dd8`)

**The single source comment is explicitly not treated as proof.** `internal/backend/backend.go:3` reads *"by protocol-specific layers such as HTTP (server) and ACP."* — forward-looking prose in a doc comment. It is the only `\bacp\b` match in the entire fork (`*.go`/`*.md`/`*.json`, tests excluded), re-confirmed here. A comment is not a command surface.

[SIB] settled this with four independent lines, none of which was re-run:

1. `crush acp` → `Unknown command "acp" for "crush"`, exit 1.
2. `go.mod` declares no ACP dependency.
3. `internal/cmd/root.go` registers `run`, `dirs`, `projects`, `update-providers`, `logs`, `logout`, `schema`, `login`, `stats`, `session`, `server`, `models` — no `acp`. Independently corroborated here by listing `internal/cmd/`, which contains no `acp*.go`.
4. `crush server` is TCP/Unix-socket HTTP (`server.ParseHostURL`) — disqualified by the bar in §1.

A stdio handshake against `crush run` returned **no response within 20 s** ([SIB]).

**"Not ACP-capable at this pin" is the correct and useful result.** Crush must not appear in a registry manifest as an ACP agent.

### 4.4 PMOVES-KeYlOkODe (`kilo acp`) — `indeterminate` at fork pin `503b8602`

[SIB] recorded a genuine PASS — `protocolVersion: 1`, `agentInfo.name: Kilo`, version 7.7.5 — **and flagged its own caveat**: the binary on PATH is **upstream npm `@kilocode/cli` 7.7.5**, not a build of our fork. Confirmed here: `which kilo` → `/home/powerfulmoves/.nvm/versions/node/v24.15.0/bin/kilo` (an nvm/npm global), and the fork carries the command in source at `PMOVES-KeYlOkODe/packages/opencode/src/cli/cmd/acp.ts` but is **not built on this node**.

**Blocker, named precisely:** building `PMOVES-KeYlOkODe` @ `503b8602` requires a pnpm/bun workspace install — an environment mutation this task is forbidden from performing, and it would race `t-20260922T123510Z-4d6ce8d214e2`'s tree. Until the fork itself is built and handshaken, *upstream kilo conforms* is not evidence that *our fork conforms*. **Nothing about PMOVES-KeYlOkODe may be declared.**

### 4.5 PMOVES-ClawZ — `indeterminate` at pin `913b53ad808`

ACP surface is real, not incidental: `PMOVES-ClawZ/src/acp/server.ts` imports `AgentSideConnection` (line 7) and *"Starts the ACP Gateway bridge and serves AgentSideConnection over stdio"* (line 92, instantiated line 253) — the **agent** side, i.e. the side that answers `initialize`. `package.json` declares the ACP SDK. An `openclaw acp` CLI command exists in `src/cli/command-catalog.ts` ([SIB]).

**Blocker, named precisely:** `PMOVES-ClawZ/node_modules` and `PMOVES-ClawZ/dist` do not exist, and there is no `openclaw` on PATH. Probing it requires a build — environment mutation, forbidden here. **Dependency:** if this matters for the manifest, it belongs to `t-20260922T123510Z-4d6ce8d214e2` or a follow-on, not to this task.

### 4.6 PMOVES-deepseek-harness — `indeterminate` at pin `50f1201`

`packages/acp/`, `packages/subagent/subagent-acp`, `packages/test-support/acp-snapshot` all declare the ACP SDK; `packages/examples/acp-demo/src/bin.ts` is described as an *"automation-only Agent Client Protocol server"* with `pnpm run demo:acp` ([SIB]).

**Blocker, named precisely:** not installed. Bringing it up needs a full 246-project pnpm workspace install plus the `DEEPSEEK_API_KEY` environment variable — **named here only; no value appears in this document.** [SIB] disclosed that a bounded attempt left an empty, gitignored `node_modules/` directory behind; confirmed still empty here (0 entries), and the submodule's tracked files are unchanged.

### 4.7 PMOVES-composio — `not_acp` as an agent, at pin `027b773`

This is the one candidate a dependency-grep alone would misclassify, so it is recorded explicitly. `ts/packages/cli/package.json:75` declares `"@agentclientprotocol/sdk": "^1.4.0"`, and `src/services/run-subagent-acp.ts` uses it — but at line 895 it constructs `new acp.ClientSideConnection(...)`. `AgentSideConnection` appears nowhere in `src/`.

Composio is an ACP **client**: it *launches and drives* other ACP agents as subagents. It never answers `initialize`; it sends one. **An ACP consumer is not an ACP citizen**, and declaring it as an agent in a registry manifest would be a false claim. (It is also unbuilt here — no `node_modules`, no `dist` — but the verdict does not rest on that.)

---

## 5. A2A is not ACP

**A2A does not qualify under §1 and no A2A implementation may be declared as ACP.** They are different protocols with different transports: ACP v1 is JSON-RPC over child-process **stdio**; A2A here is **HTTP** — `/.well-known/agent-card.json` plus `/a2a/v1/*` routes. Conflating them would produce a manifest that fails a protocol matrix and would put a false capability claim in public.

All three A2A implementations in this repo, listed and **explicitly labelled not-ACP**:

| # | A2A implementation | Location / pin | Surface | ACP? |
|---|---|---|---|---|
| A1 | **Agent Zero runtime** | `PMOVES-Agent-Zero` @ `a83e74f1` | `helpers/fasta2a_server.py`, `helpers/fasta2a_client.py`, `prompts/agent.system.tool.a2a_chat.md`, `docs/guides/a2a-setup.md` | **Not ACP** — HTTP/Starlette |
| A2 | **hermes-agent A2A platform plugin** | `PMOVES-hermes-agent` @ `4595a549` | `plugins/platforms/a2a/` — `adapter.py`, `protocol.py`, `security.py`, `tools.py` | **Not ACP** — HTTP agent-card surface, separate from `acp_adapter/` |
| A3 | **PMOVES Agent Zero supervisor service** | `pmoves/services/agent-zero/` (in-repo) | `python/features/a2a/server.py`, `types.py`; `main.py:706` mounts `/.well-known/agent-card.json` and `/a2a/v1/*` | **Not ACP** — HTTP, Supabase-JWT gated |

Note that **A2 and 4.1 are the same fork**: hermes ships an A2A plugin *and* a separate ACP adapter. They are independent surfaces. Only `acp_adapter/` supports the ACP claim; `plugins/platforms/a2a/` supports nothing about ACP.

> **Correction to the task's premise.** The task names the third A2A implementation as the **"BoTZ gateway"**. No A2A surface exists at `PMOVES-BotZ-gateway` @ `43b95f2` (`git ls-tree -r | grep -i a2a` → empty; `grep -rlniE '\ba2a\b'` over `*.py|*.ts|*.md|*.json` → empty), nor in `pmoves/services/botz-gateway`. The only `\ba2a\b` hits under `PMOVES-BoTZ` are two prose mentions of *Cipher's* `/.well-known/agent.json` in `scripts/pmoves_cli.py:10` and `PMOVES_Edition.md:109` — a reference to a third party's surface, not an implementation. The actual third implementation is **A3, the PMOVES Agent Zero supervisor service**, which is in-repo rather than a submodule. The count of three holds; the attribution does not.

The prior scout's finding that repo docs and code contain no A2A/ACP conflation is preserved: in every tree inspected, the two surfaces live in separate directories with separate transports, and nothing labels one as the other.

---

## 6. Closing statement — what may honestly be declared today

**Exactly one PMOVES fork may be declared an ACP v1 citizen at its recorded pin: `PMOVES-hermes-agent` @ `4595a54987f34ab04dcc9f0bec64257f23c12e42`.**

That claim is supported by a completed `initialize` handshake served by the pinned tree itself, discriminated from the installed copy by `agentInfo.version` `0.20.0` vs `0.17.0` (§4.1). It must carry its prerequisite: **`agent-client-protocol==0.9.0` installed**, since the pin declares ACP as an optional extra and ships no venv. A manifest entry omitting that prerequisite would overstate what we verified.

**A second entry is defensible only if it is worded as a CLI-version claim, not a fork-pin claim:** the installed **`a0` CLI 2.12** completes the handshake (§4.2). Our submodule pin `a83e74f1` (`v2.11-180`) contains the runtime-side `_a0_acp` plugin — present, contrary to the task's premise — but **not** the stdio connector that answers `initialize`. Pinning the fork commit and claiming ACP conformance from it would be false. Spynel already covers Agent Zero with a built-in alias, so this entry buys nothing and is the easiest place to introduce an untrue claim. **Recommendation: omit it, or word it strictly as the CLI version.**

**Nothing else may be declared, and here is why for each:**

- **Crush** `v0.91.1-pmoves.1` — settled **`not_acp`** on four independent lines. The one source comment is prose about a layer that does not exist at this pin.
- **KeYlOkODe** `503b8602` — **`indeterminate`**. The only PASS on this node came from upstream npm `@kilocode/cli` 7.7.5. Declaring our fork on the strength of upstream's binary would be precisely the kind of false positive a schema validator cannot catch.
- **ClawZ** `913b53ad8` — **`indeterminate`**. A genuine `AgentSideConnection` stdio server, but unbuilt; the capability is plausible and **unproven**, and plausible is not declarable.
- **deepseek-harness** `50f1201` — **`indeterminate`**. Unbuilt; needs a 246-project workspace install and `DEEPSEEK_API_KEY`.
- **composio** `027b773` — **`not_acp`** as an agent. It is an ACP *client*; it sends `initialize`, it does not answer one.
- **BoTZ, surf, space-agent, minimax-cli, BotZ-gateway** — **`not_acp`**, no ACP surface.
- **All three A2A implementations (A1/A2/A3)** — **not ACP**, by transport and by protocol.

**One out of twelve.** The registry's own verifier checks shape, not truth: it cannot detect an ACP claim for an agent that never answers `initialize`. Every entry beyond hermes would rest on file presence, a pinned dependency, a source comment, a vendor self-check, or an upstream binary — each one explicitly disqualified in §1, and each one a claim that would propagate publicly under the operator's GitHub identity before anything could contradict it.

---

## 7. Boundary and provenance

- **Read-only.** `.spynel/config.yaml` unmodified; harness selection unchanged (`claude-code`, unchanged throughout per [SIB]); nothing installed, built, or created.
- **No handshake settled by `t-20260922T123510Z-4d6ce8d214e2` was re-run.** Crush's four lines, the kilo PASS, and the ClawZ/deepseek/BoTZ/surf/space-agent/minimax findings are cited from it. The three handshakes run here are additions it left open — the hermes **pin** (it ran the installed venv and said so), a full `initialize` for Agent Zero (it ran only `--check`), and the composio client/agent discrimination (not in its candidate set).
- **No environment mutated in another task's tree.** The hermes pin was probed via `PYTHONPATH` against an already-installed interpreter.
- **No credential values** appear here. `DEEPSEEK_API_KEY` is named only.
- **Not committed.** Branch `feat/comfyui-ui-to-api` carries an unrelated dirty tree; this document is left **untracked** and no pull request was opened.
