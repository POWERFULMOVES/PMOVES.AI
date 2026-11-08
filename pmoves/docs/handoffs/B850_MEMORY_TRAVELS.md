# B850 memory travels — handoff

Lane: `feat/b850-memory-travels` (B850-CLAUDE / Knuckles, claim filed 2026-10-08T12:26:29Z).

Goal: a B850-CLAUDE session (and Z890/5090/4090/SPARK siblings) boots on ANY
node with its memory reachable.

## Gaps (measured 2026-10-08)

| # | Gap | Status |
|---|-----|--------|
| 1 | Fleet roster entry `pmoves-cipher` (tailnet Z890 :8105/mcp/sse) answers 401; `pmoves-cipher-local` (localhost:8105) works | COULD-NOT-FIX-LOCALLY (design decision + Z890 operator step) |
| 2 | `brv` (ByteRover CLI, `byterover-cli`) absent on knuckles; launcher says nothing | FIXED in fragment + manifest; launcher hookup LANDED in `c8b7377ab` (road `launcher:pr:3313`) |
| 3 | cipher `agent_checkpoint` rows record `harness:"unknown"`, `model:"unknown"` | DESIGN-ONLY (server fix is in the `Pmoves-cipher` submodule); interim launcher stamp LANDED in `c8b7377ab` |
| 4 | host-run `pmoves-nats-fleet` MCP handed `NATS_URL` host `nats` (compose-internal) -> "no servers available" | FIXED in the normalizer (P6), tested red then green |

Findings are appended per gap below as each is resolved.

## Gap 1 — fleet cipher 401: the bearer is fine, the token STORE is per-node

### Measured (2026-10-08, knuckles, live roster `claude-pmoves-mcp-roster.wdphbjra.json`)

Header values compared by shape and hash only, never printed:

| entry | host | path | Authorization len | token len | prefix | sha256[:12] |
|---|---|---|---|---|---|---|
| `pmoves-cipher` | tailnet Z890 (13-char name) | `/mcp/sse` | 46 | 39 | `cipher_` | `e673a4ac4835` |
| `pmoves-cipher-local` | loopback | `/mcp/sse` | 46 | 39 | `cipher_` | `e673a4ac4835` |

So the header is NOT an unexpanded `${VAR}`, NOT the bootstrap bearer, and NOT
different between the two entries: both carry the same expanded, per-agent
`b850-claude` bearer. The normalizer did its job.

Authenticated probe (in-process `urllib`, header taken from the roster, token
never written to disk or argv):

| request | `pmoves-cipher` (Z890) | `pmoves-cipher-local` (B850) |
|---|---|---|
| roster bearer | **401** `invalid or revoked token` | **200** |
| no header | 401 `Bearer token required` | 401 `Bearer token required` |
| fabricated well-formed `cipher_` bearer | 401 `invalid or revoked token` | 401 `invalid or revoked token` |
| `/health` | 200, **no `per_agent_auth` field** | 200, `per_agent_auth.state=ok` |

Z890's shim is reachable over the tailnet (so its `CIPHER_BIND` is no longer
loopback) and treats our real bearer exactly like a fabricated one.

### Root cause — by construction, not a launcher bug

`Pmoves-cipher/src/pmoves/auth.ts:8` defaults the lookup to
`http://supabase-kong:8000/rest/v1` — the SERVING node's own compose-network
Kong — and `auth.ts:124` resolves a `cipher_<uuid>` bearer by
`cipher_agent_tokens?token_uuid=eq.<uuid>&revoked_at=is.null`. Every node runs
its own Supabase, and `pmoves/scripts/mint_cipher_token.py` writes to
`$SUPABASE_REST_URL` (default `localhost:8000`, i.e. the node it runs on) with a
FRESH `uuid4` every time. So:

- the `b850-claude` row exists in B850's store (local 200 proves it);
- Z890's store has no row with that `token_uuid`, so it answers "invalid or
  revoked" — the same answer as for a fabricated bearer;
- the roster gives both entries ONE variable (`${CIPHER_API_TOKEN}`), and the
  mint road cannot produce one bearer registered in two stores. On any node
  other than Z890 the fleet entry is therefore guaranteed to 401, whatever is
  minted. On Z890 itself both entries hit the same store and both work.

Measurement limit: I cannot see Z890's container log from here, so I cannot
rule out that Z890's shim (an older build: no `per_agent_auth` in `/health`)
is ALSO failing its Supabase lookup. Either way the B850 row is not in Z890's
store, so the fix below is required in both cases.

### Why this is COULD-NOT-FIX-LOCALLY

Making memory travel needs a decision between two designs, and both need an
operator step on Z890. Neither is a launcher patch.

- **A. One bearer per agent, registered in every store it must reach.** No
  roster change. Needs a NEW mint mode that registers an EXISTING `token_uuid`
  (today mint always generates a fresh one — there is no road), the bearer
  carried to Z890 through the CHIT pipeline, and revocation done in every
  store (`revoke_cipher_token.py` is also per-store).
- **B. A distinct fleet bearer variable** (recommended). The fleet entry
  becomes `Bearer ${CIPHER_FLEET_API_TOKEN:-${CIPHER_API_TOKEN}}`: the inner
  reference stays bare (a miss is still classified hard by `session_check`),
  Z890 keeps working with no new key, and other nodes 401 exactly as today
  until a fleet token is bound — non-regressing, so it can land before
  provisioning. `pm-cipher-token-bind.sh` binds it from a
  `CIPHER_FLEET_TOKEN_<AGENT>` key in `pmoves/.env.local`. Cost: the fleet URL
  appears in ~35 tracked files (inventory, generator output, `.kimi`, kilo, 7
  Hermes profiles, 17 claws configs) and the inventory test pins the bare
  `${CIPHER_API_TOKEN}` form, so this is a fleet roster change, not a lane fix.

**Operator step (owning node: Z890), required for either design:** on Z890 run
`make -C pmoves cipher-mint-token AGENT=b850-claude` (b850-claude has an active
card), and deliver the bearer to knuckles through the CHIT pipeline
(`make -C pmoves env-local-set KEY=CIPHER_FLEET_TOKEN_B850_CLAUDE` under B, which
prompts without echo). Repeat per roaming agent (`z890-claude` needs nothing;
`5090-claude` and `4090-claude` each need a Z890 row; SPARK has no `*-claude`
signing card in `pmoves/config/signing_identity_cards.yaml`, so it needs a card first). Also
`make -C pmoves up-cipher` on Z890 so its shim reports `per_agent_auth` and a
future 401 can be told apart from a lookup failure.

## Gap 2 — `brv` absent, and nothing said so

Install route verified from the submodule (read-only): `Pmoves-cipher/package.json`
is `byterover-cli` 3.16.1, `bin: {brv: ./bin/run.js}`, `engines.node >=20`;
its README installs with `npm install -g byterover-cli`. Under fnm/nvm the npm
global prefix is in `$HOME`, so no sudo. Nothing was installed.

Landed on this branch:

- `pmoves/scripts/pm-brv-check.sh` — new fragment, same contract style as
  `pm-cipher-token-bind.sh`: always returns 0, sets `PM_BRV_OK`, `PM_BRV_LINE`
  (one stderr line, `WARN: brv=MISSING ... Install (user-level, no sudo): npm
  install -g byterover-cli`) and `PM_BRV_PROMPT` (the same fact for the session
  prompt, because stderr scrolls away before the TUI paints).
- `pmoves/configs/cli_tools.yaml` — `host_clis.brv` (optional), so
  `make -C pmoves cli-check` now reports it: measured `MISSING  brv (optional)`.
- `pmoves/tests/test_pm_brv_check.py` — hermetic PATH: missing is loud + rc 0,
  present is quiet, and the fragment's install hint is pinned to the manifest.

LANDED in `c8b7377ab` — the hookup in `pmoves/scripts/claude-pmoves.sh`. That
path is `readOnlyPaths` (`pmoves/scripts/*-pmoves.sh`) and grants are
operator-reserved, so it was first staged as
`pmoves/docs/handoffs/patches/B850_MEMORY_TRAVELS_brv_launcher.patch`
(`git apply --check` rc 0; `bash -n` clean on the patched copy), then applied
under the operator-approved road `launcher:pr:3313` (2026-10-08). The block
sits after the identity-carry block and before `pm_ident_prompt_args`, so the
prompt sentence is composed into the single `--append-system-prompt` flag.
The patch file is kept as a record only — **do not re-apply it**; its context
is already in the tree.

Unattended grant found while checking: `.claude/hooks/damage-control/.known-road-active`
holds `compose:pr:3260`, 146 h old, verdict `NOT honoured [stale]`. Not ridden;
reported here so its owner can clear it.

## Gap 3 — checkpoints filed as `unknown/unknown`

Measured: `pmoves_cipher_session_recall(agentId=b850-claude, limit=10)` on
`pmoves-cipher-local` returned **1** checkpoint (2026-09-20), with
`harness:"unknown"`, `model:"unknown"`. n=1, so this shows the defect exists,
not how widespread it is.

### Where the value comes from (submodule `Pmoves-cipher` @ `cd426d50`, the gitlink on origin/main)

| file:line | what |
|---|---|
| `src/pmoves/mcp-sse.ts:632-633` | tool schema: `harness` and `model` are OPTIONAL, `default: 'unknown'` |
| `src/pmoves/mcp-sse.ts:817` | `const {..., harness = 'unknown', model = 'unknown', summary} = args` |
| `src/pmoves/mcp-sse.ts:821-822` | `unknown` written into both the content header and `metadata` |
| `src/pmoves/mcp-sse.ts:844, :854` | recall reads them back, also defaulting to `unknown` |

The server never guesses: it stamps whatever the CALLER passes, and no caller
passes anything. Nothing in the launcher, the roster or the prompt tells the
model these arguments exist, so it omits them.

### Design (DESIGN-ONLY — the server change is inside the submodule)

Precedence at write time: **explicit tool argument > per-session client header
> `'unknown'`**. A tool argument equal to `'unknown'` counts as absent, because
schema-default-filling clients send it literally.

1. **Server** (`Pmoves-cipher`, fork PR on `PMOVES.AI-Edition-Hardened`):
   - `mcp-sse.ts`, beside `identityFromRequest` (`:87`): add
     `clientFromRequest(req): {harness?: string; model?: string}` reading
     `X-PMOVES-Harness` / `X-PMOVES-Model`. Sanitize: trim, at most 64 chars,
     `[A-Za-z0-9._:/@+\[\]-]` only, else undefined. These are SELF-ASSERTED
     labels, not identity — keep them OUT of `McpAuthContext` (`:20`) so nothing
     can mistake them for authentication.
   - `:496-500` (SSE `GET /sse`, the request that OPENS the session — headers
     are present there) and `:545` (stateless `POST /`): compute it and pass it
     to `buildMcpServer` (`:561`) as a new optional trailing parameter.
   - `:817`: `harness = pick(args.harness, client.harness)`,
     `model = pick(args.model, client.model)`, where `pick` skips
     undefined/empty/`'unknown'`.
   - Test: session_save with no args + headers -> stamped from headers; args
     present -> args win; `'unknown'` arg + header -> header; oversized/garbage
     header -> `unknown`.
2. **Roster** (main repo, lands WITH or AFTER the server change, never before:
   an inert header the server ignores is a gated publisher, not a wired one):
   add to both cipher entries in `pmoves/config/mcp_inventory.json`
   `"X-PMOVES-Harness": "${PMOVES_HARNESS:-unknown}"` and
   `"X-PMOVES-Model": "${PMOVES_MODEL:-unknown}"`, then regenerate
   (`python -m pmoves.tools.mcp_config_generator --client claude` etc.). The
   `:-unknown` default is deliberate: a bare reference would make
   `mcp_roster_normalize.py` DROP cipher on any node that does not export the
   label, trading a missing label for missing memory.
3. **Launchers** export `PMOVES_HARNESS` (each knows its own: `claude-code`,
   `crush`, `kimi-cli`, `kilocode`, `hermes-agent`) and, where the launcher
   actually knows it, `PMOVES_MODEL` (`--model` / `ANTHROPIC_MODEL` after
   `claude_backend_apply` in the inner launcher).

### Interim, client-side (LANDED in `c8b7377ab`, protected path)

`pmoves/docs/handoffs/patches/B850_MEMORY_TRAVELS_checkpoint_stamp_launcher.patch`
for `pmoves/scripts/claude-pmoves.sh`: exports `PMOVES_HARNESS=claude-code` and
appends one prompt sentence telling the model to pass `harness 'claude-code'`
and its own exact model id on every `pmoves_cipher_session_save`. The model is
the most reliable source of its own id (the launcher composes the prompt
BEFORE `claude_backend_apply` may swap the model). Fixes new checkpoints
without a server change; it relies on the model following the instruction, which
is why the server-side stamp above is still needed.

Both patches were APPLIED in `c8b7377ab` under the operator-approved road
`launcher:pr:3313` (+26 lines in `claude-pmoves.sh`; pre-apply check: `git
apply --check` rc 0, scratch copy 355 -> 381 lines, `bash -n` clean;
`shellcheck` is not installed on knuckles — not run). The two `.patch` files
are kept as a record only — **do not re-apply them**.

## Gap 4 — the bus: a host-run NATS MCP was handed a container hostname

A session that cannot reach NATS cannot see its siblings, so the bus is part of
"memory travels".

**Measured (team-lead, 2026-10-08, re-measured here):** the live roster gives
`pmoves-nats-fleet` — which `uv run`s `nats_mcp.server` on the HOST — a
`NATS_URL` whose host is `nats`. That is env.shared's IN-STACK value, correct for
containers; #3309 (`derive_nats_url.py`) re-derives only its userinfo and keeps
the host, by design, and this fix does not touch it. On the host, `nats` does not
resolve. With the roster's own credentials and nothing else changed:

| NATS_URL host | result (raw socket: INFO, CONNECT, PING — nothing published) |
|---|---|
| `nats` (before) | `gaierror [Errno -3] Temporary failure in name resolution` |
| `127.0.0.1` (after P6) | `INFO` -> `PONG` (authenticated) |

**Rule:** env files are written for containers; a stdio MCP server launched by
`uv`/`npx`/`uvx` is a host process. The normalizer now has a P6 pass
(`pmoves/tools/mcp_roster_normalize.py`): in the `env` of a host-run server, a URL
whose host is a compose service name is pointed at that service's published
loopback port. Narrow on purpose:

- table `_IN_STACK_HOSTS = {"nats": ("NATS_PORT", 4222)}` — only names whose host
  publish is measured (`${NATS_BIND:-0.0.0.0}:${NATS_PORT:-4222}:4222`);
- only the client port (4222, or no port) is rewritten — `nats:6222`/`:8222` are
  not the published listener and are left alone; `natsbox` is not `nats`;
- the published port follows `NATS_PORT` when set;
- servers launched through `docker`/`podman` keep `nats` (`docker run -e` forwards
  the value into a container on the compose network, where the name is right);
- scheme, userinfo and path are carried byte-for-byte — the credential is never
  parsed, decoded or re-encoded; a comma-separated server list is handled per entry;
- every rewrite is announced on stderr and recorded in
  `_pmoves_roster_verdicts.rewritten` as `{server, field, from_host, to_host}` —
  hostnames only, never the value.

Comparison with cipher-local: it never had the defect because its URL is a
literal `http://localhost:8105/...` in the inventory (`cipher_local_url`), not an
env-file value. NATS is the only host-run server whose URL comes from an env file
written for containers. Sweep of the live roster: 9 host-run servers; the only
URL host that is compose-internal is `pmoves-nats-fleet`'s `nats`.

**Not fixed, same defect elsewhere:** `.kimi/mcp.json`, `kilo.json` and 7
`pmoves/configs/claws/opencode-*.json` also pass a raw `${NATS_URL}` to the NATS
MCP, and none of those harnesses runs this normalizer. Claude Code sessions are
fixed; those harnesses need the same rule in their own config path.
Also not measured: `pmoves-hirag-mcp` has no `env` block and inherits the
launcher's environment, so I could not see what host it dials from the roster.

Tests (`pmoves/tests/test_mcp_roster_normalize.py`): 76 collected before, 84
after (8 new). RED commit `1352fbeb3`: 80 passed / 4 failed, rc 1 — all 4
failures behavioural (host still `nats`; no notice on stderr), and the 4
narrowness/docker guards passed pre-fix, as they must. GREEN `c36cc8f31`: 84
passed, rc 0.

Not done, per brief: no leafnode topology change, nothing published to the bus.
