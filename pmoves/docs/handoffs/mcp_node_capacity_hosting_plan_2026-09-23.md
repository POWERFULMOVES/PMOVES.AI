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
5. **Nodes don't run different secrets.** Every bundle comes from the same repo-level GitHub secrets. B850 is the *default* producer, not the only one.

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

### Phase A — stop the damage (small PRs, zero cross-harness risk)
- **A1** `mcp-toolkit-4090.mk`: port 8089 → 8090 and set `PMOVES_MCP_PROFILE_ID=pmoves_4090_web`. 4090-only file. *Check first:* nothing else consumes 8089 (`port-audit`).
- **A2** Gateway token (F3): the inventory sends `${MCP_GATEWAY_AUTH_TOKEN}`; the listener **reads** the funnel value and fails closed when it is unset, instead of minting its own. The token gets a manifest entry (operator: the manifest is guard-protected). Affects hermes + kilocode only; both currently send the wrong token, so this can only fix them.
- **A3** Roster regeneration **with e2b only**: set flute's `clients` so it is **not** rendered for any harness until Phase C gives it a reachable name. e2b needs the built package on each node; add a `mcp-bootstrap-check` probe that marks it degraded (not failed) where `pmoves-e2b-mcp-server/packages/js/build/index.js` is absent.

### Phase B — one auth path (F6)
- For each OAuth account, choose one owner. Proposal: **Claude's roster owns Cloudflare/comfy/composio** (it already has them), and `cloudflare-docs` is removed from `pmoves_4090_web` / `pmoves_5090_web`. Non-Claude harnesses that need Cloudflare get it through the gateway, which then owns *their* OAuth, and Claude never loads that gateway's Cloudflare entry.
- Document "which client owns which OAuth" as a table in `MCP_TOOLKIT.md`, and have `mcp-bootstrap-check` fail on any account wired in two places.

### Phase C — ScaleTail pilot (one service, per the posture doc step 3)
- **Pilot service: flute-gateway**. It's small, has an existing `X-API-Key`, and is the server the founder asked for.
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

## 4. Cross-harness safety checks (run for every phase)
- `make -C pmoves mcp-bootstrap-check` for **all** clients, not just `claude`.
- Diff the rendered config per client before and after. Any server that disappears from a harness is a stop.
- `audit-layers-static` (the gates a change trips, not a hand-picked subset).
- Cipher is **out of scope**: B850-CLAUDE owns `fix/cipher-mcp-per-request-auth` and `fix/cipher-agent-token-handoff`. Phase D must not change cipher entries until those land; coordinate by register NOTE.

## 5. Operator actions (agents can't do these)
- Add `AIRTABLE_API_KEY`, `TAVILY_API_KEY` and `MCP_GATEWAY_AUTH_TOKEN` to the secrets manifest and GitHub secrets, and check `TENSORZERO_CLICKHOUSE_USER`.
- Approve the Prod environment on each `sync-secrets-local.yml` run.
- Approve any VPS change (kvm2 / kvm4-1 / kvm4-2) separately; `vps-deployer` via Hostinger MCP, never raw SSH.

## 6. Open questions
1. Is `tag:mcp` the right ACL shape, or should it wait for the planned grants migration (`FLEET_ACCESS_NATS_HUB.md:52-57`)?
2. Phase B owner choice: is Claude's roster the right owner for Cloudflare OAuth, given that the other harnesses outnumber it?
3. Should kvm4-1 still host a fleet gateway front (08-27 plan), or is per-node + sidecars enough on its own?
