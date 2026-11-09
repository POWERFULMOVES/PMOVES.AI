# PMOVES Networking Stack Review — DRAFT (local, not committed)

> **Status:** working draft. **Do NOT PR or publish** until the WireGuard-roaming
> path is tested and validated on real hardware (see §6). Kept local per operator
> decision 2026-07-20. Hostnames only — no raw Tailscale/LAN IPs (see
> [[feedback_no_tailscale_ips]]).
>
> **Scope:** ties together the home-server app-install layer (Pinokio 8 skills),
> the mesh transport (Tailscale / Headscale / WireGuard), remote desktop (RustDesk),
> and exit-node egress — with the Android-access decision front and centre.

## 1. The stack, layer by layer

| Layer | What it is | Source of truth |
|-------|-----------|-----------------|
| **App install / management** | Home-server node is a **Pinokio 8** node; P8 **skills** sync into `.claude/skills` and are how the node gains/installs capabilities (e.g. Ultimate-TTS). | P8 release notes; `.claude/skills/`; gepeto skill |
| **Mesh transport** | **Tailscale** tailnet `tailcad9b4.ts.net`; optional self-hosted control via **Headscale** (`PMOVES-Headscale`). Both ride **WireGuard** underneath. | `TAILSCALE_EXIT_NODE_RUNBOOK.md`, `HERMES_AGENT_INTEGRATION.md` |
| **Remote desktop** | **RustDesk self-hosted**, relay on `pmoves-kvm2`, rides the tailnet (ScaleTail sidecar). | `RUSTDESK_SELF_HOSTED.md`, `RUSTDESK_ENROLLMENT.md` |
| **Egress** | Traffic exits via a **KVM exit node** (`tag:exit`, ACL auto-approved). | `tailscale-portfwd-exit-followup-2026-06-25.md`, `MULLVAD_EXIT_UPSTREAM.md` |
| **Client onboarding** | Per-device app **or** a **Gateway Kit** router (no per-phone app). | `MESH_GATEWAY_KIT.md`, `mesh-egress-ab` skill |

## 2. Verified live (2026-06-25, from the 4090)

- All 3 KVMs online + offering exit: `pmoves-kvm4-2` **fastest (176 ms)**,
  `pmoves-kvm4-1` (designated egress, 845 Mbps), `pmoves-kvm2` **slowest (921 ms)**.
- Egress provably leaves through the KVM (public IP = Hostinger DC), not the local uplink.
- MagicDNS + cross-node service reach work (`pmoves-5090:11434` → 200, etc.).
- `tailscale serve` correctly **OFF** — real ingress is Cloudflare/nginx for `*.pmoves.ai`.

**Low-risk action available now (operator):** the 4090 is pinned to the *slowest*
exit (kvm2). Safe-flip to kvm4-2 (runbook): `tailscale set --exit-node=pmoves-kvm4-2
--exit-node-allow-lan-access` → verify egress IP → auto-revert on failure. Raw
`tailscale set` is guard-blocked; run via the runbook.

## 3. The Android problem — corrected against official Tailscale docs

The internal `MESH_GATEWAY_KIT.md` says the Tailscale app "drops on Android
(Doze/battery)." **The official docs do not support that as a general limitation** —
they say Android **as an exit-node _client_** works "normally... without special
restrictions" (KB 1103). What the official docs *do* document as failure modes:

1. **Node-key expiry — every 180 days, "fail-close"** (Tailscale key-expiry docs).
   When a key expires the device silently stops routing until re-auth. This is the
   most likely cause of a phone that "was fine, then went offline."
2. **Missing `autogroup:internet` grant** — "To permit exit node use, add a grant or
   ACL whose `dst` is `autogroup:internet`" (KB 1103). Without it a client connects
   but gets **no internet** — the "connected but slow/dead" symptom.
3. **Android OS battery optimization** killing the *background* VPN service — this is
   an **Android OS behavior (Doze)**, not a Tailscale-documented limitation. It hits
   *any* always-on VPN client (Tailscale or WireGuard) unless the app is exempted
   from battery optimization. Tailscale also offers **app-based split tunneling** and
   **MDM system-policy forced exit-node** on Android (official).
4. **Running an exit node _on_ Android** IS officially limited — "not performant...
   userspace routing only... plug the device into a power source" (KB 1103). Not our
   case (phones *consume*; KVMs *advertise*).

**Correction to carry into the runbook:** before reaching for WireGuard, rule out
(1) key expiry and (2) the ACL grant — both are documented, both are free to fix. The
OS-battery issue (3) is real but affects WireGuard too, so it is not by itself a
reason WireGuard wins.

## 4. Android access — combined path (DECISION: document both)

Two first-class paths; pick per situation.

### 4a. Gateway Kit — at a fixed location (documented, grounded)
GL.iNet router runs Tailscale; phones **just join its WiFi** (no app, no login) and
ride a KVM exit node transparently. Three layers must all be right (from Tailscale KB):
1. **ACL:** clients need `autogroup:internet` — handled by `tag:gateway` in the exit-consume rule.
2. **Route approval via a TAG** auto-approver (a suspended *user* stops advertising; a tag doesn't).
3. **Keep SNAT on** so the router does LAN→exit NAT.

Setup + per-kit steps: see `MESH_GATEWAY_KIT.md` (already complete). Router's
connected-client count = pilot door-count metric.

### 4b. Plain WireGuard — roaming, per device (Hermes suggestion — TO VALIDATE)
For a phone **away from the kit**, the official **WireGuard app** is a standalone
full-tunnel VPN. Grounded in the WireGuard quickstart, a full-tunnel client config is:

```ini
[Interface]
PrivateKey = <phone-private-key>     # wg genkey / wg pubkey
Address    = 10.x.x.2/32
DNS        = <resolver>

[Peer]
PublicKey           = <server-public-key>
Endpoint            = <wg-server-host>:51820
AllowedIPs          = 0.0.0.0/0, ::/0   # official: routes ALL traffic through the peer
PersistentKeepalive = 25                # official: keeps the NAT mapping alive
```

`AllowedIPs = 0.0.0.0/0, ::/0` is exactly how the WireGuard docs define full-tunnel;
`PersistentKeepalive = 25` is the documented value for a client behind NAT.

**Open design question that MUST be validated before this is real (§6):**
the KVM exit nodes run **Tailscale, not a raw WireGuard server**, so there is no
`Endpoint` for the phone to dial today. A roaming WG path needs one of:
- a **WireGuard server on a KVM** (e.g. `wg-easy`), advertising `AllowedIPs =
  0.0.0.0/0` so egress leaves via that KVM — a **parallel plane** to the tailnet.
  **Best roaming fit**: the KVM already has a stable public `Endpoint`, so no DDNS /
  port-forward is needed. This is the recommended test path.
- the **GL.iNet router's built-in WireGuard Server** (official: VPN → WireGuard
  Server → Initialize; add a user; hand the phone a QR/`.conf`). Grounded caveat from
  GL.iNet docs: **"If the GL.iNet router is under a main router, you may need to set
  up port forwarding on the main router"** — i.e. it needs a **reachable endpoint
  (DDNS + upstream port-forward)** to work when the phone is *away from home*. Great
  for "dial back into the home server"; **not** a zero-config roaming answer.
- **Headscale** does **not** apply here — official docs: it replaces only the Tailscale
  *control server*, and "users must continue using official Tailscale client
  applications." Same client on Android → same key-expiry/OS-battery considerations.
  It is a **control-plane sovereignty** choice, not an Android or roaming fix.

**Honest framing (per §3):** WireGuard's advantage here is a *simpler, standalone*
tunnel — NOT immunity from Android Doze (any always-on VPN is subject to OS battery
optimization). Its real win is roaming without the router and without tailnet
key-expiry/ACL coupling.

**Recommendation to test:** a small `wg-easy` on `pmoves-kvm4-2` (fastest) as the
roaming WG endpoint, egress-only, keyed per device. Confirm it does NOT conflict
with the node's Tailscale exit role (IP forwarding / SNAT), and measure vs the tailnet
path with `mesh-egress-ab`.

## 5. Decision matrix (why "both")

| Path | Phone runs | Works roaming | Solves Doze | Needs hardware/endpoint |
|------|-----------|---------------|-------------|-------------------------|
| Gateway Kit | nothing (WiFi) | no (per-location) | yes | GL.iNet router |
| Plain WireGuard | WG app | **yes** | yes | a WG server endpoint (to build) |
| Headscale + TS app | TS app | yes | **no** | Headscale control |

Gateway Kit = best UX at a location; WireGuard = the roaming answer. They compose.

## 6. Validation checklist (gates before this becomes a PR)

- [ ] Stand up a test `wg-easy` (or equivalent) on a KVM; Android WG app connects.
- [ ] Confirm egress leaves via that KVM (`ipinfo.io` shows Hostinger DC).
- [ ] Confirm the WG server + Tailscale exit role **coexist** on the same node
      (ip_forward, SNAT, no route conflict) — or split roles across nodes.
- [ ] `mesh-egress-ab` numbers: WG-roaming vs Gateway-Kit vs direct.
- [ ] Battery/stability soak on Android (the thing Tailscale failed).
- [ ] RustDesk still reachable for a WG-connected device (or note it's tailnet-only).
- [ ] Key management story (per-device WG keys; revoke path).
- [ ] Re-point 4090 egress kvm2 → kvm4-2 (independent, do anytime).

## 7. Open items / not found

- **Correction logged:** `MESH_GATEWAY_KIT.md`'s "Tailscale drops on Android (Doze)"
  is not supported by official docs — Android exit-node *client* use is documented as
  normal. Real documented causes are key-expiry (180d fail-close) and the
  `autogroup:internet` ACL grant. The gateway kit is still a good UX choice; the
  *justification* should be corrected when this is promoted. (Consider a follow-up
  PR to fix the claim in `MESH_GATEWAY_KIT.md` itself.)
- **Hermes WireGuard reasoning was verbal** — §4b is now grounded in the official
  WireGuard quickstart rather than that verbal note.
- Headscale's exact role in PMOVES (control-plane migration vs Tailscale SaaS) is
  not yet decided here — `PMOVES-Headscale` exists but this review doesn't commit to it.

## 8. Sources

**Official (authoritative — this review is written from these):**
- Tailscale exit nodes — https://tailscale.com/kb/1103/exit-nodes
  (autogroup:internet grant, IP forwarding, `--exit-node-allow-lan-access`,
  Android client = normal, Android exit-node server = not performant)
- Tailscale exit-node feature page — https://tailscale.com/docs/features/exit-nodes
- Tailscale key expiry (180d, fail-close) — https://tailscale.com/docs/features/access-control/key-expiry
- Tailscale Android app-based split tunneling — https://tailscale.com/docs/features/client/android-app-split-tunneling
- Tailscale subnets — https://tailscale.com/kb/1019/subnets · ACL syntax — https://tailscale.com/kb/1337/acl-syntax
- WireGuard quickstart (full-tunnel `AllowedIPs=0.0.0.0/0`, `Endpoint`, `PersistentKeepalive=25`) — https://www.wireguard.com/quickstart/
- GL.iNet WireGuard Server — https://docs.gl-inet.com/router/en/4/interface_guide/wireguard_server/
  (Initialize server, add user, QR/`.conf`; "under a main router ... set up port forwarding on the main router")
- GL.iNet two-router WG home server — https://docs.gl-inet.com/router/en/4/tutorials/build_your_own_wireguard_home_server_with_two_glinet_routers/
- Headscale (self-hosted control server; clients still use official Tailscale apps) — https://headscale.net/stable/

**Internal PMOVES (context, not authority):**
`MESH_GATEWAY_KIT.md` · `TAILSCALE_EXIT_NODE_RUNBOOK.md` ·
`tailscale-portfwd-exit-followup-2026-06-25.md` · `RUSTDESK_SELF_HOSTED.md` ·
`MULLVAD_EXIT_UPSTREAM.md` · `mesh-egress-ab` skill · P8 release notes.

**Curated guides — GATED (not yet pulled; services down on this node):**
The PMOVES.yt playlist + `PMOVES-transcribe-and-fetch` transcripts, surfaced via
**Open Notebook** (PMOVES.yt ↔ Open Notebook integration), are a first-party source
for existing networking/home-server guides. As of this draft: yt service (:8600)
**down**, Open Notebook **not running on this node** (CATALOG: external via
`$OPEN_NOTEBOOK_API_URL`; `Notebook Sync :8095`), transcribe-and-fetch submodule
present but not up. **Action:** bring up Open Notebook (or transcribe-and-fetch) to
ingest/query those guides, then fold their grounded specifics into §4–§6 and cite the
source video/transcript per claim. Until then, §1–§8 stand on the vendor docs above.

## 9. Aspirational vs grounded — what literally won't work as-is

Every row is a plausible-sounding plan that **fails** for a grounded reason. Keep this
table honest as we validate — move a row up to §4–§6 only once it's proven.

| "Sounds right" | Why it literally won't work | Grounded path |
|----------------|-----------------------------|---------------|
| Flute container → native Ultimate-TTS at `host.docker.internal:7860` | Flute is multi-homed on internal tiers; its default route has no path to the Docker Desktop host-gateway → "Network unreachable" (observed) | Reach TTS over the host's **Tailscale** address, or run TTS **in Docker** on `pmoves_external` |
| Rebind Ultimate-TTS to 0.0.0.0 to fix Flute→TTS | `launch.py` already defaults `server_name=0.0.0.0` — binding was never the blocker | Fix the **container→host route** (above), and confirm the app finished loading |
| Android WireGuard app → a Tailscale exit node directly | Exit nodes run **Tailscale, not a WG server** — there is no `Endpoint` to dial | `wg-easy` on a **KVM** (public endpoint), or a **GL.iNet WG server** |
| GL.iNet WG server for true roaming, no extra setup | GL.iNet docs: behind a main router it needs **port-forward + DDNS** to be reachable when away | KVM `wg-easy` (stable public endpoint) for roaming; GL.iNet WG server for **home dial-in** |
| Headscale to fix Android drops | Official: Headscale is **control-server only**, clients still run the Tailscale app → same key-expiry/OS-battery | Fix **key-expiry (180d)** + `autogroup:internet` **ACL** first |
| `tailscale serve` as service ingress | Internal `networking-defense-in-depth` TAC treats it as a **workaround to avoid** | Cloudflare / nginx for `*.pmoves.ai`; Funnel only for exit nodes |
| Phone "connected but slow" → needs a faster exit node | Often the phone is **actually offline** (key expired, fail-close) or lacks the `autogroup:internet` grant | Verify **key + ACL** before touching egress |
| WireGuard "immune to Android Doze" | Android battery optimization kills **any** always-on VPN unless the app is exempted | Exempt the app from battery optimization; WG's real win is simplicity/roaming, not Doze-immunity |
