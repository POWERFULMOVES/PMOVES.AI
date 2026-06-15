# Tailscale Exit-Node Runbook — Fleet Egress via the KVMs

> **Goal:** route fleet/site egress through the KVM VPSes (Hostinger DC uplink) instead
> of the local Starlink uplink, and scale exit-node capacity as the tailnet grows to host
> other users. Local nodes use Starlink only to reach the tailnet; **egress exits via a KVM
> exit node.**
>
> Companion: `YT_EGRESS_RUNBOOK.md` (YT-stack-specific egress via `pmoves-kvm4-1`),
> `.claude/context/runner-topology.md` (Phase 9Q), `pmoves/mk/egress.mk`.

## Tailnet + exit-node inventory (2026-06-15)

Tailnet: `tailcad9b4.ts.net`. ACL: `pmoves/configs/tailscale-acl-policy.json`
(has `autoApprovers.exitNode: ["tag:exit"]`).

| Tailscale node | Hostinger hostname | Public IP | Exit node | Notes |
|---|---|---|---|---|
| `pmoves-kvm2`   | PMOVES.AI.CLOUD.KVMII  | 167.88.38.57 | ✅ approved (untagged, hand-approved) | reverse-proxy / RustDesk relay; KVM 2 / 8 GB |
| `pmoves-kvm4-1` | PMOVES.AI.CLOUD1.KVMIV | 31.97.42.207 | ❌ enable | designated Phase-9Q egress; API gateway; KVM 4 / 16 GB |
| `pmoves-kvm4-2` | PMOVES.AI.CLOUD2.KVMIV | 167.88.39.80 | ❌ enable | data/storage; KVM 4 / 16 GB |
| `pmoves-4090`   | (this laptop)          | —            | client → kvm2 | egress set to `pmoves-kvm2` 2026-06-15 (verified) |

**Two planes — do not conflate:**
1. **Advertise** (node-local): the node *offers* itself as an exit node
   (`tailscale set --advertise-exit-node`, or an authkey carrying `tag:exit`).
2. **Approve** (tailnet admin): the tailnet *accepts* the advertised route
   (admin console, Tailscale API/MCP, or — for `tag:exit` nodes — the autoApprover).

The Hostinger API manages the VM (start/stop/firewall/snapshot) but touches **neither**
plane — that's why the Tailscale MCP/API (or console) is required for approval.

---

## Scalable pattern (recommended) — `tag:exit` authkey

Because the ACL already auto-approves `tag:exit`, an exit node brought up with a
**tagged authkey self-approves** — zero console clicks per node. This is the path that
scales to "as many exit nodes as the tailnet can support."

**One-time (operator, admin console) — FOLLOW-UP (credential wiring):**
1. Confirm `tag:exit` tagOwners in `tailscale-acl-policy.json` includes the operator/automation identity (it lists `tag:exit` already).
2. Mint a **reusable, pre-authorized, tagged authkey**:
   admin → *Settings → Keys → Generate auth key* → **Reusable**, **Tags: `tag:exit`**
   (optionally **Ephemeral=off**, **Pre-approved**). Result: `tskey-auth-…`.
3. Store it as `TAILSCALE_EXIT_AUTHKEY` via the Known Road (`env.shared` → `make -C pmoves secrets-funnel`); never inline.

**Per exit node (vps-deployer agent, or operator `!`):**
```bash
# kvm4-1 (31.97.42.207) and kvm4-2 (167.88.39.80)
sudo tailscale up \
  --authkey "${TAILSCALE_EXIT_AUTHKEY}" \
  --advertise-exit-node \
  --advertise-tags=tag:exit \
  --reset
# --reset clears prior flags; re-auth is brief. Node re-joins tagged → autoApprover approves.
```
New future exit nodes (other users' boxes) use the **same authkey** → advertise + tag +
auto-approve in one step. No console interaction as the fleet grows.

---

## Manual path (one-off, no tagged authkey) — what kvm2 used

If you're enabling a node *without* re-tagging (e.g. a quick one-off):

**Advertise (on the node):**
```bash
sudo tailscale set --advertise-exit-node
```
**Approve (pick one):**
- **Console:** admin → *Machines* → node → ⋯ → *Edit route settings* → enable **Exit node**.
- **Tailscale MCP / API:** with `TAILSCALE_API_KEY` set (see below), approve the route
  programmatically (`POST /api/v2/device/{id}/routes` with the exit-node CIDRs
  `0.0.0.0/0`, `::/0`). This is how this repo's automation will approve at scale.

---

## Client side — route a node's egress through an exit node

```bash
# keep LAN reachable; route only internet egress via the exit node
tailscale set --exit-node=pmoves-kvm4-1 --exit-node-allow-lan-access
# revert:
tailscale set --exit-node=
```
**Safe-flip pattern** (used for `pmoves-4090` on 2026-06-15) — set, test, auto-revert so a
broken exit node can't strand the box:
```bash
tailscale set --exit-node=<node> --exit-node-allow-lan-access
sleep 4
curl -sf --max-time 12 https://api.github.com/zen >/dev/null \
  && echo "exit node OK" \
  || { tailscale set --exit-node= ; echo "reverted — exit node unreachable"; }
```

---

## Tailscale MCP (for programmatic approval + ongoing management)

Already configured in `.claude/mcp.json` (`tailscale-mcp@2026.4.10-1`, pinned). It is **not
in the Docker MCP catalog** — it's a standalone npx stdio server (like `hostinger-mcp`).
It connects once these env vars are present (FOLLOW-UP — credential wiring):

| Var | Value | Source |
|---|---|---|
| `TAILSCALE_API_KEY` | `tskey-api-…` (admin → *Settings → Keys → access token*) — **or an OAuth client** (durable; access tokens expire ~90d) | `env.shared` → `secrets-funnel` |
| `TAILSCALE_TAILNET` | tailnet name (*Settings → General*) or `-` for the key's default | `env.shared` → `secrets-funnel` |

For a multi-tenant, growing tailnet prefer an **OAuth client** (scopes `devices`,
`routes`) over a personal access token — it doesn't expire and is auditable.

### Credential wiring (operator-direct — the manifest is zero-access to agents)

`pmoves/chit/secrets_manifest.yaml` is in the damage-control `zeroAccessPaths`
(`.claude/hooks/damage-control/patterns.yaml`) — **no agent (Edit/Write/Bash) can touch
it and there is no Known-Road bypass**; it is operator-owned. The MCP env vars are not yet
declared there (only `tailscale_authkey` is), which is why `TAILSCALE_API_KEY` never lands
in `.env.generated` even though it's a GitHub secret. **Operator applies this directly:**

1. Add to `pmoves/chit/secrets_manifest.yaml` (next to `tailscale_authkey`):
   ```yaml
   - id: tailscale_api_key
     source: { type: cgp, label: TAILSCALE_API_KEY }
     targets:
     - { file: .env.generated, key: TAILSCALE_API_KEY }
     - { file: env.shared.generated, key: TAILSCALE_API_KEY }
     - { file: env.tier-agent, key: TAILSCALE_API_KEY }
     required: false
   - id: tailscale_tailnet
     source: { type: cgp, label: TAILSCALE_TAILNET }
     targets:
     - { file: .env.generated, key: TAILSCALE_TAILNET }
     - { file: env.shared.generated, key: TAILSCALE_TAILNET }
     - { file: env.tier-agent, key: TAILSCALE_TAILNET }
     required: false
   ```
   (Mirrors the working `hostinger_api_token`/`tailscale_authkey` pattern — `.env.generated`
   is the file the MCP launch env sources, same path that makes the hostinger MCP live.)
2. Ensure both are in GitHub Secrets (`TAILSCALE_API_KEY` reportedly present; add
   `TAILSCALE_TAILNET` — value is the tailnet name or `-` for the key's default).
3. Refresh + distribute through the CHIT pipeline (these targets ARE agent-runnable):
   ```bash
   gh workflow run sync-secrets-local.yml --repo POWERFULMOVES/PMOVES.AI -f output_format=cgp
   make -C pmoves secrets-funnel        # decode CGP → .env.generated + tiers
   make -C pmoves env-check             # validate cross-tier consistency
   ```
4. Restart Claude Code (and the own MCP gateway, `make mcp-4090-gateway-start`, if it
   serves the tailscale MCP) so the launch env re-reads `.env.generated`.
5. Verify the MCP connected, then approve the kvm4-1/kvm4-2 exit routes via the MCP.

`TAILSCALE_TAILNET` is not secret (`-` works); if preferred, hardcode it in
`.claude/mcp.json`'s `tailscale.env` instead of routing it through the manifest.

---

## Verify

```bash
# exit-node advertisers visible from any tailnet member:
tailscale status --json | python -c "import sys,json;d=json.load(sys.stdin);[print(p['HostName'],'exitOption=',p.get('ExitNodeOption')) for p in ({**{'self':d['Self']},**d.get('Peer',{})}).values() if 'kvm' in p.get('HostName','').lower()]"
# a client actually using an exit node — egress IP should be the KVM's public IP:
curl -sf https://api.ipify.org   # expect 31.97.42.207 / 167.88.39.80 / 167.88.38.57
```

---

## Handoff (2026-06-15)

- **Done:** `pmoves-4090` egress flipped through `pmoves-kvm2` (verified Starlink→KVM IP change + reachability, auto-revert safety).
- **Follow-up (operator + partner — creator-pipeline operator's new infra role):**
  1. Mint the `tag:exit` reusable authkey + wire `TAILSCALE_EXIT_AUTHKEY` (and
     `TAILSCALE_API_KEY`/`TAILSCALE_TAILNET` for the MCP) via `secrets-funnel`.
  2. vps-deployer: run the tagged `tailscale up` on `pmoves-kvm4-1` + `pmoves-kvm4-2`
     → advertise + auto-approve.
  3. Re-point `pmoves-4090` (and other site clients) to `pmoves-kvm4-1` (designated egress)
     once approved; keep `pmoves-kvm2` as fallback.
  4. Onboard future user exit nodes with the same authkey (self-approving).
