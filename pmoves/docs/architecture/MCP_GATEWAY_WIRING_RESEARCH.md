# MCP Gateway wiring for PMOVES.AI — research findings

**Status:** research complete; substrate chosen (§5). Superseded recommendation kept visible, not deleted.
**Date:** 2026-08-20 · **Node:** B850 · **Scope:** how every PMOVES service that speaks MCP gets registered in one gateway reachable by all agents.

---

## 0. The ask

> every service that has mcp needs that mcp registered in gateway; that gateway needs to be reachable by all agents … we have `PMOVES-BotZ-gateway` and the e2b stack which has mcp docker in it … it does not need to be the kubernetes fan-out.

Two of those three are satisfiable today. The third — using `PMOVES-BotZ-gateway` **without** Kubernetes — is not, for a structural reason worth knowing before anyone starts building. That is §2.

---

## 1. What actually exists

Three containers run today with "botz" in the name, and they are three different systems:

| container | port | what it is |
|---|---|---|
| `pmoves-botz-mcp-bridge` | 8100 | **The real MCP server.** 23 tools, JSON-RPC on `POST /mcp`. From `PMOVES-BoTZ/docker-compose.yml`. |
| `pmoves-botz-gateway` | 2091 | `pmoves-botz-python-gateway` image, from the same compose. |
| `pmoves-botz-gateway-1` | 8054 | **The shim.** `pmoves/services/botz-gateway` — a BoTZ CLI work-item coordinator. Not an MCP server. |

The bridge's 23 tools: `hirag_query`, `hirag_similarity`, `hirag_graph`, `hirag_health`, `nats_publish`, `nats_request`, `nats_subjects`, `nats_health`, `tensorzero_chat`, `tensorzero_embed`, `tensorzero_providers`, `tensorzero_health`, `supabase_query`, `supabase_insert`, `supabase_rpc`, `supabase_tables`, `supabase_health`, `cast_discover`, `cast_list`, `cast_speech`, `cast_audio`, `cast_status`, `cast_stop`.

**No GitHub tools.** This matters — see §3.

`PMOVES-BotZ-gateway` (the submodule) is Microsoft's **MCP Gateway**. It is referenced by **zero** compose files in this repo. It is not deployed anywhere.

---

## 2. Why Microsoft's gateway cannot federate: it deploys, on Kubernetes

The gateway has no way to register an MCP server that already exists. Everything it manages, it **launches from a container image**.

- `Management/src/Contracts/AdapterData.cs` — `ImageName` and `ImageVersion` are `required`. An adapter *is* an image.
- `Management/src/Contracts/ToolData.cs` — `ToolData : AdapterData`, so `/tools` inherits the same requirement.
- `Management/src/Service/ToolManagementService.cs:18` — *"Tools are deployed the same way as adapters"*; line 72 calls `_deploymentManager.CreateDeploymentAsync(...)`.
- `Management/src/Deployment/` — `IAdapterDeploymentManager` has exactly **one** implementation: `KubernetesAdapterDeploymentManager`.
- `Service/src/Program.cs:28` — `IKubernetesClientFactory → LocalKubernetesClientFactory`. The README's "local deployment" means a **local Kubernetes cluster**, not "no Kubernetes".
- `Service/src/Program.cs:30` — `IServiceNodeInfoProvider → AdapterKubernetesNodeInfoProvider`. A second Kubernetes dependency, used for session-affinity routing.

So the appealing shape — *point the gateway at `hi-rag-gateway-v2:8086` and `botz-mcp-bridge:8100` and let it route* — **is not expressible in this codebase**. There is no endpoint field to put a URL in.

What agents *would* call once servers are registered is a single, uniform route:

```
POST /adapters/{name}/mcp        # AdapterReverseProxyController.cs:35
```

That part is exactly what we want. It is only the registration side that assumes it owns the lifecycle.

---

## 3. Why the current wiring is dead

`github-issue-triage` builds `GitHubMCPClient(BOTZ_MCP_URL)`, default `http://botz-gateway:8102`. Four independent breaks:

1. **Wrong host and port.** The shim binds 8054 (Dockerfile `EXPOSE`, `CMD --port`, uvicorn, compose mapping, healthcheck all agree). The MCP bridge is a *different container* on 8100. Nothing binds 8102 there.
2. **Routes do not exist.** The client calls `/mcp/github/add_labels` and `/mcp/github/get_issue`. The shim exposes 16 routes, none under `/mcp/*`. The bridge 404s both — it speaks JSON-RPC on `POST /mcp`, not REST.
3. **No GitHub tools exist anywhere.** See the list in §1.
4. **Credentials are ignored.** Compose injects `GH_APP_ID` / `GH_APP_SEC` / `GH_APP_INSTALLATION_ID` into the shim under the comment *"GitHub App credentials — MCP GitHub server token minting"*. `pmoves/services/botz-gateway/main.py` never reads them.

It *looks* wired because compose declares `depends_on: botz-gateway: condition: service_healthy`, and that dependency genuinely resolves — the shim's 8054 healthcheck passes. The dependency is real; the capability behind it is not. No test covers the wiring.

The client is at least honest: it logs and increments `triage_error_total{error_type='mcp_call'}`. The failure is observable. It has not been observed.

---

## 4. Why the shims exist

**13 of 71 submodules are uninitialized** on this checkout (`git submodule status`, leading `-`), including `PMOVES-MiniMax-MCP` (0 files).

That is not cosmetic. `.claude/mcp.json` registers MiniMax as `uvx minimax-mcp==0.0.18` — from PyPI — and its own note says the pin *"matches the audited PMOVES-MiniMax-MCP gitlink f4d6a61b"*. The gitlink was audited; the working tree was never populated; the registration routes around the submodule. Same shape as the `botz-gateway` shim standing in for a gateway that was never deployed.

Any wiring effort that starts before submodule init is fixed will produce more of these.

### Registration inventory

| MCP surface | ships a Dockerfile? | adapter-ready |
|---|---|---|
| `pmoves-e2b-mcp-server` | **yes** | yes |
| `PMOVES-jcodemunch-mcp` | **yes** | yes |
| `pmoves-cipher-mcp` | no | needs one |
| `pmoves-hirag-mcp` | no | needs one (mcp.json already notes this) |
| `PMOVES-MiniMax-MCP` | **uninitialized** | blocked on init |
| `botz-mcp-bridge` (23 tools) | in `PMOVES-BoTZ` compose | yes |
| `docling-mcp`, `vpn-mcp` | in `PMOVES-BoTZ` compose | yes |
| `hf-mcp-server` | in `pmoves` compose | yes |

`.claude/mcp.json` currently registers **15** servers. Every one is a direct client→server connection (stdio / SSE / HTTP). **None** routes through any gateway. The file says so itself: *"interim local wiring until the PMOVES MCP-gateway hub hosts it as an adapter."*

---

## 5. The substrate: Docker's own gateway, not a fork of Microsoft's

The first version of this document recommended implementing
`DockerAdapterDeploymentManager` against `IAdapterDeploymentManager` in the
Microsoft fork. **That is cancelled.** It was the right answer to the wrong
question — it assumed the Microsoft gateway was the only gateway available.

`POWERFULMOVES/PMOVES-mcp-gateway` is a fork of **`docker/mcp-gateway`**: the
`docker-mcp` CLI plugin and Docker MCP Gateway. Its README states it "can work in
Docker Desktop or independently". Its server-entry spec
(`docs/server-entry-spec.md`) defines three types — `server`, `remote`, `poci` —
and `remote` is exactly the capability §2 found missing:

| field | required | meaning |
|---|---|---|
| `remote.url` | yes | URL endpoint of an MCP server that already runs |
| `remote.transport_type` | no | e.g. `sse` |
| `remote.headers` | no | custom HTTP headers (auth) |

So `hi-rag-gateway-v2:8086`, `botz-mcp-bridge:8100` and `cipher:8105/mcp/sse` can
be federated as-is. No image, no pod, no Kubernetes, no C#.

**Both gateways are kept.** Microsoft's (`PMOVES-BotZ-gateway`) remains the
Kubernetes substrate; Docker's (`PMOVES-mcp-gateway`) is the compose-fleet
substrate. They are not competing — they target different runtimes, and §2 is the
evidence for why the split exists rather than a preference.

### Mapping the inventory onto server entries

| surface | entry type | why |
|---|---|---|
| `botz-mcp-bridge` :8100 (23 tools) | `remote` | already running, JSON-RPC on `POST /mcp` |
| `pmoves-cipher` :8105 SSE | `remote` | `transport_type: sse` + `headers` for the bearer token |
| `agent-zero` :8080/mcp | `remote` | already running |
| `cloudflare-api`, `comfy` (hosted) | `remote` | third-party HTTPS endpoints |
| `pmoves-e2b-mcp-server`, `PMOVES-jcodemunch-mcp` | `server` | ship Dockerfiles |
| `pmoves-cipher-mcp`, `pmoves-hirag-mcp`, `PMOVES-MiniMax-MCP` | `server` | need a Dockerfile first |

### Sequence

1. ~~Fix submodule init~~ — **done**. All 13 initialized; the gate that missed
   them is fixed in #2659.
2. Add `PMOVES-mcp-gateway` as a submodule — **done in this change**, tracking
   `PMOVES.AI-Edition-Hardened` (created at `main` HEAD, zero divergence),
   registered in `fork_registry.json`.
3. Author the PMOVES catalog: one server entry per surface in the table above.
4. Stand the gateway up on compose and point `.claude/mcp.json` at it — one
   endpoint for all agents, which is the actual goal.
5. Fix `github-issue-triage` (§3): a `github_*` server entry, then delete
   `BOTZ_MCP_URL`'s `:8102` default and cover it with a test.

Steps 3–5 are the remaining work. Nothing in them requires Kubernetes or a new
deployment manager.

## 5a. Best-practice review against the gateway's own docs

The first working configuration was reviewed against `docs/security.md`,
`docs/mcp-gateway.md`, `docs/profiles.md` and the shipped examples. Five
deviations were found and corrected; they are recorded because four of them
would have looked fine indefinitely.

| deviation | why it was wrong | corrected to |
|---|---|---|
| Healthcheck POSTed `tools/list` to `/mcp` with no `Authorization` | that endpoint requires a Bearer token, so the probe would have 401'd on every interval and the container would never have gone healthy | `GET /health` — 200/503, and exempted from auth by design (`auth.go:56`) |
| `/var/run/docker.sock` mounted "for future `type: server` entries" | granted the daemon socket for a capability nothing in the catalog uses. Every entry is `remote`, which starts no containers; the gateway's own remote-only example mounts the catalog and nothing else | socket removed, to be added in the same change as the first `server` entry |
| `image: docker/mcp-gateway:latest` | a floating tag on the component that authenticates every agent's MCP traffic. The repo already pins images by digest (`minio/mc@sha256:…`) | pinned by digest, resolution verified upstream |
| `DOCKER_MCP_ALLOW_INSECURE_REMOTE_URLS` under-documented | `docs/security.md` calls it "a development and test opt-out" and puts reports depending on it **out of scope** — the remote-URL boundary is off, and we own that surface | scope, what still holds, and the TLS exit written into the file |
| Secrets-engine warning unexplained | the gateway defaults to Docker Desktop's secrets API; on Docker CE that socket never exists, so the log line is permanent noise that invites a wild-goose chase | documented as expected, with the correct fix for when a server first declares `secrets:` |

Two further constraints are now recorded rather than discovered later:

* **Origin header.** Requests carrying `Origin` are accepted only from
  `localhost`/`127.0.0.1`/`::1`. Requests without one are allowed, which is how
  non-browser clients connect — so CLI and SDK agents reach the gateway across
  the fleet, while a browser-based agent on another node is rejected by that
  check, not by the token.
* **Image verification.** Signature verification is on by default for the Docker
  Hub `mcp/` namespace and verified images must be referenced **by digest**.
  That governs the future `type: server` entries, not today's `remote` ones.

On catalogs vs profiles: `docs/catalog.md` marks catalog *management* deprecated
in favour of Profiles, but Profiles must be turned on explicitly
(`docker mcp feature enable profiles`) and their MCP Registry references are
documented as "not fully implemented and not expected to work yet". With the
flag off — our case — `--catalog` is the supported path and is exactly what the
shipped `examples/remote_mcp` uses. Revisit when Profiles stabilise.

## 6. Related finding

`pmoves-botz-mcp-bridge` reported `healthy` to Docker for 5 days while answering `/healthz` with `{"status": "degraded", …, "error": "Integration health check failed: attempted relative import with no known parent package"}`. The check was a bare `urlopen()`, which only raises on transport/HTTP errors — it could not observe the field it existed to observe. Fixed in POWERFULMOVES/PMOVES-BoTZ#190.

The same blind pattern appears in **74** healthchecks across the fleet composes. **Zero** read the response body. Any service that reports a `status` field can be degraded while Docker calls it healthy.
