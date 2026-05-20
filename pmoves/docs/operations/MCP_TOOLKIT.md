# Docker MCP Toolkit — PMOVES.AI Fleet Operations Guide

> Living doc. Created 2026-05-19 on the 5090 node after the `pmoves_5090_web` profile artifact was discovered already published at `docker.io/darkxside/pmoves_5090_web:latest`. Owners: DARKXSIDE (mint), per-node CLAUDE (bootstrap), MissingLinc (validation, [[persona_missing_linc]]).

This is the operational guide for running the **Docker MCP Toolkit** across every PMOVES.AI node + sandbox surface. Read this before connecting any Claude/Cursor/Codex/etc. client to a Toolkit profile, and before adding a new MCP server to the canonical PMOVES profile.

---

## 1. What Docker MCP Toolkit is, in PMOVES vocabulary

| Toolkit term | PMOVES analog | What it actually is |
|---|---|---|
| **MCP Server** | individual capability (one tool surface) | An image or remote endpoint speaking the Model Context Protocol. Examples in our profile: `hostinger-mcp-server`, `cloud-run-mcp`, `cloudflare-graphql`, `github-official`, `dockerhub`, `context7`, `postman`. |
| **Profile** | a named PMOVES bundle of capabilities | A YAML manifest listing N servers + per-server secrets/config. Published as an OCI artifact (mediaType `application/vnd.docker.mcp.profile.v1+json`). Lives under `docker mcp profile`. |
| **Catalog** | the canonical Docker MCP server registry | `mcp/docker-mcp-catalog:latest` — public Docker-curated catalog. Profiles reference servers by name in this catalog. Custom catalogs are supported but not currently needed for PMOVES. |
| **Gateway** | the runtime that fronts a profile | `docker mcp gateway run --profile <id>` starts a gateway process exposing the profile's servers as a single MCP endpoint to a client. When Docker Desktop is running with the Toolkit enabled, the gateway runs automatically in the background. |
| **Client connection** | how Claude/Cursor/etc. picks up the gateway | `docker mcp client connect <claude-code|cursor|vscode|…> --profile <id>` writes into the client's MCP config (e.g. `.claude/mcp.json`) so it discovers all the profile's servers as a single MCP source. |

**Where the line lives:** Toolkit handles MCP server lifecycle + secrets keychain + supply-chain pinning. PMOVES handles which profile is canonical, which servers it bundles, which agents/clients connect, and how secrets reach the keychain headlessly.

---

## 2. The canonical PMOVES profile

`docker.io/darkxside/pmoves_5090_web:latest` — published, importable, mirror-of-truth for the bundle. **25 servers** as of 2026-05-19:

| # | Type | Server | Notes |
|---|---|---|---|
| 1 | image | `hostinger-mcp-server` | DNS + VPS for `pmoves.ai`, `powerfulmoves.cloud`, `cataclysmstudios.com`. Duplicates the legacy `hostinger-mcp` entry in `.claude/mcp.json` — drop the legacy entry after Lane A lands. |
| 2 | image | `openapi-schema` | OpenAPI spec tooling |
| 3 | remote | `openmesh` | |
| 4 | image | `cloud-run-mcp` | Google Cloud Run |
| 5–17 | remote | `cloudflare-{autorag,workers-builds,ai-gateway,audit-logs,browser-rendering,dns-analytics,one-casb,workers-bindings,observability,logpush,docs,container,graphql}` | OAuth-mediated. **Not headless-safe** without cached tokens — see § 5. |
| 18 | remote | `docker-docs` | |
| 19 | image | `dockerhub` | |
| 20 | image | `context7` | Library docs lookup |
| 21 | image | `github-official` | |
| 22 | remote | `gitmcp` | |
| 23 | remote | `deepwiki` | |
| 24 | remote | `cloudflare-radar` | OAuth |
| 25 | image | `postman` | API spec + workspace management |

Why these and not others: the bundle is tuned for **cloud-school + multi-site web operations** — DARKXSIDE's three managed domains (powerfulmoves.cloud, pmoves.ai, cataclysmstudios.com) plus the dev tooling (GitHub, Docker Hub, Postman) plus library reference (Context7, DeepWiki). When adding new servers, ask: does this serve the cloud-school workflow, or is it a different bundle?

Versioning: the profile's OCI tag is `:latest` today, but **pin to immutable SHA** in client configs (per the `_pinned_versions_note` in `.claude/mcp.json` — F-07 supply-chain note). Re-tag explicitly when bumping.

---

## 3. Per-node bootstrap

Every PMOVES node that wants Toolkit access runs the same two-step bootstrap. Wrapped in `make mcp-toolkit-bootstrap` (see § 7).

```bash
# 1. Confirm Docker Desktop + Toolkit are installed
docker mcp version   # expect ≥ v0.42.0 as of 2026-05-19

# 2. Pull + import the canonical PMOVES profile
docker mcp profile pull docker.io/darkxside/pmoves_5090_web:latest
docker mcp profile ls   # expect pmoves_5090_web listed
```

Then either start the gateway explicitly (`docker mcp gateway run --profile pmoves_5090_web`) or rely on Docker Desktop's auto-started gateway when the Toolkit is enabled in Desktop settings.

**Per-node status as of 2026-05-20:**

| Node | Bootstrap state | Notes |
|---|---|---|
| 5090 | ✅ Profile imported + ✅ claude-code connected | Lane A connect landed (this PR). `MCP_DOCKER` stdio gateway entry in `.mcp.json`. Restart Claude Code session to consume gateway. |
| Z890 | unknown | TODO bootstrap when next Z890 session opens |
| 4090 | unknown | TODO bootstrap during next 4090 session (per [[project_4090_active_lanes_2026_05_16]]) |
| SPARK | unknown | TODO — likely needs `docker-pass` provider since SPARK is Linux-headless |
| B850 | unknown | TODO |
| KVM4-1 / KVM4-2 / KVM2 | likely not applicable | KVMs run service workloads, not interactive Claude sessions — Toolkit only needed if a sandbox runs there |

---

## 4. Client connection

Once the profile is bootstrapped on a node, connect each client that should consume it. **Mutates the client's MCP config — get DARKXSIDE auth first per the auto-mode classifier policy.**

**Wrapped target** (preferred — pre-flights CLI + profile presence, makes pre-connect backups):

```bash
make -C pmoves mcp-toolkit-connect                # default profile pmoves_5090_web
make -C pmoves mcp-toolkit-connect PROFILE=other  # override
```

The wrapper exits non-zero with a clear message if the Toolkit CLI is missing (exit 1), the profile isn't bootstrapped on this node (exit 2), or the underlying connect command fails (exit 3).

**Where the connect actually writes** (≥ Toolkit v0.42.0): a project-scoped `.mcp.json` at the **repository root** (not `.claude/mcp.json`) for `claude-code`. The file contains host-specific env paths (`LOCALAPPDATA`, `ProgramData`, `ProgramFiles` on Windows; different on Linux/macOS) and is **gitignored** — each node generates its own. The pre-existing `.claude/mcp.json` is **not modified** by the Toolkit connect; the legacy entries (`pmoves-cipher` SSE, `docker` mcp/docker stdio, `hostinger-mcp` npx, `tailscale` npx, `pmoves-nats-fleet` uv) coexist with the new `MCP_DOCKER` stdio gateway entry in `.mcp.json`. Claude Code merges both files at startup.

**Direct invocation** (for reference / non-PMOVES contexts):

```bash
# Per-repo (recommended for project-scoped agents)
cd /path/to/PMOVES.AI && docker mcp client connect claude-code --profile pmoves_5090_web

# System-wide (every Claude Code session on this node)
docker mcp client connect claude-code --profile pmoves_5090_web --global
```

Same pattern for `cursor`, `vscode`, `codex`, `gemini`, `crush`, `cline`, `continue`, `goose`, `gordon`, `kiro`, `lmstudio`, `opencode`, `sema4`, `zed`, `claude-desktop`. Run `docker mcp client ls` to see current connection state per client per repo.

**Disconnect / cleanup:** `docker mcp client disconnect <client>` reverts the config change. The wrapper backs up `.mcp.json` to `.mcp.json.pre-toolkit-connect.bak` (and `.claude/mcp.json` to `.claude/mcp.json.pre-toolkit-connect.bak`) on first invocation — both backup files are gitignored.

**Post-connect verification:**

```bash
# Confirm client shows connected with the gateway entry
docker mcp client ls

# Inspect the new .mcp.json (host-specific paths expected)
cat .mcp.json | jq .mcpServers

# Restart Claude Code to consume the gateway (per Toolkit prompt)
# Then verify the tool surface
docker mcp tools ls
```

**Post-connect dedup notes** (left additive in this PR — call out for future cleanup):
1. The legacy `hostinger-mcp` entry in `.claude/mcp.json` (npx hostinger-api-mcp) duplicates the bundled `hostinger-mcp-server` from the profile. Keep both (additive, ~2× tool surface but namespaced) OR remove the legacy entry (cleaner). Decide in a follow-up PR after a few sessions of mixed usage.
2. The legacy `docker` entry (`mcp/docker` stdio) overlaps with Toolkit's auto-gateway. Toolkit exposes `dockerhub` + `docker-docs` via the profile; the legacy entry's narrow scope (just `mcp/docker`) may still be useful in headless-but-no-Toolkit deployments.
3. The three independent entries — `pmoves-cipher` (SSE local), `tailscale` (npx), `pmoves-nats-fleet` (uv local) — stay; they're not in the profile.

---

## 5. Secrets handling (the headless gap)

`docker mcp secret ls` reveals secrets are stored under three providers:

| Provider | What | Headless-safe? |
|---|---|---|
| `docker-pass` | API-key style (Hostinger token, GitHub PAT, DockerHub PAT, Discord token, …) | **Yes** — `docker mcp secret set NAME` accepts STDIN. PMOVES `secrets-funnel` can populate non-interactively. |
| `docker-desktop-mcp-oauth` | OAuth access tokens (Cloudflare suite) | **No** — requires browser-mediated initial flow. Token cache can be ported between nodes if file-based. |
| `docker-desktop-mcp-dcr` | Dynamic Client Registration tokens (OAuth pairing artifacts) | **No** — same as oauth. |

**PMOVES bridge** (`make mcp-toolkit-secrets-sync`, see § 7):

The bridge reads `pmoves/env.shared` by default (the canonical aggregate the secrets-funnel produces). Override with `PMOVES_TIER_FILE=pmoves/env.tier-agent` (or any other tier) when syncing a subset. The script resolves its default path relative to its own location, so `make -C pmoves mcp-toolkit-secrets-sync` and direct invocation from repo root both work. It maps known PMOVES env names to Toolkit secret names:

| PMOVES env | Toolkit secret name | Provider |
|---|---|---|
| `HOSTINGER_API_KEY` | `hostinger-mcp-server.api_token` | docker-pass |
| `GITHUB_PAT` / `GITHUB_TOKEN` | `github.personal_access_token` | docker-pass |
| `DOCKERHUB_PAT` | `dockerhub.pat_token` | docker-pass |
| `DISCORD_TOKEN` | `discord.token` | docker-pass |
| (postman API key — TBD when adding) | `postman.api_key` | docker-pass |

Cloudflare's 13 OAuth-mediated servers need a one-time browser-mediated `docker mcp oauth authorize cloudflare-<service>` per node, OR a cached-token export from a paired node. Document the choice per-deployment.

**Anti-pattern:** never paste secrets in chat; never bake them into the OCI profile artifact ([[vision_secrets_pipeline_never_chat]]). The profile is shareable; the secrets fill in headlessly per-node.

---

## 6. E2B + sandboxed agents

**Architecture decision (2026-05-20): D-Proxy.** Rather than installing the full Toolkit inside every sandbox, the canonical pattern is:

1. **5090 host** runs the gateway in SSE mode on a network port: `make -C pmoves mcp-toolkit-gateway-start` (calls `pmoves/scripts/mcp-toolkit-gateway-listen.sh --background`).
2. **Sandboxes** receive `MCP_GATEWAY_URL` + `MCP_GATEWAY_AUTH_TOKEN` via `Sandbox.create({envs: {...}})` and connect to the host gateway over HTTPS+SSE.
3. Secrets stay on the host where the secrets-funnel already runs. Sandboxes never see API keys directly — they ask the gateway, the gateway invokes the tool image with the secret injected, the tool returns the result.

Why D-Proxy and not Docker-in-Docker (D-Inside):
- Sandbox image stays small (no Docker daemon, no Toolkit CLI)
- Faster `Sandbox.create()` cold start
- Single secrets-management surface (host, not host-per-sandbox)
- Trades a small isolation property (sandbox can call tools but can't inspect them) for a large operational simplification

### Host gateway listener (this PR adds these)

| Target | What it does |
|---|---|
| `make mcp-toolkit-gateway-start` | Runs `docker mcp gateway run --profile pmoves_5090_web --transport sse --port 8090` in the background (PID file `/tmp/pmoves-mcp-gateway.pid`, log `/tmp/pmoves-mcp-gateway.log`). Generates and persists `MCP_GATEWAY_AUTH_TOKEN` to `env.shared` on first run. |
| `make mcp-toolkit-gateway-stop` | SIGTERM → 10s grace → SIGKILL, cleans up PID file. |
| `make mcp-toolkit-gateway-tail` | `tail -f` on the gateway log. |

Overrides:
- `PMOVES_MCP_GATEWAY_PORT` — listen port (default 8090)
- `PMOVES_MCP_GATEWAY_TRANSPORT` — sse / stdio / streaming (default sse)
- `PMOVES_MCP_BLOCK_NETWORK=1` — adds `--block-network` to forbid tool containers from arbitrary outbound (defense-in-depth; safe default is 0 because most servers in `pmoves_5090_web` need outbound to call Cloudflare/Hostinger APIs)

### Security model

- **SSE auth token** — `MCP_GATEWAY_AUTH_TOKEN` (32-byte hex, auto-generated) prevents DNS rebinding attacks per upstream Docker docs. Persisted to `env.shared`; clients (E2B sandboxes, BoTZ Gateway, Danger Room Desktop) read the same value.
- **`--block-secrets` default on** — secret values cannot exfil through tool args/responses (upstream Toolkit default).
- **Bind interface** — for production, prefer binding to a Tailscale interface rather than `0.0.0.0`. Operator-configurable via `PMOVES_MCP_GATEWAY_HOST` (not yet wired; TODO when fleet rollout starts).
- **Image signature verification** — `--verify-signatures` available but not enabled in this PR. Add via env override when supply-chain audit is tightened.

### Sandbox-side consumption (next PR — Lane D-sandbox)

Pseudocode for the sandbox bootstrap script (lands when `PMOVES-E2B-Danger-Room-Desktop` is customized):

```python
sandbox = Sandbox.create(envs={
    "MCP_GATEWAY_URL": "https://pmoves-5090.tail-scale.ts.net:8090/mcp/sse",
    "MCP_GATEWAY_AUTH_TOKEN": os.environ["MCP_GATEWAY_AUTH_TOKEN"],
})
sandbox.commands.run("/usr/local/bin/pmoves-mcp-client-bootstrap.sh")
```

The bootstrap script inside the sandbox writes a Claude/MCP client config pointing at `$MCP_GATEWAY_URL` and discovers the 25-server tool surface automatically.

---

## 6.x [PRIOR DESIGN — preserved for context]

Upstream Docker docs note: **"E2B sandboxes now include direct access to the Docker MCP Catalog."** What this means for PMOVES:

1. E2B sandbox templates can pull + import the `pmoves_5090_web` profile during startup using the same two-step bootstrap as § 3.
2. Secrets bridge runs inside the sandbox via `docker mcp secret set` STDIN, sourced from sandbox-injected env (NOT baked into the template image).
3. The sandbox's `docker mcp gateway run --profile pmoves_5090_web` starts the gateway; the agent inside the sandbox connects its MCP client to it.

**Open implementation gap** (Lane D, not in this PR): our `PMOVES-E2B-Danger-Room` submodule is still vanilla upstream (README is unchanged from upstream). The PMOVES customization (template Dockerfile + startup hook running the bootstrap + secrets bridge) is the next step. See [[platform_activation_session_2026_05_19_mcp_toolkit]] when it lands.

**Danger Room Desktop on Linux** (Lane F, also future): E2B Desktop supports custom Dockerfile-based templates. A PMOVES-base template (Pop!_OS or Ubuntu LTS) with Toolkit + profile + secrets pre-wired gives every Computer-Use session immediate access to the 25-server tool surface. Track as a separate doc when designed.

---

## 7. PMOVES Make targets

| Target | What it does |
|---|---|
| `make mcp-toolkit-bootstrap` | Verifies `docker mcp` CLI present, pulls `pmoves_5090_web` profile from OCI, imports it. Idempotent. Per-node. |
| `make mcp-toolkit-secrets-sync` | Reads `pmoves/env.shared` (override via `PMOVES_TIER_FILE`), populates `docker-pass`-style Toolkit secrets non-interactively. Skips OAuth-style servers (see § 5). |
| `make mcp-toolkit-status` | `docker mcp profile ls && docker mcp client ls && docker mcp secret ls` + gateway PID — single-shot health. |
| `make mcp-toolkit-gateway-start` | Run gateway in SSE on a network port (background). See § 6 for security model. |
| `make mcp-toolkit-gateway-stop` | Graceful stop + force-kill fallback. |
| `make mcp-toolkit-gateway-tail` | `tail -f` the gateway log. |
| Target | What it does | Added by |
|---|---|---|
| `make mcp-toolkit-bootstrap` | Verifies `docker mcp` CLI present, pulls `pmoves_5090_web` profile from OCI, imports it. Idempotent. Per-node. | PR #1553 |
| `make mcp-toolkit-secrets-sync` | Reads `pmoves/env.shared` (override via `PMOVES_TIER_FILE`), populates `docker-pass`-style Toolkit secrets non-interactively. Skips OAuth-style servers (see § 5). | PR #1553 |
| `make mcp-toolkit-connect` | Pre-flights CLI + profile presence, backs up pre-existing `.mcp.json` and `.claude/mcp.json`, runs `docker mcp client connect claude-code --profile $(PROFILE)`. Override profile: `PROFILE=<name>`. Writes a project-scoped `.mcp.json` (gitignored, host-specific env paths). | This PR (Lane A) |
| `make mcp-toolkit-status` | `docker mcp profile ls && docker mcp client ls && docker mcp secret ls` — single-shot health. | PR #1553 |
>>>>>>> 3fb2336e4 (feat(mcp): wrap docker mcp client connect as `make mcp-toolkit-connect` (Lane A))

Targets live in `pmoves/Makefile`. Scripts live in `pmoves/scripts/mcp-toolkit-*.sh`.

---

## 8. BoTZ Gateway relationship

`PMOVES-BotZ-gateway/openapi/mcp-gateway.openapi.json` defines a REST `POST /adapters {name, imageName, imageVersion}` API for registering MCP servers. **Decision deferred** until DARKXSIDE chooses between two integration models:

- **(a) BoTZ Gateway is the entry point**, internally invoking `docker mcp profile server add` or running `docker mcp gateway run` under the covers. Multi-agent fan-out happens at BoTZ Gateway; Toolkit is an implementation detail.
- **(b) Toolkit Gateway is the entry point**, BoTZ Gateway becomes a thin auth/audit shim in front of it (or is retired in favor of native Toolkit gateway tooling).

Either way: this PR doesn't lock in the choice. Document explicitly when picked.

---

## 9. Supply-chain pinning

The `.claude/mcp.json` header comment (`_pinned_versions_note`, dated 2026-05-14) is the canon discipline: pin every MCP server to an exact version (or SHA digest), audit before bumping. Applied to Toolkit:

- **Toolkit CLI version**: pin in `pmoves/scripts/mcp-toolkit-bootstrap.sh` — current minimum is `v0.42.0`. Bootstrap exits non-zero if the local version is below the floor.
- **Profile artifact**: pin to `pmoves_5090_web@sha256:<digest>` once stable. The OCI manifest digest is what protects against rug-pull on `:latest`.
- **Per-server images**: profile YAML already pins `mcp/hostinger-mcp-server@sha256:...`, `mcp/context7@sha256:...`, etc. — preserved by `docker mcp profile pull`.
- **Catalog**: pin `mcp/docker-mcp-catalog:latest` similarly when bumping.

When updating the profile, bump SHAs in one commit, mirror them in this doc's § 2 table, and rebuild the OCI artifact.

---

## 10. Living-doc reconcile

Lives in `pmoves/configs/living_docs_registry.yaml` (TODO: register after first PR merges). Reconcile signal: `docker mcp profile show pmoves_5090_web | grep -c '^    - type:'` should match § 2's server count; if not, this doc is stale.

---

## 11. Cross-references

- [[vision_secrets_pipeline_never_chat]] — secrets must flow through env.tier-* → secrets-funnel, never chat
- [[feedback_node_identity_verify_first]] — verify which node before signing AGNOTE on Toolkit changes
- [[persona_missing_linc]] — MissingLinc validator persona, primary consumer of the Cloudflare/Hostinger forensic surface
- [[project_z890_claude_submodule_worktree_lane]] — submodule pin promotion for E2B integration belongs to Z890-CLAUDE lane
- [[vision_5090_claude_max_level_inventory]] — 5090-CLAUDE is the primary developer of this fleet primitive
- Upstream: `docs.docker.com/ai/mcp-catalog-and-toolkit/`, `docs.docker.com/ai/mcp-gateway/`
