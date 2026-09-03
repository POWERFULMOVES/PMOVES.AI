# Cipher Memory — Auth Provisioning & Verification Runbook

**Service:** `cipher-api` (`pmoves-cipher-api-1`), published on loopback `:8105`.
**Scope:** how `CIPHER_API_TOKEN` is provisioned, how to verify enforcement, and
what the token does and does not buy.

> **`/health` CANNOT tell you the auth posture.** `/health` and `/healthz` are in
> `PUBLIC_PATHS` (`Pmoves-cipher/src/pmoves/auth.ts`), so they answer `200` whether
> the service is fully enforcing or completely open. `docker ps` reads `(healthy)`
> in both states, and startup logs never mention dev mode. **This is why the fleet
> ran fail-open on at least one node without anyone noticing.** Use the matrix in
> §3, never the health endpoint.
>
> This is not hypothetical plumbing. The one signal that fires **automatically**
> every session — `.claude/hooks/session-env-check.sh:60`, the SessionStart hook —
> is `curl -sf http://localhost:8105/health && echo UP`, and prints
> `Cipher: UP`. `/health` is in `PUBLIC_PATHS`, so that line reads `UP` just as
> happily while every MCP client on the node is 401ing. Pre-existing and not
> changed here; treat `Cipher: UP` as "the process is alive", never as "auth is
> configured". Giving that hook a discriminating probe is a follow-up lane.

---

## 1. The two token modes (they are NOT interchangeable)

`resolveToken()` in `src/pmoves/auth.ts` branches on a **prefix**:

| Token shape | Path taken | Resolves to |
|---|---|---|
| does **NOT** start with `cipher_` | compared against `$CIPHER_API_TOKEN` | `agentId: "bootstrap"` |
| **starts with** `cipher_` | Supabase lookup in `cipher_agent_tokens` | that row's `agent_id` |

**Consequence:** the bootstrap/env-var token **must not** carry a `cipher_` prefix.
A `cipher_`-prefixed value never consults the env var at all — it goes to Supabase
and 401s unless a matching un-revoked row exists. The `cipher_{uuid.hex}` format
belongs to the per-agent lane only (see `.kilo/command/cipher-village-pr-2-per-agent-tokens.md`).

## 2. Provisioning (the sanctioned road — no raw env edits)

`CIPHER_API_TOKEN` is already declared in `pmoves/bootstrap/registry.json` under
service id `cipher`, targeting `pmoves/env.shared`, with
`generate: {type: random_urlsafe, length: 32}` — prefix-less, i.e. the correct
shape for §1. It is marked **`required: false`**, which is precisely why it was
never provisioned: `--check` never fails on it and the interactive wizard skips it.
It is **not** in `pmoves/configs/secrets_cleared.yaml`, so empty is not a
deliberate configured state here — it is an omission.

```bash
# 1. mint + write the value (surgical in-place replace of one key in env.shared)
python pmoves/scripts/bootstrap_env.py --rotate CIPHER_API_TOKEN
#    --gen-type defaults to the registry's random_urlsafe -> prefix-less. Correct.
#    To supply an externally-minted value WITHOUT it passing through argv:
#      MY_TOK=... python pmoves/scripts/bootstrap_env.py --rotate CIPHER_API_TOKEN --value-env MY_TOK

# 2. propagate into the tier env files compose actually reads
make -C pmoves chit-export && make -C pmoves secrets-funnel

# 3. OPERATOR STEP — the container must be recreated to pick up a new env var.
#    A running container's environment is immutable; `restart` is NOT enough.
make -C pmoves up-cipher
```

Why a recreate is unavoidable: `pmoves/docker-compose.agents.yml` sets
`CIPHER_API_TOKEN=${CIPHER_API_TOKEN:-}` as compose **interpolation** (the service
has no `env_file:` of its own), resolved from the `--env-file` layering in
`pmoves/Makefile:94-133`. Interpolation happens at container-create time.

Note the `:-` there: an **empty** value interpolates cleanly and silently restores
fail-open. `${CIPHER_API_TOKEN:-}` cannot fail closed on a blank. After step 2,
confirm the value is non-empty before recreating.

### 2a. Ordering — steps 1-3 are ONE unit, and they come BEFORE the roster change

Steps 1, 2 and 3 must run back-to-back on a node. **Between step 2 and step 3 the
node's cipher is down for every client, whatever the roster says**, and no client
config can prevent it. Measured on B850 in exactly that state (token in
`env.shared` and the tier files, container not yet recreated):

```
$ bash pmoves/scripts/with-env.sh bash -c '...'
STATE: token SET in env (non-empty), container NOT yet recreated (still fail-open)
real token, no agentId        -> 401
real token, agentId=bootstrap -> 401
real token, /mcp/sse          -> 401
```

The server's `expected` is still the empty string it was created with, so
`resolveToken()`'s `token === expected && expected` is false and it returns `null`.
Every state, measured on this node unless noted:

| # | `CIPHER_API_TOKEN` in env | container | roster form | goes on the wire | result |
|---|---|---|---|---|---|
| A | absent | fail-open | `${VAR:-}` | `Bearer ` (empty) | **200** |
| B | absent | fail-open | `${VAR}` (bare) | the literal `${VAR}` text | **401** |
| C | set | fail-open *(the step-2 to step-3 window)* | `${VAR:-}` | the real token | **401** |
| C'| set | fail-open *(same window)* | `${VAR}` (bare) | the real token | **401** |
| D | set | enforcing | `${VAR:-}` | the real token | 200 *(sidecar)* |
| E | set | enforcing | `${VAR}` (bare) | the real token | 200 *(sidecar)* |

Read C against C'. Once the variable is set, **both roster forms emit identical
bytes**, so the roster form is irrelevant to the provisioning window — keeping
`:-` would not have shortened or softened it. The two forms differ in exactly one
row, A vs B: a node that never runs step 1. That is a fleet question, not an
ordering question — see §6a.

**Therefore:**

1. Run steps 1-3 on the node, contiguously. Verify with §3 (`no header -> 401`).
2. Land the roster change (`.claude/mcp.json` and its siblings) **after** that.

The reverse order — roster first — puts the node into row B, which is a real
outage (200 today, 401 after the merge) for the whole interval before someone gets
to step 1. An earlier draft of this lane recommended that order, on the theory
that recreating the container while the roster still carried `:-` would break
sessions. Row D shows it does not: `:-` resolves the real token perfectly well
against an enforcing server. The fear was unfounded and the order it produced was
backwards.

## 3. Verification — the only reliable test

Run the whole block. `q` is the search parameter name (not `query`).

Two things this block has to get right, both measured rather than assumed:

* **It runs through `pmoves/scripts/with-env.sh`.** `bootstrap_env.py --rotate`
  writes `env.shared`; it does **not** export into your shell. A probe pasted
  into a plain shell after step 1 sends `Bearer ` (empty) and reports 401 — a
  correctly-provisioned node looking broken. `with-env.sh` is the canonical
  loader (`env.shared` → tier files → `.env` overlays, then `exec "$@"`), and
  the same one the Makefile sources at `pmoves/Makefile:144`.
* **Every `curl` is bounded by `-m`.** In the fail-open posture `/mcp/sse`
  returns a live event stream and an unbounded `curl` inside `$( )` never
  returns — measured, it had to be killed by an outer `timeout 12` (exit 124).
  With `-m 3` curl exits 28 but `%{http_code}` still reports the status, which
  is all this matrix needs. The two 200 rows are also slow: a fail-open
  `/api/memory/search` reaches the real backend and took **20.0s** here, against
  ~1ms for every 401, so `-m 30` is the floor for those, not decoration.

```bash
bash pmoves/scripts/with-env.sh bash -s <<'PROBE'
C=http://localhost:8105
S="$C/api/memory/search?q=test"
p() { printf '%-24s -> %s\n' "$1" "$2"; }
p 'no header'           "$(curl -s -o /dev/null -m 30 -w '%{http_code}' "$S")"
p 'empty bearer'        "$(curl -s -o /dev/null -m 30 -w '%{http_code}' -H 'Authorization: Bearer ' "$S")"
p 'wrong token'         "$(curl -s -o /dev/null -m 30 -w '%{http_code}' -H 'Authorization: Bearer wrong' "$S")"
if [ -n "${CIPHER_API_TOKEN:-}" ]; then
  p 'right token+agentId' "$(curl -s -o /dev/null -m 30 -w '%{http_code}' -H "Authorization: Bearer $CIPHER_API_TOKEN" "$S&agentId=bootstrap")"
else
  p 'right token+agentId' 'SKIPPED - CIPHER_API_TOKEN not in this shell'
fi
p 'GET /mcp/sse, none'  "$(curl -s -o /dev/null -m 3 -w '%{http_code}' -H 'Accept: text/event-stream' "$C/mcp/sse")"
p 'GET /health'         "$(curl -s -o /dev/null -m 5 -w '%{http_code}' "$C/health")"
PROBE
```

Real output from B850 mid-provisioning (token set, container not yet recreated —
state C of §2a), which is also what the block looks like when it is working:

```
no header                -> 200
empty bearer             -> 200
wrong token              -> 401
right token+agentId      -> 401
GET /mcp/sse, none       -> 200
GET /health              -> 200
```

| Probe | Fail-open (unset) | Enforcing (set) |
|---|---|---|
| no Authorization header | **200** | **401** |
| `Bearer ''` (empty) | **200** | **401** |
| `Bearer <wrong>` | 401 | 401 |
| `Bearer <correct>` + `agentId=bootstrap` | 200 | 200 |
| `GET /mcp/sse` no header | 200 | **401** |
| `GET /health` | 200 | 200 ← **useless as a signal** |

`Bearer <wrong>` returns 401 in *both* postures, so it is not a discriminator
either. **The discriminating probe is a request with NO header.**

## 4. Setting the token CHANGES THE REQUIRED REQUEST SHAPE on REST

This is the part that breaks callers. `dist/pmoves/memory-routes.js` has a **live**
`assertAgentId(req, argsAgentId)` that activates only once `req.agentId` is set by
the middleware — i.e. only once a token is in play. Measured:

```
correct token, NO agentId           -> 400 {"error":"agentId is required when a token is present"}
correct token, agentId=bootstrap    -> 200 {"results":[]}
correct token, agentId=someone-else -> 403 Forbidden: token belongs to agent 'bootstrap'
correct token, agentId=*            -> 403 Forbidden: cross-agent wildcard search is not allowed
```

**Every REST caller of `/api/memory/*` that omits `agentId`, or sends anything
other than `bootstrap` while using the env-var token, breaks at enablement.**
Audit callers before step 3.

## 5. What the token does NOT buy — MCP has no per-agent authorization

Do not read §4 as "cipher enforces per-agent identity everywhere." It does not.

`dist/pmoves/rest-server.js` mounts the MCP router with **two** arguments:

```js
app.use('/mcp', createMcpSseRouter(memoryManager, nats));   // auth param omitted
```

`createMcpSseRouter(memoryManager, nats, auth = {})` therefore receives `auth = {}`,
so `authAgentId` is `undefined` and **both** guards inside `mcp-sse.js`'s own
`assertAgentId` are short-circuited by their leading `if (authAgentId && ...)`.
That function cannot throw. Confirmed at source **and** in the running image.

All 10 MCP tools take `agentId` from **caller-supplied arguments**. So on the MCP
surface the token gates *access to the service*; it does **not** prevent an
authenticated caller from acting as any agent. Per-agent authorization exists on
the REST path only.

## 6. The client-side half — do not enable the token without this

Setting the token 401s every MCP client that does not present it, and Claude Code
surfaces **no error** for an MCP server it cannot reach; it simply offers no tools.

`.claude/mcp.json` uses a bare `${CIPHER_API_TOKEN}` (the `:-` default was removed
2026-09-02). The reason is observability. Against an **enforcing** server:

| roster form | var present | var absent/empty |
|---|---|---|
| `${CIPHER_API_TOKEN:-}` | real token, 200 | `Bearer ` → 401, `session_check` says `!` |
| `${CIPHER_API_TOKEN}` | real token, 200 | literal → 401, `session_check` says `x` |

`mcp_roster_normalize.expand()` records a miss only for a reference with **no
default**, and treats an exported-but-empty value as missing, so only the bare
form reaches the `_pmoves_roster_verdicts` degraded list.

**Do not oversell this.** The gain is real but narrower than "silent → auditable":

* The `:-` failure was **not** invisible. `pmoves/scripts/session_check.py`
  already has a purpose-built classifier for it (`classify()`, the `soft` class,
  whose docstring names this exact node-dependent disagreement). Measured with
  the token absent: the old roster reports `! pmoves-cipher CIPHER_API_TOKEN`
  under "RESOLVES TO EMPTY"; the new one reports `x pmoves-cipher` under
  "UNRESOLVABLE". The change is a **severity upgrade `!` → `x` in a
  manually-run tool**, not the creation of a signal from nothing.
* `_pmoves_roster_verdicts` **has no reader today.** `git grep` finds the key at
  `pmoves/tools/mcp_roster_normalize.py:80` (writer) plus tests and prose — no
  production consumer. The launcher deliberately exports `PMOVES_MCP_ROSTER`
  pointing at the **raw** roster (`claude-pmoves.sh:218`), not the normalized
  payload, so `session-check` never sees the verdicts block either. Wiring a
  reader is a **follow-up lane**, not something this change already delivers.
  Until then the durable channel is `make -C pmoves session-check`, run by hand.

Sessions must start through `deploy/provision/claude-pmoves.sh`, which sources
`env.shared` and auto-exports every key.

**A bare `claude` session does not show cipher as degraded — it has no cipher at
all.** This repo has no `.mcp.json`; `.claude/mcp.json` is loaded only via the
launcher's `--mcp-config`. Measured 2026-09-02: `claude mcp list` from a bare
session returns 14 servers, **none of them PMOVES** — no `pmoves-cipher`, no
`pmoves-cipher-local`, no `agent-zero`. A bare session never runs the normalizer,
so no verdict is produced. Cipher is absent, not degraded. Use the launcher.

### 6a. Fleet consequence — this roster change goes live everywhere on merge

`deploy/provision/claude-pmoves.sh:181-207`: unless `PMOVES_ROSTER_FROM_TREE` is
set (it is not, by default), the launcher runs

```sh
git -C "$ROOT" show origin/main:.claude/mcp.json > "$_main_roster"
```

and hands **that** to Claude. So the roster a session gets is whatever is on
`origin/main`, regardless of which branch the node has checked out. Merging this
PR therefore changes behaviour on **every node at once**, not when a node next
pulls. `env.shared` and the tier files are per-node and untracked, so a node that
has never run §2 step 1 keeps `CIPHER_API_TOKEN` unset — state B of §2a: 200
today, 401 after the merge.

Mitigating, and measured against `origin/main` rather than assumed: the bare form
is **already the majority**. On `origin/main` today it is in `.kimi/mcp.json`, all
**7** Hermes profiles (`4090, 5090, b850, elder-melchor, kvm4-1, spark, z890`, two
entries each), all **8** `pmoves/configs/claws/opencode-*.json`, all **9**
`pmoves/configs/claws/scopes/*.json`, and `.claude/CATALOG.md`. Those clients
already 401 on a token-less node. This change brings claude-code, kilo and crush
into line with the majority; it does not invent a new failure mode, and the set of
nodes it can newly break is bounded by "nodes running claude-code or crush with no
token".

**Per-node remedy — one Known Road, no raw env edits:**

```bash
# on each node, in the repo root
bash pmoves/scripts/with-env.sh bash -c \
  '[ -n "${CIPHER_API_TOKEN:-}" ] && echo "provisioned (len=${#CIPHER_API_TOKEN})" || echo MISSING'
# if MISSING, run §2 steps 1-3 on that node, then verify with §3.
```

`CIPHER_API_TOKEN` is **already registered** as a manifest entry
(`pmoves/chit/secrets_manifest.yaml` id `cipher_api_token`, and
`pmoves/tools/chit_manifest_register.py`, tier `agent`, `required: false`), so the
funnel routes it into `env.tier-agent` wherever the node's CGP bundle carries it.
Registration handles **propagation**, not **minting**: a node whose bundle has no
value still needs step 1. Do not read the manifest row as fleet-wide provisioning.

## 7. Rollback

```bash
python pmoves/scripts/bootstrap_env.py --clear CIPHER_API_TOKEN
make -C pmoves chit-export && make -C pmoves secrets-funnel && make -C pmoves up-cipher
```
This returns the service to fail-open (`skipIfUnset` defaults **true**). Treat that
as an incident state, not a resting state.

## 8. Related

- `.claude/CATALOG.md` — Cipher Memory service entry
- `pmoves/docs/TAC/TAC_CIPHER.md` — architecture decision
- `.kilo/command/cipher-village-pr-2-per-agent-tokens.md` — per-agent token lane
- `pmoves/tools/mcp_roster_normalize.py` — roster expansion + verdict recording
