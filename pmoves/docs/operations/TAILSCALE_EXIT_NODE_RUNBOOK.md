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
# (0) PREREQUISITE — enable kernel IP forwarding, or the node "advertises" but drops
#     all routed traffic (control plane OK, data plane dead). Linux exit nodes REQUIRE this:
echo 'net.ipv4.ip_forward = 1'            | sudo tee -a /etc/sysctl.d/99-tailscale.conf
echo 'net.ipv6.conf.all.forwarding = 1'   | sudo tee -a /etc/sysctl.d/99-tailscale.conf
sudo sysctl -p /etc/sysctl.d/99-tailscale.conf
# (1) advertise + tag (self-approves via the tag:exit autoApprover)
sudo tailscale up \
  --authkey "${TAILSCALE_EXIT_AUTHKEY}" \
  --advertise-exit-node \
  --advertise-tags=tag:exit \
  --reset
# --reset clears prior flags; re-auth is brief. Node re-joins tagged → autoApprover approves.
```
> **Optional perf (high-throughput exit nodes):** enable UDP GRO on the primary NIC —
> `sudo ethtool -K <iface> rx-udp-gro-forwarding on rx-gro-list off` (persist via networkd/
> a boot unit). Tailscale recommends it for exit nodes/subnet routers moving real volume.
New future exit nodes (other users' boxes) use the **same authkey** → advertise + tag +
auto-approve in one step. No console interaction as the fleet grows.

---

## Manual path (one-off, no tagged authkey) — what kvm2 used

If you're enabling a node *without* re-tagging (e.g. a quick one-off):

**Advertise (on the node):**
```bash
# IP forwarding first (see prerequisite above) — required even for the manual path:
echo 'net.ipv4.ip_forward = 1'          | sudo tee -a /etc/sysctl.d/99-tailscale.conf
echo 'net.ipv6.conf.all.forwarding = 1' | sudo tee -a /etc/sysctl.d/99-tailscale.conf
sudo sysctl -p /etc/sysctl.d/99-tailscale.conf
sudo tailscale set --advertise-exit-node          # stop: --advertise-exit-node=false
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

### Docker hosts MUST install the routing shim (or all container egress dies)

Selecting an exit node on a node that runs Docker silently kills **all container egress**
(host traffic keeps working — that's the trap). Replies de-NAT'd back to container
addresses hit Tailscale's policy rule (`5270: from all lookup 52`), which has no route to
the local bridges, so they leave via `tailscale0` instead of reaching the container. First
hit: Knuckles/B850 2026-07-07 — `supabase-edge-functions` crash-looped 291× on Deno imports
while `pmoves-kvm4-2` was selected; every container timed out on every destination.

```bash
# one-time, per Docker+Tailscale node (idempotent; no-op while no exit node is selected):
sudo bash deploy/provision/install-docker-tailscale-routing.sh
# verify: rule 5269 sits just before Tailscale's 5270
ip rule show | grep -E "^52(69|70):"
```

Container **outbound** traffic still egresses through the exit node (verify from a
container: `docker run --rm curlimages/curl -s https://ipinfo.io/json` → should show the
KVM). `hostinger-kvm-setup.sh` installs this automatically on freshly provisioned nodes.
Refs: [tailscale/tailscale#13367](https://github.com/tailscale/tailscale/issues/13367),
[blog.thms.uk/2026/06/docker-tailscale-exit-node](https://blog.thms.uk/2026/06/docker-tailscale-exit-node).

### Auto / recommended exit node (scales with the fleet)

Instead of pinning every client to a specific node, let Tailscale pick the lowest-latency
exit node — so adding kvm4-3/kvm4-N for new users requires **no client reconfiguration**:
```bash
tailscale exit-node suggest          # prints the recommended node (latency/location)
tailscale set --exit-node=<ID|name>  # apply the suggestion
tailscale exit-node list             # all advertised+approved exit nodes
```
(Requires a Standard+ plan.) This is the client-side complement to the server-side
`tag:exit` autoApprover: new nodes self-approve, clients self-select.

### Enabling a node over the wire (no operator on the box) — what we used 2026-06-15

Admin nodes can drive the node-side setup via **Tailscale SSH** (ACL `ssh` rule:
`autogroup:admin → *`, root allowed; subject to a periodic browser **check** re-auth):
```bash
# IP-forward + advertise in one shot (the kvm2-exit-node.sh configurator, inlined):
tailscale ssh root@pmoves-kvm4-1 'sysctl -w net.ipv4.ip_forward=1; \
  sysctl -w net.ipv6.conf.all.forwarding=1; \
  printf "net.ipv4.ip_forward = 1\nnet.ipv6.conf.all.forwarding = 1\n" \
    > /etc/sysctl.d/99-tailscale-exit-node.conf; sysctl --system; \
  tailscale set --advertise-exit-node'
# if host-key strict-check trips a node, raw ssh TOFU-accepts: ssh -o StrictHostKeyChecking=accept-new ...
```
Canonical configurator: `deploy/provision/kvm2-exit-node.sh` (its no-authkey path is
node-agnostic). **Do NOT** use the Hostinger `recreateVirtualMachine` API to "reinstall
with config" on **running** prod KVMs (kvm4-1/kvm4-2 host TensorZero/Agent-Zero/Hi-RAG/
Supabase) — recreate wipes the disk. Recreate-with-post-install is for **fresh** nodes only.

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

## Tailscale Serve — tailnet-internal HTTPS (no nginx hop)

Expose a local service to **tailnet members only**, over auto-TLS MagicDNS
(`https://<node>.tailcad9b4.ts.net`). Good for giving hosted users clean internal access
to PMOVES services without the KVM2 nginx / Cloudflare layer:
```bash
tailscale serve --bg 8086         # Hi-RAG v2 → https://pmoves-kvm4-1.tailcad9b4.ts.net (members only)
tailscale serve --bg --set-path=/grafana 3000
tailscale serve status            # list ; tailscale serve reset  # clear
```
`--bg` persists across reboots. Serve is tailnet-private; for public exposure use Funnel.

## Tailscale Funnel — public ingress (alternative to Cloudflare/nginx)

Expose a service to the **public internet** through Tailscale's relays (end-to-end
encrypted, hides the node IP). **Only ports 443 / 8443 / 10000.** ACL already grants it to
exit nodes (`nodeAttrs: tag:exit → funnel`); for non-exit nodes add `autogroup:member`.
```bash
tailscale funnel --bg --https=443 localhost:3000   # public https://<node>.ts.net
tailscale funnel status ; tailscale funnel --https=443 localhost:3000 off
```
**When to use vs Cloudflare→KVM2-nginx:** Funnel for quick/standalone public endpoints
(no DNS/cert/port-forward work); keep the Cloudflare/nginx path for `*.pmoves.ai` apex
routing, WAF, and caching. A port can't be Serve (private) and Funnel (public) at once.

## RustDesk self-hosted — stays on the mesh, NOT Funnel

The self-hosted relay (`hbbs`/`hbbr` on **kvm2**, bare-metal systemd) uses ports
**21115–21119 TCP/UDP**, which **do not fit Funnel** (443/8443/10000 only). So RustDesk
rides the **Tailscale mesh directly**: fleet clients target `pmoves-kvm2` (MagicDNS) as the
rendezvous/relay — no public port-forward needed when every client is on the tailnet
(the "ScaleTail" intent). Mobile clients must install Tailscale to use the mesh path.
- Known Roads: `make -C pmoves fleet-rustdesk-fix` (`/fleet:fix-relay`), `/fleet:rustdesk-check`.
- **P0 blocker:** kvm2 port-22 SSH has been blocked ~45 days → can't manage hbbs/hbbr by
  normal SSH. **But Tailscale SSH reaches kvm2** (ACL `autogroup:admin → *`, root) — use
  `tailscale ssh root@pmoves-kvm2 'systemctl status hbbs hbbr'` to manage it over the tailnet,
  bypassing the dead port-22. (Same channel that enabled the kvm4 exit nodes.)
- Decision for the growing tailnet: prefer **tailnet-only** RustDesk (close public UFW
  21115–21119, require clients on the tailnet) for defense-in-depth; keep public ports only
  while non-Tailscale clients must connect.

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

**Done this session:**
- `pmoves-4090` egress flipped through `pmoves-kvm2` (verified Starlink→KVM IP change, auto-revert safety).
- `pmoves-kvm4-1` + `pmoves-kvm4-2`: IP-forwarding enabled + `--advertise-exit-node` set, driven
  over **Tailscale SSH** from the 4090 (operator authed the SSH check). `kvm4-1` **approved → live**;
  `kvm4-2` advertised, **pending one console approve** (untagged → not auto-approved).

**Remaining:**
1. Approve `pmoves-kvm4-2` exit route (console, 1 click) — or wire `TAILSCALE_API_KEY` for the MCP to do it.
2. (Optional, designated egress) re-point `pmoves-4090` + site clients to `pmoves-kvm4-1`; keep kvm2 fallback.
   Or adopt **auto exit-node** (`tailscale exit-node suggest`) so clients self-select.
3. **Scale path for new users' exit nodes:** mint a `tag:exit` reusable authkey + wire
   `TAILSCALE_EXIT_AUTHKEY` via `secrets-funnel`, then bring nodes up tagged → they advertise +
   **auto-approve** (no console clicks). This is the durable onboarding road as the tailnet grows.
