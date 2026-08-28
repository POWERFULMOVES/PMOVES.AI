# Docker MCP Toolkit — PMOVES.AI Fleet Operations Guide

> Living doc. Created 2026-05-19 on the 5090 node after the `pmoves_5090_web` profile artifact was discovered already published at `docker.io/darkxside/pmoves_5090_web:latest`. Owners: DARKXSIDE (mint), per-node CLAUDE (bootstrap), MissingLinc (validation, [[persona_missing_linc]]).

This is the operational guide for running the **Docker MCP Toolkit** across every PMOVES.AI node + sandbox surface. Read this before connecting any Claude/Cursor/Codex/etc. client to a Toolkit profile, and before adding a new MCP server to the canonical PMOVES profile.

---

## 0. Topology — the KVM gateway is primary, Docker Desktop is the fallback

**Refreshed 2026-08-28.** Sections 2-4 below still describe the per-node Docker
Desktop bootstrap as though it were the whole story. It is not. It is the
FALLBACK, and it is the one that breaks.

| Layer | Role | Status |
|---|---|---|
| **KVM-hosted gateway** | **PRIMARY.** One self-hosted endpoint every node reaches over the tailnet, so a node needs no local Toolkit to have MCP. | **NOT YET DEPLOYED** — verified 2026-08-27, no MCP server runs on any KVM VPS (25+ ports probed across kvm2, kvm4-1, kvm4-2). See `pmoves/docs/handoffs/infra_mcp_hosting_analysis_2026-08-27.md`. |
| **Docker Desktop Toolkit** | **FALLBACK / workstation dev.** Per-node, per-operator, needs a GUI. | Live on the workstation nodes. This is what sections 2-4 document. |
| **Direct CLI + MCP** | Hostinger, Cloudflare and Tailscale are reachable directly, with their own CLIs and MCP servers. | Live. Does not depend on either gateway. |

**Why KVM primary.** The Toolkit gateway is a workstation product: it needs
Docker Desktop, a logged-in desktop session, and a per-node secret keychain that
is a per-node point of failure (see § 5.1 — it wedged on the 4090 on 2026-08-28
and survived a full Desktop restart). A KVM-hosted gateway is reachable by every
node including the arm64 and headless ones, is provisioned by the same funnel
that provisions everything else, and does not require anyone to be logged into a
GUI for an agent to have tools.

**Placement, from the 2026-08-27 capacity probe** (do not re-derive; re-measure
before acting on it):

- **kvm4-1 — best fit for the fleet-facing gateway.** 8C/16GB with roughly 6GB
  usable headroom, already the API/agent tier, egress-separated.
- **kvm2 — right host for light public SSE surfaces** behind its nginx; it has
  the most free RAM (~7.5GB).
- **kvm4-2 — add nothing.** Over-subscribed: ~29GB of declared container limits
  on a 16GB host. Fix that before it hosts anything else.

**Which gateway to clone.** The substrate decision is already made: the **Docker
MCP Gateway** on port **8189** with `--static`, auth through the CHIT secrets
pipeline, per #2656 / #2665 / #2681, with a verified 23-tool bring-up. The BoTZ
MCP gateway (`:8052`) draft is **superseded for federation** — it is K8s-only and
cannot federate existing servers. New gateway work clones #2665's pipeline.

**Prerequisite that is easy to miss:** `up-mcp-gateway` depends on
`mcp-gateway-preflight`, which fails closed unless the `pmoves_pmoves_app`
network exists AND `pmoves-botz-mcp-bridge` is running — the bridge is the only
catalogued server, and the network is created by the PMOVES-BoTZ project, not
this repo. Run `make -C pmoves up-botz-mcp-bridge` FIRST. `pmoves/mk/infra.mk`
records why this is called out: a previous verification passed on B850 only
because that stack happened to already be up.

### 0.1 Profile naming is drifting from the topology

`docker.io/darkxside/pmoves_5090_web:latest` is the artifact every node
bootstraps to — `scripts/mcp-toolkit-connect.sh:31` and
`scripts/mcp-toolkit-bootstrap.sh:14-15` both default to it. **5090 is a node.**
So every node in the fleet runs a profile named after one workstation, and on
the 4090 that means the node's own `pmoves_4090_web` (24 servers) sits unused
while it serves the 5090's (25 servers, and the only one carrying
`github-official`).

It works — the artifact really is the shared bundle — but the name says
otherwise, and a fleet-wide bundle belongs with the fleet-wide gateway on a KVM,
not under a workstation's name. Renaming is an operator decision; this section
exists so the next reader does not mistake the current name for the intent.

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
| 4090 | ✅ Profile imported + ✅ claude-code connected | Bootstrapped 2026-07 (docker mcp v0.42.2). `MCP_DOCKER` stdio gateway in the gitignored repo-root `.mcp.json` (+ `.pre-toolkit-connect.bak` backup); **200 tools** (GitHub/DockerHub/Context7/Hostinger DNS+VPS/Cloudflare). Restart Claude Code to consume. OAuth Cloudflare servers (13/25) still need a one-time browser authorize (§5). |
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

### 5.1 Recovery — when the secret resolver wedges

**The symptom.** Everything else works and only secrets fail:

```
$ docker mcp secret ls
deadline_exceeded: Post "http://unix/resolver.v1.ResolverService/GetSecrets": net/http: timeout awaiting response headers

$ docker mcp profile ls    # OK
$ docker mcp client ls     # OK
$ docker mcp catalog ls    # OK
$ docker mcp feature ls    # OK
```

Four of five subsystems answer; only the resolver is down. Docker itself is
healthy — this is not a Docker outage.

**Why it matters more than it looks.** A server whose secret cannot be fetched
starts anyway, with an EMPTY credential env var. It then fails at call time with
a 401, in whatever tool called it, with nothing pointing back here. On
2026-08-28 that presented as "the GitHub token is missing" when the token was in
fact present in every place the funnel routes it.

**Recorded occurrences.** 2026-08-17 on the 5090 (fresh `mcp-toolkit.db`, stuck
`.mcp-toolkit-migration.lock`, after a Docker Desktop VMM/backend migration) and
2026-08-28 on the 4090. The 4090 case **survived a full Docker Desktop
restart**, so a restart alone is not the fix.

**Check for it before it bites:**

```bash
python pmoves/tools/mcp_toolkit_preflight.py --profile <id>
#   0  ready
#   1  resolver down — servers WILL start unauthenticated (it names which)
#   3  could not measure — NOT a pass
```

`make -C pmoves mcp-toolkit-gateway-start` runs this automatically and reports
non-zero as advisory. Set `PMOVES_MCP_STRICT=1` to refuse to start instead —
which is what CI and unattended bring-up should do.

**Recovery, in order:**

1. Restart Docker Desktop. Re-check with `docker mcp secret ls`. If it answers,
   go to step 4.
2. If it still wedges, the migration state is stuck: stop Docker Desktop and
   clear the stale `mcp-toolkit.db` / `.mcp-toolkit-migration.lock` under the
   Docker MCP config directory, then start it again. **Operator step** — that
   directory holds credentials and is out of scope for agents.
3. Re-check. Do not proceed while `secret ls` still times out — every write in
   step 4 goes through the same resolver.
4. Re-provision without re-typing anything:
   ```bash
   make -C pmoves docker-mcp-secrets-hydrate DRY_RUN=1   # preview
   make -C pmoves docker-mcp-secrets-hydrate             # push
   ```
   Values come from the funnel, so nothing is rotated and nothing is entered by
   hand. Add `PROFILE=<id>` to force a profile; otherwise it is discovered from
   `.mcp.json`, then `PMOVES_MCP_PROFILE_ID`.
5. Re-run the preflight. Expect exit 0.

**What hydrate does NOT cover:** the 13 Cloudflare servers are OAuth-mediated,
not API-key. They need a one-time interactive `docker mcp oauth authorize
<server>` per node and will still show unauthenticated after any hydrate. That
is expected, not a regression.

**If a secret is reported as a funnel gap** rather than pushed, the key exists in
the map but has no value on this node. `GITHUB_PAT` materializes into
`env.tier-agent`, and the hydrator reads the `env.shared` aggregate, so a stale
aggregate can hide a populated key — point it at the tier file to tell the two
apart:

```bash
python pmoves/tools/docker_mcp_secrets_hydrate.py --dry-run --env-shared pmoves/env.tier-agent
```

Only a value missing from BOTH needs `secrets-rotate`.

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
| `make mcp-toolkit-bootstrap` | Verifies `docker mcp` CLI present, pulls `pmoves_5090_web` profile from OCI, imports it. Also writes Kimi + KiloCode configs for the native PMOVES MCP stack. Idempotent. Per-node. |
| `make mcp-toolkit-secrets-sync` | Reads `pmoves/env.shared` (override via `PMOVES_TIER_FILE`), populates `docker-pass`-style Toolkit secrets non-interactively. Skips OAuth-style servers (see § 5). |
| `make mcp-toolkit-status` | `docker mcp profile ls && docker mcp client ls && docker mcp secret ls` + gateway PID — single-shot health. |
| `make mcp-toolkit-gateway-start` | Run gateway in SSE on a network port (background). See § 6 for security model. |
| `make mcp-toolkit-gateway-stop` | Graceful stop + force-kill fallback. |
| `make mcp-toolkit-gateway-tail` | `tail -f` the gateway log. |
| `make mcp-toolkit-connect` | Pre-flights CLI + profile presence, backs up pre-existing `.mcp.json` and `.claude/mcp.json`, runs `docker mcp client connect claude-code --profile $(PROFILE)`. Override profile: `PROFILE=<name>`. Writes a project-scoped `.mcp.json` (gitignored, host-specific env paths). |
| `make mcp-config-bootstrap` | Writes Kimi + KiloCode `.kimi/mcp.json` and `kilo.json`, plus all `pmoves/configs/claws/opencode-*.json` node configs, from the canonical inventory (`pmoves/config/mcp_inventory.json`). Safe to re-run. |
| `make mcp-bootstrap` | Umbrella: Toolkit profile + native PMOVES MCP configs. Runs even when Docker Toolkit is unavailable. |
| `make mcp-bootstrap-check` | Validates the imported Toolkit profile, generated configs, and key presence. |
| `make hermes-crush-bootstrap` | Updates Hermes Agent `~/.hermes/profiles/pmoves-hermes/config.yaml` and Crush CLI `~/.config/crush/crush.json` MCP sections from the inventory. |
| `make opencode-bootstrap` | Updates all `pmoves/configs/claws/opencode-*.json` node configs with canonical PMOVES MCPs (preserves existing zai/docker entries). |

Targets live in `pmoves/Makefile` (included from `pmoves/mk/mcp-toolkit.mk`). Scripts live in `pmoves/scripts/mcp-toolkit-*.sh` and `pmoves/scripts/bootstrap-hermes-crush.sh`.

---

## 7.5. Verification fixture

`pmoves/tools/verify_pmoves_5090_web_mcp_integration.sh` runs a 5-phase end-to-end check against the canonical profile on the local node. Wrap target: `make -C pmoves mcp-toolkit-verify`.

**Phases:**

| Phase | What it checks | When it FAILs |
|---|---|---|
| **P1** | `docker mcp version` succeeds + `pmoves_5090_web` profile is imported | CLI missing or profile not bootstrapped — run `mcp-toolkit-bootstrap` |
| **P2** | `claude-code: connected` for THIS worktree's project scope (cwd-scoped per Toolkit semantics) | run `mcp-toolkit-connect` in the current worktree, OR run the fixture from a connected worktree |
| **P3** | `docker mcp tools count` > 0 — at least one tool discoverable | gateway runtime broken; check Docker Desktop + Toolkit health |
| **P4** | Host-side SSE gateway listener (PR #1555) reachable at `http://127.0.0.1:8090/sse` | run `mcp-toolkit-gateway-start` (PR #1555); P4 is gated on PR #1555 landing |
| **P5** | Round-trip a known low-side-effect tool (`context7-resolve-library-id react` by default) | gateway-broken, tool name drifted, or upstream context7 outage |

**Overrides via env / Make var:**
- `PROFILE=<name>` — verify a different profile (default `pmoves_5090_web`)
- `MCP_GATEWAY_PORT=<n>` — different gateway port (default `8090`)
- `PROBE_TOOL=<tool>` + `PROBE_TOOL_ARG=<arg>` — different round-trip probe (default `context7-resolve-library-id` + `react`)

**Exit code:** number of failed phases (0 if all PASS). SKIP'd phases don't count as failures (P1 cascades SKIP downstream when CLI absent).

**P2 substring trap (lesson learned):** `docker mcp client ls` emits `claude-code: disconnected` or `claude-code: connected`. A naive `grep -q "connected"` matches BOTH — disconnected substring contains "connected". The fixture uses `grep -qE '^[^a-zA-Z]*claude-code:[[:space:]]+connected[[:space:]]*$'` with an end-anchor to reject the false-positive. This is a general CLI-table-parsing class — see relevant feedback memory files for the broader pattern.

**P4 + P5 gateway semantics:** P3 + P5 query the global Toolkit gateway (cwd-independent), so they can PASS even when P2 reports the current worktree is disconnected. P4 specifically probes the host-side SSE listener from PR #1555 — that's distinct from the Toolkit's auto-started internal gateway. Treat P3 (internal) and P4 (Lane D-host) as independent surfaces.

**Sample output (2026-05-20 on 5090 node, before PR #1555 lands):**

```text
P1    PASS    docker mcp v0.42.0; profile 'pmoves_5090_web' present
P2    PASS    this worktree: '● claude-code: connected'
P3    PASS    66 tools available across profile servers
P4    FAIL    http://127.0.0.1:8090/sse not reachable (run: make -C pmoves mcp-toolkit-gateway-start)
P5    PASS    context7-resolve-library-id 'react' returned 79 bytes

Totals: 1 FAIL, 0 SKIP, 4 PASS
```

P4 will pass once PR #1555 merges and `make mcp-toolkit-gateway-start` is run on this node.

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
