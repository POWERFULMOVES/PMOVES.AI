# B850 memory travels — handoff

Lane: `feat/b850-memory-travels` (B850-CLAUDE / Knuckles, claim filed 2026-10-08T12:26:29Z).

Goal: a B850-CLAUDE session (and Z890/5090/4090/SPARK siblings) boots on ANY
node with its memory reachable.

## Gaps (measured 2026-10-08)

| # | Gap | Status |
|---|-----|--------|
| 1 | Fleet roster entry `pmoves-cipher` (tailnet Z890 :8105/mcp/sse) answers 401; `pmoves-cipher-local` (localhost:8105) works | COULD-NOT-FIX-LOCALLY (design decision + Z890 operator step) |
| 2 | `brv` (ByteRover CLI, `byterover-cli`) absent on knuckles; launcher says nothing | FIXED in fragment + manifest; launcher hookup is a PATCH (protected path, no grant) |
| 3 | cipher `agent_checkpoint` rows record `harness:"unknown"`, `model:"unknown"` | investigating |

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

NOT landed — the two-line hookup in `pmoves/scripts/claude-pmoves.sh`. That path
is `readOnlyPaths` (`pmoves/scripts/*-pmoves.sh`); the road is
`KNOWN_ROAD=launcher:<reason>`, and grants are operator-reserved, so I did not
open one. The exact edit is
`pmoves/docs/handoffs/patches/B850_MEMORY_TRAVELS_brv_launcher.patch`
(`git apply --check` rc 0 against this branch; `bash -n` clean on the patched
copy). It sits after the identity-carry block and before
`pm_ident_prompt_args`, so the prompt sentence is composed into the single
`--append-system-prompt` flag. Operator: open
`launcher:handoff:B850_MEMORY_TRAVELS.md` (or `launcher:pr:<n>` once a PR
exists), `git apply` the patch, close the road.

Unattended grant found while checking: `.claude/hooks/damage-control/.known-road-active`
holds `compose:pr:3260`, 146 h old, verdict `NOT honoured [stale]`. Not ridden;
reported here so its owner can clear it.
