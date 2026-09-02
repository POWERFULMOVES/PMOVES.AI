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

## 3. Verification — the only reliable test

Run all five. `q` is the search parameter name (not `query`).

```bash
C=http://localhost:8105
printf 'no header  -> %s\n' "$(curl -s -o /dev/null -w '%{http_code}' "$C/api/memory/search?q=test")"
printf 'wrong tok  -> %s\n' "$(curl -s -o /dev/null -w '%{http_code}' -H 'Authorization: Bearer wrong' "$C/api/memory/search?q=test")"
printf 'right tok  -> %s\n' "$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $CIPHER_API_TOKEN" "$C/api/memory/search?q=test&agentId=bootstrap")"
printf 'mcp, none  -> %s\n' "$(curl -s -o /dev/null -w '%{http_code}' -H 'Accept: text/event-stream' "$C/mcp/sse")"
printf 'health     -> %s\n' "$(curl -s -o /dev/null -w '%{http_code}' "$C/health")"
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
2026-09-02). The reason is observability, and it is measured:

| roster form | var present | var absent/empty |
|---|---|---|
| `${CIPHER_API_TOKEN:-}` | real token, 200 | `Bearer ` → **401, recorded nowhere** |
| `${CIPHER_API_TOKEN}` | real token, 200 | literal → **401, recorded as `degraded`** |

`mcp_roster_normalize.expand()` records a miss only for a reference with **no
default**, and treats an exported-but-empty value as missing. So the bare form is
what puts the failure into the `_pmoves_roster_verdicts` block instead of losing it.

Sessions must start through `deploy/provision/claude-pmoves.sh`, which sources
`env.shared` and auto-exports every key. A session started as bare `claude` will
not have the variable and will now show cipher as **degraded** rather than silently
tool-less.

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
