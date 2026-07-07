# PMOVES Mesh Gateway Kit

> **A shareable "mesh-in-a-box."** A GL.iNet travel router + any uplink + a portable
> battery = on-the-spot WiFi anywhere, with every device that joins riding a PMOVES
> exit node — no per-phone VPN app. Hand it to a Fordham Hill resident, run a demo, or
> take it to a shop whose lines are down. **The router's connected-client count is the
> pilot's door-count / participation metric.**

## The kit

| Part | Role | Example |
|------|------|---------|
| **Router** | Runs Tailscale + hands out WiFi | GL.iNet **Slate 7 / GL-BE3600** (LAN `<router-LAN>/24`) |
| **Uplink** | Gets the router online | Starlink dish, home WAN, phone tether, another WiFi |
| **Power** | Runs it anywhere | Pecron / portable power station |
| **Egress** | Where traffic exits | a PMOVES KVM exit node (**kvm4-1**, 845 Mbps — not kvm2, 578) |

Devices join the router's **WiFi** and get mesh egress transparently. This is strictly
better than the per-device Tailscale app, which drops on Android (Doze/battery) — that
was the "connected but slow" symptom (the phones were actually *offline* on the tailnet).

## Why it works (grounded in Tailscale docs)

Three layers must all be right — this is what the official docs make explicit:

1. **ACL — the device must be allowed to reach `autogroup:internet`.** "Only devices with
   access to `autogroup:internet` can use exit nodes" (the #1 point of confusion). The
   gateway's traffic (and its advertised subnet's) is attributed to the router's identity,
   so without this the clients connect but get **no internet** — the exact "no internet
   when turned on" symptom. → handled by `tag:gateway` in the exit-consume rule.
2. **Route approval — via a TAG auto-approver, not a user.** A user who advertised a route
   stops advertising it if suspended; a tag doesn't. → `autoApprovers.routes` for `tag:gateway`.
3. **Keep SNAT on.** A single device doing *both* subnet-router and exit-node-client can drop
   upstream traffic with `--snat-subnet-routes=false`; keep the default (SNAT on) so GL.iNet's
   exit-node feature does the LAN→exit NAT. (Splitting the two roles across nodes is the docs'
   alternative, but for a travel router the default works.)

Refs: Tailscale KB [1019 subnets](https://tailscale.com/kb/1019/subnets),
[1103 exit-nodes](https://tailscale.com/kb/1103/exit-nodes),
[1337 acl-syntax](https://tailscale.com/kb/1337/acl-syntax).

## One-time tailnet setup (operator, once)

1. **ACL** — merge the `tag:gateway` policy (`pmoves/configs/tailscale-acl-policy.json`):
   tagOwner `tag:gateway` and add it to the exit-consume rule (`→ autogroup:internet:*`).
   Applies via `deploy-tailscale-acl.yml` on merge. **Do not edit the live ACL via API — gitops overwrites it.**
   Note: the committed `autoApprovers.routes` auto-approves only the `tag:exit` default routes
   (`0.0.0.0/0` / `::/0`). The router's `<router-LAN>/24` subnet route is **not** auto-approved —
   the literal CIDR is kept out of the repo per the no-LAN-IPs policy. Approve it once in step 2,
   or maintain a local, uncommitted ACL overlay that adds `{"<router-LAN>/24": ["tag:gateway"]}`.
2. **Tag the router `tag:gateway`** — admin console → Machines → the router → Edit ACL tags
   (or `tailscale up --advertise-tags=tag:gateway` if the router exposes the CLI). Tagging grants
   its clients `autogroup:internet` egress, but its advertised `<router-LAN>/24` **still needs a
   one-time subnet-route approval** (Machines → the router → Approve subnet) — the committed ACL
   does not auto-approve LAN CIDRs. Approve it once; it persists.

## Per-kit setup (repeatable — this is the shareable part)

On the GL.iNet admin (`the GL.iNet admin page (its default gateway)`):
1. **Internet** → connect the uplink (Starlink / WAN / tether / repeater).
2. **Applications → Tailscale** → turn on, log in to the tailnet (approve the device).
3. **Exit Node → `pmoves-kvm4-1`** — routes the router *and its WiFi clients* through that KVM.
4. **Allow Remote Access LAN** (advertises `<router-LAN>/24`) — optional but enables door-count
   visibility + tailnet reachability of clients. Needs the one-time subnet-route approval from
   setup step 2 (Machines → the router → Approve subnet) — it is **not** auto-approved. Client
   egress through the exit node works without it; only LAN reachability/door-count needs the route.
5. **Set the WiFi SSID/password** you'll share.

Client side: **just join the WiFi.** No app, no login. Verify egress on a phone:
`https://ipinfo.io` should show the KVM (Hostinger), and a speed test should be healthy.

## Door-count / participation metric

The router knows every connected device (DHCP leases). That count **is** the pilot signal:
- GL.iNet admin → **Clients** shows connected devices live.
- Feed it to the pilot dashboard: on the router, `cat /tmp/dhcp.leases | wc -l` (or the GL.iNet
  API) → publish to the observation stack. Distinct devices over time ≈ people/homes reached.
- Combine with the exit node's `exit-node-observer.sh` (peers + throughput) for the full picture.

## Use cases (why this is the point)

- **Fordham Hill:** a shared router in a common area → residents join, get pooled mesh internet,
  and the client count is the enrollment metric — no per-resident setup.
- **Demos:** one kit = instant PMOVES-mesh WiFi for a room.
- **Off-grid / disaster:** power out in parts of PA → dish + router + Pecron → stand up WiFi for a
  shop with the lines down. Sovereign connectivity where there is none.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Clients connect, no internet | ACL doesn't grant the gateway `autogroup:internet` | merge the `tag:gateway` ACL + tag the router |
| Route stuck "pending" (clients online but LAN unreachable / no door-count) | committed ACL does not auto-approve LAN CIDRs — the `<router-LAN>/24` subnet route needs a one-time manual approval | admin console → Machines → the router → **Approve subnet** (or add a local uncommitted ACL overlay `{"<router-LAN>/24": ["tag:gateway"]}`). Egress still works while pending — only LAN reachability/door-count is blocked |
| Slow / high latency | router↔KVM path is DERP-relayed | enable UPnP on the router WAN; pick the closest fast KVM |
| Works then drops | uplink flaps (Starlink/tether) | expected; the tunnel re-establishes — kit stays on router, not clients |
| Docker containers on a fleet node lose ALL egress when its exit node is on (host traffic fine) | container-subnet replies routed into Tailscale table 52 instead of back to the bridge | `sudo bash deploy/provision/install-docker-tailscale-routing.sh` (see TAILSCALE_EXIT_NODE_RUNBOOK.md § Docker hosts) |

## Related
- `pmoves/configs/tailscale-acl-policy.json` (`tag:gateway`), `deploy-tailscale-acl.yml`
- `pmoves/docs/operations/TAILSCALE_EXIT_NODE_RUNBOOK.md`, `deploy/provision/exit-node-observer.sh`
- `deploy/provision/mesh-egress-ab.sh` (measure the kit's egress)
- Memory: `project_pmoves_mesh_gateway_kit`, `project_fordham_hill_pilot`
