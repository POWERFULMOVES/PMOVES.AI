# RustDesk on KVM2 — fleet client wiring to the self-hosted server

**Node:** SPARK · **Date:** 2026-09-15 · **Lane:** rustdesk self-host adoption (operator-directed)
**Trigger:** "point each rustdesk to self-hosted on kvm2 — we need to add the servers on
rustdesk — research best way to set that up."

## Measured state (today)

`pmoves-kvm2` answers **21115, 21116, 21117, 21118, 21119** (TCP) from the tailnet —
hbbs (ID/rendezvous: 21115/21116+udp/21118) and hbbr (relay: 21117/21119) are live and
fleet-reachable. 21114 (web console/API) is closed — optional, not needed for client
operation. KVM2 also runs nginx :80/443 (SSL termination) and the `fleet-rustdesk-fix`
Make target already exists for server-side config repairs.

## Official contract (rustdesk.com/docs/en/self-host, accessed 2026-09-15)

| Field (client → Network → ID/Relay Server) | Value | Why |
|---|---|---|
| **ID Server** | `pmoves-kvm2` (MagicDNS) — or `id.pmoves.ai` once added to KVM2's CoreDNS split-DNS | hbbs rendezvous; domain beats IP for stability |
| **Relay Server** | `pmoves-kvm2` (or `relay.pmoves.ai`) | hbbr; same host in our layout |
| **API Server** | leave EMPTY | 21114 closed; address-book API is not deployed |
| **Key** | hbbs public key — read from the hbbs data dir on kvm2 (`*_key.pub` / `id_ed25519.pub` next to the hbbs database) | enforces clients only trust OUR servers; without it clients warn on key mismatch |

Rules that matter:
- **UDP 21116 must stay direct** — it is the hole-punching path; do not put it behind
  nginx. Only 21118/21119 (WebSocket) are proxyable if a web client is ever wanted.
- Domain names over raw IPs in client config (fleet doctrine agrees: MagicDNS names are
  the sanctioned form; KVM2 CoreDNS can mint `id.pmoves.ai` / `relay.pmoves.ai` the same
  way `media.pmoves.ai` was done).
- Client-side lock: distribute the config locked (advanced settings lock / config
  string) so fleet clients cannot silently fall back to the public RustDesk servers.

## Setup order

1. **[operator, once]** Read the hbbs public key on kvm2 (hbbs container data volume).
2. **[operator or agent]** Add `id.pmoves.ai` + `relay.pmoves.ai` to KVM2 CoreDNS →
   pmoves-kvm2 tailnet address (mirrors media.pmoves.ai pattern).
3. **[each node/client]** RustDesk → Settings → Network:
   ID Server `id.pmoves.ai`, Relay Server `relay.pmoves.ai`, Key `<pubkey>`.
4. **Verify**: two fleet clients see each other's IDs and connect direct (P2P) with the
   relay as fallback; connection details should list the kvm2 endpoints, not public rs-ny.
5. Optional later: 21114 web console behind kvm2 nginx (TLS) for address book.

## Provenance

- Port probe from SPARK across the tailnet (2026-09-15).
- `pmoves/Makefile` `fleet-rustdesk-fix` (server-side repair road).
- `.claude/CATALOG.md` kvm2 entry (hbbs/hbbr, nginx, CoreDNS split-DNS).
