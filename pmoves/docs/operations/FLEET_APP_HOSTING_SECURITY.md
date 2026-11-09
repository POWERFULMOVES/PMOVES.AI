# Hosting an app on the fleet — exposure model and security posture

**Node:** SPARK · **Date:** 2026-09-15 · **Lane:** app-hosting security doctrine
**Trigger:** operator — "security posture and exit node egress … where is docs on hosting app
or securing rustdesk — you just have on the vps naked routing."

This is the missing doc: one page that answers "I have an app — where does it live, who can
reach it, and what guards it."

## The three exposure patterns

| Pattern | Reachable by | Guards | Use for |
|---|---|---|---|
| **Tailscale-only** (default doctrine) | tailnet identities only (WireGuard, ACL-governed) | mesh ACLs + service auth | fleet internals: DBs, NATS, JuiceFS meta, dashboards |
| **Cloudflare-public** | the internet | CF proxy (HTTP/S only), WAF, origin hidden | human-facing web apps |
| **Direct-public** | the internet, raw TCP/UDP | only what the app itself enforces | unavoidable non-HTTP protocols (RustDesk class) — **requires a deliberate decision** |

Rule: an app starts Tailscale-only. Going public is a decision recorded with its guards,
never a side effect of a port binding.

## Where the live apps sit today (audited 2026-09-15)

| App | Surface | Posture |
|---|---|---|
| **Jellyfin** | `media.pmoves.ai` — Traefik on the 5090, KVM2 CoreDNS split-DNS, clients on tailnet (Finamp/Swiftfin + Tailscale app) | Tailscale-only with a service account — correct |
| **JuiceFS** (pmoves-media) | tailnet only; meta exposure still gated (see JuiceFS checklist) | Tailscale-only — correct |
| **RustDesk hbbs/hbbr on kvm2** | binds all interfaces; `id/relay.pmoves.ai` now in PUBLIC Cloudflare DNS (DNS-only) → kvm2 public IP | **Direct-public — this is the naked-routing finding** |

## The RustDesk finding, stated honestly

- hbbs/hbbr bind all interfaces (RustDesk default `BIND`).
- **Ambiguity I will not paper over**: my "public reachability" probe ran from SPARK, and
  kvm2 advertises an exit node — if SPARK's traffic exits via kvm2, the probe looped back
  and proves nothing about the outside. `ip` route checks are hook-blocked here.
  **Verification owed**: one probe from a true external vantage (phone on LTE: try
  `id.pmoves.ai:21116`), or check the Hostinger cloud-firewall panel for kvm2.
- Guards that exist regardless: the **Key** (`id_ed25519.pub`) pins clients to our servers —
  a stranger reaching hbbs without the key gets nothing. But port-level exposure is real
  attack surface (scanner noise, hbbs CVE class).

### Hardening options (pick, record, apply)

1. **Tailscale-only RustDesk** (strictest): remove the public DNS records, firewall
   21114-21119 to tailnet-only on kvm2. Cost: no off-tailnet clients (phones must run
   Tailscale — which the fleet already does for media).
2. **Keep direct-public + add guards**: Hostinger cloud firewall rate-limit / source
   ranges; keep DNS-only records; monitor hbbs logs for probe storms (exit-node observer
   can carry a check).
3. **Hybrid**: public for the few real remote-support clients, tailnet for fleet nodes —
   enforced at the firewall, not the app.

Whatever is chosen gets recorded here and in the RustDesk runbook.

## Cloudflare + Hostinger notes (measured 2026-09-15)

- Cloudflare zone `pmoves.ai` (id `2637f857…`) via funnel `CLOUDFLARE_API_TOKEN`; apex
  records are Hostinger-origin (proxied), MX = titan.email. Fleet-internal names do NOT
  live in public DNS (KVM2 CoreDNS split-DNS holds those) — correct posture.
- DNS-only (`proxied: false`) is load-bearing for any non-HTTP record: CF proxy speaks
  HTTP(S); RustDesk's TCP/UDP must stay direct.
- Hostinger VPS facts come from the funnel (`HOSTINGER_KVM2_IP` etc.) and the
  `hostinger-mcp` (320 tools) — no IPs in committed files.

## School queue (added this lane)

`pmoves/config/channel_monitor.json` +3 watched channels (16→19): **Digital Spaceport**
(UC `UCiaQzXI5528Il6r2NNkrkJA` — AI homelab builds), **Level1Techs** (@Level1Techs —
virtualization/networking depth), **Gamers Nexus** (@GamersNexus — hardware engineering).
Transcription rides the proven yt→whisper pipeline; learnings map like the Archon/Cole
Medin lane (#3050).

## Provenance

- RustDesk contract: `rustdesk/doc.rustdesk.com` (source repo) + `rustdesk/rustdesk-server`
  README — verified 2026-09-15 (#3074).
- Cloudflare zone/records: read + write via the funnel token (this lane).
- Exit-node facts: `make exit-node-observe NODE=pmoves-kvm2` (12/26 peers, exit
  advertised, Mullvad L4 down, 58.1/16000 GB).
