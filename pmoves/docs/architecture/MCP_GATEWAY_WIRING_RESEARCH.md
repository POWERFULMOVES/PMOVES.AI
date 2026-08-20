# MCP Gateway wiring for PMOVES.AI — research findings

**Status:** research complete, implementation blocked on one decision (§5).
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

## 2. The blocker: the gateway deploys, it does not federate

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

## 5. The decision

| | approach | cost | keeps "no Kubernetes"? |
|---|---|---|---|
| **A** | Implement `DockerAdapterDeploymentManager` in the fork | 5 interface methods + a Docker `IServiceNodeInfoProvider` + a DI switch | **yes** |
| **B** | Run k3s/kind just for the gateway | zero code | no — this is the fan-out that was ruled out |
| **C** | Write a PMOVES router that mimics `/adapters/{name}/mcp` over running containers | smaller than A | yes, but it is another shim |

**Recommendation: A.**

`IAdapterDeploymentManager` is a five-method interface — `CreateDeploymentAsync`, `DeleteDeploymentAsync`, `GetDeploymentStatusAsync`, `GetDeploymentLogsAsync`, `UpdateDeploymentAsync`. All five map cleanly onto the Docker Engine API, and `AdapterData` already carries everything a Docker run needs (image, tag, env, replica count). We keep the real product — its portal, its Entra role model, its session-affinity routing, its `/adapters/{name}/mcp` contract — and swap only the substrate.

C is rejected on the grounds that produced this document: a shim that imitates a gateway is how `botz-gateway` came to be depended on by a service it cannot serve.

### Sequence

1. **Fix submodule init** (13 uninitialized) — otherwise every later step routes around a missing tree.
2. **A**: `DockerAdapterDeploymentManager` + Docker node-info provider + DI switch, in the fork.
3. **Add Dockerfiles** for `pmoves-cipher-mcp` and `pmoves-hirag-mcp` so they can be adapters.
4. **Register** each MCP surface from the §4 inventory.
5. **Repoint `.claude/mcp.json`** at `POST /adapters/{name}/mcp` — one reachable endpoint for all agents, which is the actual goal.
6. **Fix `github-issue-triage`**: either a `github_*` tool family on the bridge, or a GitHub MCP adapter. Then delete `BOTZ_MCP_URL`'s 8102 default and cover it with a test.

Step 5 is the payoff. Steps 1–2 are what make it possible.

---

## 6. Related finding

`pmoves-botz-mcp-bridge` reported `healthy` to Docker for 5 days while answering `/healthz` with `{"status": "degraded", …, "error": "Integration health check failed: attempted relative import with no known parent package"}`. The check was a bare `urlopen()`, which only raises on transport/HTTP errors — it could not observe the field it existed to observe. Fixed in POWERFULMOVES/PMOVES-BoTZ#190.

The same blind pattern appears in **74** healthchecks across the fleet composes. **Zero** read the response body. Any service that reports a `status` field can be degraded while Docker calls it healthy.
