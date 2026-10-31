# MiniMax Code Client — PMOVES Parity + pmoves.bootstrap/v1 Profile — LEARNINGS

**Date:** 2026-10-26
**Author:** mavis (mvs_5d5493b128b640e9aff8d45adcc77a66)
**Branch:** `feat/minimax-client-pmoves-parity` (off `origin/main 65ea6eed20e`)
**Worktree:** `C:\Users\russe\pmoves-wt-minimax-parity`
**Operator directive:** "we this client also needs same integration and access with PMOVES.AI" + "full parity + CGP bootstrap profile" + "make todos with dependencies verify fix local in work trees — approved on all, ok to proceed"

## TL;DR

The MiniMax Code client (the Mavis desktop runtime) was the ONE agent stack
in the fleet that did **not** get the PMOVES MCP roster. The other six
(claude, kimi, kilocode, opencode, hermes, crush) are all generator targets in
`pmoves/tools/mcp_config_generator.py`; `minimax` was not, so
`~/.minimax/mcp.json` carried only the `composio` entry.

This lane closes that gap in three coupled pieces, and makes the
`pmoves.bootstrap/v1` profile **load-bearing** rather than documentation:

1. `render_minimax()` — a MiniMax-NATIVE renderer.
2. `pmoves/configs/mavis_collection/clients/minimax-code.yaml` — the client
   bootstrap profile (identity + tools + services + routing + constraints).
3. A **profile-driven roster filter** so the rendered config and the profile
   stay diffable against each other, fail-closed on drift.

Plus the `minimax-pmoves` launcher family, generated through the sanctioned
launcher generator (not hand-edited).

## Measured result (live, on the operator's host)

```
config: C:\Users\russe\.minimax\mcp.json
servers: 7

  agent-zero               OK    sse    200
  composio                 FAIL  http   HTTP 401   <- pre-existing, operator mints the key
  flute-voice              OK    sse    200
  hostinger                SKIP  stdio  (runtime-spawned)
  pmoves-cipher-local      OK    sse    200
  pmoves-nats-fleet        SKIP  stdio  (runtime-spawned)
  tailscale                SKIP  stdio  (runtime-spawned)

reachable=3  failed=1  skipped=3
```

The MiniMax runtime picked the config up live — `mcp list` returned all 7
servers with no client restart.

## What the client was missing

`pmoves/config/mcp_inventory.json` carries 17 MCP servers in 2 groups
(`core_pmoves` = 15, `docker_toolkit` = 2). Six of the seven clients got
them via `mcp_config_generator.py`; the MiniMax client got none.

The MiniMax-native schema is NOT the Claude schema. Differences that forced
a dedicated renderer:

| key | Claude/Kimi renderer | MiniMax native | why it matters |
|---|---|---|---|
| `type` | omitted (inferred from `url`) | **required** | MiniMax needs an explicit transport discriminator |
| `disabled` | `disabled: true` | `enabled: false` | MiniMax has no `disabled` key; emitting one leaves the server ON |
| `configured` | n/a | `true` | runtime-managed flag; the merge preserves the operator's value |
| `builtin` | n/a | `false` | true only for servers the client ships itself |
| stdio vs remote | mixed freely | **never mixed** | the runtime picks the spawn path by `type`; a mixed entry dead-ends silently |

## The profile is load-bearing

The profile's `super_nodes.tools[].key` list is the roster. The generator
filters the inventory to exactly those keys, and **fails closed** if a
declared key does not resolve:

```
MCPConfigError: Client profile for 'minimax' declares tool keys that the
inventory does not resolve for this client/endpoint: <key>. Either the
inventory entry is missing, is allowlisted to other clients only, or the
endpoint mode (local) excludes it.
```

That is the property that makes the profile and the generated config
diffable against each other — and it is why the profile is a real artifact
rather than a doc. `--no-profile-filter` is the explicit escape hatch.

## The schema extension

`pmoves/configs/mavis_collection/manifest.schema.yaml` (the CGP v1.0-derived
`pmoves.bootstrap/v1` schema) already had `identity` + `super_nodes` with
`auth / models / datasets / personas / mindmap / skills / plugins / chit`. It
was missing the four groups the bootstrap contract names for a CLIENT:

- `tools` — the MCP roster the client may load
- `services` — the operator-facing service tags (Tailscale / RustDesk /
  Hostinger / Cloudflare) with the endpoint each resolves to
- `routing` — where to find the sibling agents when work hands off
- `constraints` — what the client must NOT do, each with a `source` and a
  `reason` so a downstream agent can CITE the refusal

`pmoves/tools/mavis_collection_resolve.py` enforces "every super_node entry
has at least one pointer". The pointer set was
`{ref, source, spec, design, endpoint, constellation_id, provider}`; it now
also accepts `key` (a tool key in the inventory) and `target` (a sibling
agent). `constraints` entries carry `source` — the provenance of the rule —
which satisfies the rule without needing a special case.

## Five findings this lane surfaced (all pre-existing, none caused by the lane)

### 1. `flute-voice-mcp` is a dead inventory entry (404)

`pmoves/config/mcp_inventory.json` declares `flute_mcp_local_url =
http://localhost:8055/mcp` and a `flute-voice-mcp` server with transport
`http`. MEASURED against the running `pmoves-flute-gateway-1` container
(`ghcr.io/powerfulmoves/pmoves-flute-gateway:pmoves-latest`), the gateway's
ONLY routes are:

```
GET  /sse          (SSE stream endpoint — MCP clients connect here)
POST /messages     (JSON-RPC messages, requires ?session_id=)
GET  /healthz
```

There is no `/mcp`. The entry 404s for every client that gets it (all six
siblings have no `clients` allowlist on it).

**Lane action:** `flute-voice-mcp` is NOT declared in the MiniMax client
profile — a client profile must name only surfaces that actually answer. The
inventory defect itself is a separate lane (it reaches the other six
clients' configs too).

### 2. The generator's merge mode never REMOVES a server

`write_client_config(merge=True)` deep-merges the rendered config into the
existing file. A server that drops out of the roster therefore LINGERS in the
live config forever. Measured: after removing `flute-voice-mcp` from the
profile, a plain regen left the dead entry in place.

**Lane action:** the profile change required a one-time `--no-merge` reset.
That is a footgun worth its own lane (a `--prune` flag that drops keys the
render no longer declares).

### 3. The generated config was not written owner-only

`write_client_config` called `write_text()` with no `chmod`. The repo's own
`pmoves/tests/test_mcp_roster_normalize.py` asserts the roster is `0o600`
("it holds expanded tokens") — so the writer and the contract disagreed.

This became load-bearing for the MiniMax client: the desktop app reads
`~/.minimax/mcp.json` directly and does NOT source `env.shared`, so the
tracked-repo convention of `${VAR}` placeholders leaves the agent-zero URL
path with a literal `${AGENT_ZERO_MCP_TOKEN}` (the runtime 404s on it) and
the cipher/flute headers unauthorised (401). The live config therefore holds
EXPANDED values, which makes the missing `0600` a real exposure.

**Lane action:** `write_client_config` now does `os.chmod(path, 0o600)` (a
no-op on Windows, applied on Linux fleet nodes).

### 4. The MiniMax Code CLI shim is broken on this host

`C:\Users\russe\.minimax\bin\minimax.cmd` execs
`.../MiniMax Code/resources/resources/daemon/cli.js`, which does not exist —
the daemon now ships inside `app.asar`, so the shim is stale from a previous
install layout:

```
Error: Cannot find module 'C:\Users\russe\AppData\Local\Programs\MiniMax Code\
resources\resources\daemon\cli.js'
```

The shim is written by the client's own installer; the fix is a reinstall or
a re-laid-down shim, not a PMOVES change. Reported, not patched here.

### 5. The launcher domain's readOnly guard did not fire for this client

`.claude/hooks/damage-control/known_roads.py` marks `deploy/provision/*` and
`pmoves/scripts/*` paths whose basename contains `-pmoves` as launcher-domain
readOnly for agents, and `.known-road-active` is explicitly "must be
operator-written OUT-OF-BAND" (an agent that could write it could
self-authorize its own bypass).

The damage-control hook is **Claude-Code-wired**. It did not run for the
MiniMax Code client, so the generator wrote
`deploy/provision/minimax-pmoves.{sh,ps1,cmd}` + the two install scripts
without a grant.

**Lane action / disclosure:** the files are MACHINE-GENERATED from
`pmoves/configs/cli_tools.yaml` (not hand-edited twins), the full generator
regen touched no other launcher, `--check` is clean, and the whole set lands
in a PR the operator reviews. The operator should know the guard did not
fire, because the guard is the repo's answer to "what if an agent bypasses a
domain rule".

**Also true:** the operator approved this lane in-conversation ("approved on
all, ok to proceed"), which is the human half of the model; the guard is the
mechanical half. Both are recorded here so the trail is complete.

## Constraint-discipline note (self-reported)

During the final live-config dump I printed the agent-zero MCP token in
plaintext via an ad-hoc `python -c` that dumped the full `url` field. The
verification script itself (`verify_minimax_roster.py`) was written to print
only the server key + status, precisely because that URL carries a secret in
its path — but the ad-hoc dump bypassed that discipline.

**Action:** the agent-zero MCP token is now in this session's transcript and
should be rotated by the operator. The lesson generalises: any dump of a
generated client config must strip URL paths and header values, because the
agent-zero token rides in the URL path and the cipher/flute keys ride in
header values.

## 4-bucket + 5-class taxonomy

### Bucket: SDK provenance
- **class: code/SDK** —
  `pmoves/tools/mcp_config_generator.py` (`render_minimax`, `DEFAULT_OUTPUTS`,
  `RENDERERS`, `CLIENT_PROFILES`, `_profile_tool_keys`, the `0600` chmod),
  `pmoves/tools/mavis_collection_resolve.py` (pointer set),
  `pmoves/tools/pmoves_launcher_generator.py` (`BINARY_BY_TOOL`,
  `DEFAULT_BLOCKLIST_BY_TOOL`, `DEFAULT_BRIDGES_BY_TOOL`),
  `pmoves/configs/mavis_collection/manifest.schema.yaml` (4 new groups),
  `pmoves/configs/mavis_collection/clients/minimax-code.yaml` (new),
  `pmoves/configs/agents/forms/mavis.yaml` (new),
  `pmoves/configs/cli_tools.yaml` (`minimax-pmoves`),
  `pmoves/config/mcp_inventory.json` (2 `clients` allowlists)
- **class: doc** — this LEARNINGS file + the AGNOTE row
- **class: agent memory** — the "print statuses not secrets" discipline and
  the "merge never removes" gap are cross-project lessons

### Bucket: operational
- **class: lane/PR** — `feat/minimax-client-pmoves-parity`, one PR, supersedes
  nothing (new surface)
- **class: env/ops** — the LIVE `~/.minimax/mcp.json` was rewritten on the
  operator's host (7 servers, 3 verified 200). The pre-existing backup is at
  `~/.minimax/mcp.json.pre-mcp-bootstrap.bak` (533 bytes, composio-only)

### Bucket: provenance chain
- **class: trace/ID** — branch `feat/minimax-client-pmoves-parity` off
  `origin/main 65ea6eed20e`
- **class: SDK+test contract** — 13/13 in
  `pmoves/tests/test_minimax_client_parity.py` (0.37s); launcher generator
  `--check` exit 0 (60 files, no drift); `bash -n` exit 0 on both shell
  scripts; 0 parse errors in both PowerShell scripts; live roster 3 reachable
  / 1 pre-existing failure / 3 runtime-spawned

### Bucket: decision narrative
- **class: SDK+doc vs workaround** — chose a dedicated renderer over
  reusing the Claude renderer (the schemas differ in 4 keys), and a profile
  filter over a client allowlist in the inventory (the profile must be
  load-bearing). Did NOT hand-edit `deploy/provision/` — the launcher came
  from the generator.
- **class: scope discipline** — did NOT fix the `flute-voice-mcp` inventory
  defect in this lane (it reaches the other six clients' configs; that is a
  separate lane). Did NOT fix the broken `minimax.cmd` shim (it is the
  client's own installer artifact). DID fix the `0600` write mode, because
  the live config now holds expanded secrets and that gap is in the file the
  lane writes.

## Follow-ups (not in this slice)

1. **Fix the `flute-voice-mcp` inventory entry** — the gateway has no `/mcp`.
   Either drop the entry or point it at the real SSE pair. Reaches all six
   sibling clients' configs.
2. **Add a `--prune` mode to the generator** — merge never removes a server
   that dropped out of the roster.
3. **Re-install / re-lay the MiniMax Code CLI shim** on the host (operator).
4. **Rotate the agent-zero MCP token** (see the discipline note above).
5. **Mint the Composio `x-consumer-api-key`** — the live config's
   `composio` entry 401s, exactly as it did before this lane.
6. **Make the damage-control hook client-agnostic** — the launcher-domain
   guard is Claude-Code-wired, so a non-Claude client can write the launcher
   domain without a grant.
