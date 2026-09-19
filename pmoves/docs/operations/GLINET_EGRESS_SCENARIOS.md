# GL.iNet Egress Scenarios (PMOVES Homelab)

Covers the GL.iNet travel router (tailnet identity `tag:gateway`) and its possible
egress roles. Companion docs: FLEET_APP_HOSTING_SECURITY.md and
TAILSCALE_FLEET_POSTURE.md (fleet hosting + tailnet posture context).

Fleet ground truth (from `configs/tailscale-acl-policy.json` + `mesh_exposure` docs):

- Control plane is **headscale** (self-hosted), not Tailscale SaaS.
- kvm2 (`tag:exit`, Hostinger VPS) is the approved tailnet exit node; Funnel on
  kvm2 is the alternate public ingress behind Cloudflare Tunnel.
- `tag:gateway` may advertise its LAN subnet and consume exit nodes
  (`autogroup:internet`); the LAN CIDR is deliberately absent from the repo
  (no-LAN-IPs policy) and gets approved in the admin console.

## 1. Scenario matrix

| Scenario | GL.iNet role | Egress path | Fleet status |
|---|---|---|---|
| A. VPN client | WireGuard tunnel terminator | WAN -> WG server | Optional, not default |
| B. VPN server | WG server for road warriors | Inbound only | Not used |
| C. Travel router | Tailscale subnet router + exit-node client | WAN -> kvm2 -> internet | ACTIVE |

## 2. Scenario A - GL.iNet as VPN client

- Admin Panel -> VPN -> WireGuard Client: import a `.conf`/QR, or pick a provider
  server ("Update Servers" refreshes the list) [1]. Tunnels and per-device/client
  policies are managed on the VPN Dashboard [1].
- Kill switch [2]: default Policy Mode is fail-OPEN (traffic outside the tunnels
  keeps direct internet); Enhanced Kill Switch blocks all egress if the tunnel
  drops (fail-closed). Use fail-closed only where privacy beats availability.
- Fleet fit: dial kvm2's WireGuard endpoint or a commercial WG provider when the
  tailnet itself is unreachable (control-plane outage, DERP loss). Coexistence
  with Tailscale is fine - see section 5.

## 3. Scenario B - GL.iNet as VPN server

- Admin Panel -> VPN -> WireGuard Server provisions server config + client
  peers [3]; handy as a dependency-free remote-access door to a LAN.
- Fleet verdict: **do not expose**. Public ingress is owned by kvm2 (Cloudflare
  Tunnel primary, Tailscale Funnel alternate) per TAILSCALE_FLEET_POSTURE.md;
  a second exposed WG listener on a residential uplink adds attack surface and
  needs DDNS + port-forward with no fleet observability.

## 4. Scenario C - travel router (ACTIVE)

- Applications -> Tailscale: enable and bind the device via the link shown in
  the panel [4]. Firmware v4.9 renames "Allow Remote Access LAN/WAN" to
  **Advertise LAN/WAN Subnets**; advertised routes take effect only after
  approval in the admin console (or via autoApprovers) [4][5].
- PMOVES wiring: the router is tagged `tag:gateway` and advertises its LAN /24
  (approved in the headscale console). WiFi clients egress to the internet
  THROUGH kvm2 because `tag:gateway` is on the `autogroup:internet` ACL rule;
  without that rule clients connect but get no internet [6].
- Custom Exit Nodes [4]: select a specific exit node from the panel; requires
  the router's own subnet routes enabled + approved. IP Masquerading [4] is the
  manual NAT alternative. Tailnet-side ops use `tailscale set --exit-node=` [7].

## 5. WireGuard / Tailscale interop

- Tailscale *is* WireGuard. On GL.iNet it ships as an app rather than a
  VPN-dashboard tunnel, so a classic WG client tunnel (Scenario A) and Tailscale
  can run simultaneously: two overlays where kernel routes/policy decide
  precedence.
- Rule of thumb: Tailscale owns LAN-side reachability (subnet router) and
  tailnet egress; classic WG owns provider tunnels. Never point both at
  `0.0.0.0/0` - overlapping AllowedIPs make the last-installed route win and
  break debugging.
- Tailnet via GL.iNet as subnet router: LAN devices get tailnet reachability
  WITHOUT running Tailscale - reachable from the tailnet and able to reach
  tailnet IPs, but not tailnet members (no node identity, no MagicDNS) [5].
  Their traffic is attributed to the gateway's `tag:gateway` identity.

## 6. Egress failover ladder

1. **Home uplink** (default): direct WAN, no overlay. Fastest, no privacy.
2. **Tailnet exit kvm2** (current travel default): router selects kvm2 as exit
   node; non-tailnet traffic leaves via Hostinger [4][7]. Switch via panel or
   `tailscale set --exit-node=`.
3. **Future Mullvad exits**: two options -
   - Tailscale Mullvad add-on [8]: requires Tailscale SaaS coordination; not
     available to nodes on headscale.
   - Chained Mullvad on kvm2: kvm2 dials a Mullvad WireGuard upstream so exit
     traffic leaves via Mullvad (#1945). Planned PMOVES path.
- Failover direction: WG client + Enhanced kill switch = fail-closed (no net
  without VPN); travel-router mode = fail-open to direct WAN when the tailnet
  is unreachable. Choose per threat model, not both.

## 7. DNS posture (MagicDNS vs router DNS)

- MagicDNS serves tailnet MEMBERS: node names resolved at 100.100.100.100 [10].
  headscale supports MagicDNS configuration [9].
- Devices behind the GL.iNet subnet router are not members: they use the
  router's DHCP/DNS (dnsmasq upstream) and must address tailnet nodes by
  100.x IP, not MagicDNS name.
- GL.iNet-documented gotcha: if the router's DNS upstream is a private-IP
  resolver, internet BREAKS while an exit node is active - set a public
  resolver under NETWORK -> DNS [4].
- PMOVES stance: router forwards to public resolvers (optionally via the
  AdGuard Home plugin); MagicDNS stays a member-device convenience; never point
  LAN DHCP DNS at tailnet-internal resolvers - it couples plain LAN clients to
  tailnet health and breaks on exit-node switches.

## 8. Fleet positioning

- Layer model: the GL.iNet lives entirely at L3 (tailnet mesh) as consumer and
  gateway; it never participates in L4 public ingress (kvm2 + Cloudflare) [11].
- ACL: `tag:gateway` reaches `tag:pmoves:*` and consumes `autogroup:internet`;
  it is absent from partner/guest lanes; SSH from it is nonroot-only [6].
- Recovery: re-enroll a replacement router with the same tag (headscale
  pre-auth key), re-approve the LAN route, done - no config drift.

## References

- [1] GL.iNet WireGuard client: https://docs.gl-inet.com/router/en/4/interface_guide/wireguard_client/
- [2] GL.iNet VPN kill switch: https://docs.gl-inet.com/router/en/4/faq/block_non_vpn_traffic/
- [3] GL.iNet WireGuard server: https://docs.gl-inet.com/router/en/4/interface_guide/wireguard_server/
- [4] GL.iNet Tailscale app: https://docs.gl-inet.com/router/en/4/interface_guide/tailscale/
- [5] Tailscale subnet routers: https://tailscale.com/kb/1019/subnets
- [6] Fleet ACL source of truth: `configs/tailscale-acl-policy.json`
- [7] Tailscale exit nodes: https://tailscale.com/kb/1103/exit-nodes and
  https://headscale.net/stable/ref/exit-node/
- [8] Tailscale Mullvad exit nodes: https://tailscale.com/kb/1561/mullvad-exit-nodes
- [9] headscale DNS/MagicDNS: https://headscale.net/stable/ref/dns/
- [10] Tailscale MagicDNS: https://tailscale.com/kb/1081/magicdns
- [11] `services/mesh_exposure/README.md` (L1-L4 reachability model)
- GL.iNet install walkthrough: https://tailscale.com/kb/1136/tailscale-on-gl-inet-routers
