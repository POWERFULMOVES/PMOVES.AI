# MCP Hosting to Node Capacity — DRAFT plan

**Date:** 2026-09-23
**Author:** PMOVES-4090-CLAUDE, at founder direction (DARKXSIDE)
**Lane:** `feat/mcp-node-capacity-hosting` (claimed 2026-09-23T21:57:39Z)
**Status:** DRAFT. Nothing deployed. Each phase below is a separate PR or an operator-approved action.
**Supersedes in part:** `infra_mcp_hosting_analysis_2026-08-27.md` §3. That plan pointed the fleet gateway at kvm4-1 alone. The founder's direction now is **every node hosts PMOVES to its own capacity** (kvm2 is the minimal end, not the model).

---

## 0. Founder rules this plan is built on

1. **Every node is a pore.** Each node hosts as much of PMOVES as its capacity allows. kvm2 (relay/egress, about 7.5GB free) is the floor; the GPU nodes and the 4090 are near the ceiling.
2. **Expose through the PMOVES-Tailscale fork + ScaleTail sidecars**, not by widening `*_BIND` to `0.0.0.0`.
3. **One auth path per server.** An operator should never authorize the same account twice.
4. **No change may break MCP loading for any other harness**: claude, crush, kilocode, kimi, opencode, hermes, agent-zero.
5. **Cipher is for ALL AGInTZ.** Shared memory is not any one agent's or node's service. Every harness and every drop-in model must reach it. It is in scope here and first in line.
6. **Nodes don't run different secrets.** Every bundle comes from the same repo-level GitHub secrets. B850 is the *default* producer, not the only one.

## 1. Measured state (2026-09-23, fresh main `caf03801f`)

| # | Finding | Evidence |
|---|---|---|
| F1 | The 4090's node-local `.mcp.json` ran the **5090's** Docker MCP profile (`MCP_DOCKER`, 30s timeout). Emptied on the 4090 (gitignored, node-local). | session transcript `09c544ec…`; `docker mcp profile ls` |
| F2 | `mcp-4090-gateway-start` listens on **8089** with no profile set, so it falls back to `pmoves_5090_web`; the roster's `pmoves-4090-web` expects `localhost:8090`. | `pmoves/mk/mcp-toolkit-4090.mk:12,29-32`; `scripts/mcp-toolkit-gateway-listen.sh:62-63`; `.claude/mcp.json:122` |
| F3 | `pmoves-docker-gateway-sse` sends `Bearer ${CIPHER_API_TOKEN}`, but the gateway checks `MCP_GATEWAY_AUTH_TOKEN`. The listener creates that token itself and appends it to env.shared **outside the CHIT funnel**. | `pmoves/config/mcp_inventory.json:254-265`; `listen.sh:156-176` |
| F4 | `e2b-danger-room` (clients include `claude`) and `flute-voice(-mcp)` are in the inventory but were never rendered into `.claude/mcp.json`. A generator dry run adds exactly these three. | `mcp_config_generator --client claude --dry-run` |
| F5 | Every `*_fleet_url` default is pinned to `${TS_Z890}`. Flute `:8055` is unreachable cross-node (loopback bind). | `mcp_inventory.json:3-13`; tailnet probe, all 000 |
| F6 | Cloudflare OAuth is wired **both** directly in the roster (`cloudflare-api`) and inside the Toolkit profile (`cloudflare-docs`), so it is authorized twice. Docker's OAuth store and Claude's are separate clients. | `MCP_TOOLKIT.md:94,195-212` |
| F7 | ScaleTail is a fork entry only (`fork_registry.json:503`). The "RustDesk ScaleTail sidecar" is `network_mode: host` with no tailscale container, so **no ScaleTail sidecar exists in the fleet yet**. | `deploy/docker-stacks/rustdesk-selfhosted.yml:24,45` |
| F8 | Nothing selects which services a node runs from its capacity. `compose_overrides` in profiles is only echoed. | `pmoves/tools/profile_loader.py`; `mini_cli.py:1086` |
| F9 | The generator takes one global `--endpoint local\|fleet`. Only Spark's crush configurator does "prefer local if hosted". | `mcp_config_generator.py:375,393,457`; `crush_configurator.py:655-680` |
| F0 | **Five of seven harnesses have no working Cipher path.** `pmoves-cipher` (fleet, `${TS_Z890}:8105`, no `clients` = all) is unreachable from every node but Z890, because Cipher binds loopback. `pmoves-cipher-local` (`localhost:8105`) is limited to `clients: [hermes, claude]`, so crush, kilocode, kimi, opencode and agent-zero get only the dead fleet entry. | `mcp_inventory.json` (cipher entries); `mcp_config_generator.py:67-70` (`clients: None` = all) |
| F10 | `AIRTABLE_API_KEY` / `TAVILY_API_KEY` are absent from the prod bundle too. `TENSORZERO_CLICKHOUSE_USER` masks as `CLIC...HERE`, which looks like a template placeholder. | `secrets-funnel-from-prod` + `docker-mcp-secrets-hydrate` output |

## 2. Target shape

```
            ┌─────────────── tailnet (PMOVES-Tailscale fork, ACL-tested) ───────────────┐
 node N  ──  service ─ network_mode: service:ts-<svc> ─ ts-<svc> sidecar → <svc>-<node>.<tailnet>.ts.net
            each node runs the services its capacity profile allows; loopback binds unchanged
 roster  ──  per server: local URL if hosted on THIS node, else the tailnet name of the nearest host
 auth    ──  static secrets: CHIT funnel → env / Docker secret store (one hydrate)
             OAuth: exactly ONE client owns each account (roster OR gateway, never both)
```

**Why sidecars, not `tailscale serve` or `*_BIND`:** a sidecar gives the service its own tailnet identity and tag, so the ACL governs it and the loopback bind on the host never widens. This is compatible with `networking-defense-in-depth.tac.yaml:3,11` ("no workarounds, especially not tailscale serve"): the sidecar is a node on the mesh, not a proxy on the host. Template: `FLEET_ACCESS_NATS_HUB.md:84-115`. Best in-repo example: `docker-compose.yt-egress.yml:59-95` (fail-closed auth key guard).

## 3. Phases (each one is its own PR or approval)

### Phase A0 — Cipher for every AGInTZ (first)
- **A0.1** `pmoves-cipher-local`: widen `clients` to every harness (crush, kilocode, kimi, opencode, agent-zero added to hermes + claude). Each harness then reaches Cipher on any node that hosts it. This only adds entries, so no harness loses anything.
- **A0.2** Identity: each harness passes its own `agentId` with a per-agent token (`make -C pmoves cipher-identity`), not the shared bootstrap token. This needs the per-request auth fix in the Cipher fork (`fix/cipher-mcp-per-request-auth`, advisory by default) and the launcher token binding (PR 3143). Those two PRs are the *code* that other lanes are editing; this plan depends on them and does not duplicate them. Coordinate by register NOTE; the *availability* goal belongs to every agent.
- **A0.3** Cross-node: Cipher is the **ScaleTail pilot** (Phase C) alongside flute, so nodes that don't host Cipher reach it by tailnet name instead of the dead `${TS_Z890}` URL. `.claude/context/cipher.md:60-64`'s `CIPHER_BIND` route stays the fallback, because it leaves the bearer as the only control.
- **A0.4** Drop-in models: one documented Known Road from "I am a new harness or model" to working store + search: which roster entry connects, which agentId to pass, how to get a token, and how to tell a roster failure from a service failure.

### Phase A — stop the damage (small PRs, zero cross-harness risk)
- **A1** `mcp-toolkit-4090.mk`: port 8089 → 8090 and set `PMOVES_MCP_PROFILE_ID=pmoves_4090_web`. 4090-only file. *Check first:* nothing else consumes 8089 (`port-audit`).
- **A2** Gateway token (F3): the inventory sends `${MCP_GATEWAY_AUTH_TOKEN}`; the listener **reads** the funnel value and fails closed when it is unset, instead of minting its own. The token gets a manifest entry (operator: the manifest is guard-protected). Affects hermes + kilocode only; both currently send the wrong token, so this can only fix them.
- **A3** Roster regeneration **with e2b only**: set flute's `clients` so it is **not** rendered for any harness until Phase C gives it a reachable name. e2b needs the built package on each node; add a `mcp-bootstrap-check` probe that marks it degraded (not failed) where `pmoves-e2b-mcp-server/packages/js/build/index.js` is absent.

### Phase B — one auth path (F6)
- For each OAuth account, choose one owner. Proposal: **Claude's roster owns Cloudflare/comfy/composio** (it already has them), and `cloudflare-docs` is removed from `pmoves_4090_web` / `pmoves_5090_web`. Non-Claude harnesses that need Cloudflare get it through the gateway, which then owns *their* OAuth, and Claude never loads that gateway's Cloudflare entry.
- Document "which client owns which OAuth" as a table in `MCP_TOOLKIT.md`, and have `mcp-bootstrap-check` fail on any account wired in two places.

### Phase C — ScaleTail pilot (one service, per the posture doc step 3)
- **Pilot services: Cipher and flute-gateway.** Cipher because every agent needs it (A0.3); flute because it's small, has an existing `X-API-Key`, and the founder asked for it.
- A compose overlay `docker-compose.ts-sidecar.flute.yml`: `ts-flute` sidecar with an ephemeral tagged auth key from the funnel (`TS_AUTHKEY_FLUTE`), `--advertise-tags=tag:pmoves,tag:mcp`, and flute on `network_mode: service:ts-flute`.
- ACL (`configs/tailscale-acl-policy.json`): add `tag:mcp` to tagOwners, a grant `tag:pmoves → tag:mcp:8055`, and a test case, all applied by `deploy-tailscale-acl.yml`, never by hand.
- Prerequisite: fork-sync PMOVES-Tailscale (about 5 months behind per `TAILSCALE_FLEET_POSTURE.md:24-26`).
- A make target `ts-sidecar-up SVC=<svc>` generalizes the pilot once it's verified.

### Phase D — capacity-driven placement
- Extend `pmoves/config/profiles/<node>.yaml` with `hosts: [<service>…]`, derived from capacity (RAM/VRAM/disk headroom). kvm2 = relay/egress + light SSE; the GPU nodes = everything their VRAM fits.
- Generator: add `--endpoint auto`. Per server it emits the local URL when the node's profile `hosts:` includes it, else the tailnet name of a node that does. This generalizes the Spark-only logic in `crush_configurator.py:655-680` into one shared resolver, so every harness gets the same answer.
- `*_fleet_url` defaults move from `${TS_Z890}` to sidecar MagicDNS names (`flute.<tailnet>.ts.net`), with no baked IPs.

### Phase E — bundle production on any node
- The producer is any node with a `self-hosted, ai-lab, <node>` runner (`sync-secrets-local.yml:71`). The 4090 has none; that is the only thing stopping it from producing its own bundle.
- Change `pull_chit_bundle.sh` to fall back across *registered* producers (from the runner list) instead of hard-defaulting to `b850`, and update `test_chit_provenance_check.py:221-226` to match.

### Phase F — secrets scoped to the repo that uses them (forks run standalone)
**Measured 2026-09-23** (`make -C pmoves gh-secret-capacity-audit` + GitHub API, names only):
- PMOVES.AI `env:Prod` is **100/100, at the GitHub cap**, and repository scope is 90/100. The manifest declares 169 secrets; 133 exist; **32 exist that nothing declares**. This is why `AIRTABLE_API_KEY`, `TAVILY_API_KEY` and `MCP_GATEWAY_AUTH_TOKEN` cannot be added: there is no room.
- **Every fork checked holds zero secrets of its own**: PMOVES-N8N, PMOVES-n8n-FlooS, PMOVES-Open-Notebook, PMOVES-Jellyfin, PMOVES-supabase, PMOVES-tensorzero, PMOVES-Agent-Zero, Pmoves-cipher. None can run CI or deploy on its own.
- Service-specific secrets sitting in the PMOVES.AI scopes today (Prod + repo): open-notebook 15, supabase 14, hostinger 11, bots 9, tailscale 6, jellyfin 4, agent-zero 3, tensorzero 3, n8n 2, wger 2.

**Target:** a secret lives in the scope of the repo that consumes it. n8n secrets and settings go on the n8n fork, Jellyfin's on the Jellyfin fork, and so on. PMOVES.AI keeps only what crosses services: fleet CI, the CHIT/bundle keys, the tailnet and the LLM providers. Every fork then runs standalone, with its own secrets, its own `.env.example`, and a compose file that doesn't need the parent repo. The same key can be pushed to more than one repo from the one CHIT source, so the rule "nodes don't run different secrets" still holds.

**Steps:**
1. **Reconcile first, then move.** Declare or retire the 32 undeclared secrets. Retiring undeclared or duplicate ones is headroom that costs nothing.
2. **Manifest routing** (operator: the manifest is guard-protected): let a key's `github_secret` target name a **repo** (e.g. `POWERFULMOVES/PMOVES-N8N`) as well as a PMOVES.AI scope. Extend `gh-secret-capacity-audit` to measure each fork's scope, not just PMOVES.AI's three.
3. **Pilot on n8n** (2 secrets, the smallest real case): route both to the n8n fork, confirm the fork's workflow reads them, then remove them from `env:Prod`.
4. **Standalone check per fork:** the fork's CI goes green using only its own secrets, and `docker compose up` works from the fork checkout alone, without PMOVES.AI.
5. Move the larger groups in order: open-notebook, supabase, jellyfin, then the rest. Re-run the audit after each move so the published headroom figures come from a fresh measurement.

## 4. Cross-harness safety checks (run for every phase)
- `make -C pmoves mcp-bootstrap-check` for **all** clients, not just `claude`.
- Diff the rendered config per client before and after. Any server that disappears from a harness is a stop.
- `audit-layers-static` (the gates a change trips, not a hand-picked subset).
- Cipher availability is **in scope for every harness** (Phase A0). The files being edited in open PRs (the Cipher fork's `mcp-sse.ts`/`rest-server.ts`, the launchers in PR 3143) are sequenced after those PRs rather than edited in parallel, and coordinated by register NOTE.

## 5. Operator actions (agents can't do these)
- Add `AIRTABLE_API_KEY`, `TAVILY_API_KEY` and `MCP_GATEWAY_AUTH_TOKEN` to the secrets manifest. They can't go in `env:Prod` until Phase F frees room (it's at 100/100). Check `TENSORZERO_CLICKHOUSE_USER`.
- Phase F manifest routing: per-repo `github_secret` targets.
- Approve the Prod environment on each `sync-secrets-local.yml` run.
- Approve any VPS change (kvm2 / kvm4-1 / kvm4-2) separately; `vps-deployer` via Hostinger MCP, never raw SSH.

## 6. Open questions
1. Is `tag:mcp` the right ACL shape, or should it wait for the planned grants migration (`FLEET_ACCESS_NATS_HUB.md:52-57`)?
2. Phase B owner choice: is Claude's roster the right owner for Cloudflare OAuth, given that the other harnesses outnumber it?
3. Should kvm4-1 still host a fleet gateway front (08-27 plan), or is per-node + sidecars enough on its own?
