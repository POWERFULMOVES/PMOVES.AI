# RustDesk on KVM2 — fleet client wiring to the self-hosted server

**Node:** SPARK · **Date:** 2026-09-15 · **Lane:** rustdesk self-host adoption (operator-directed)
**Trigger:** "point each rustdesk to self-hosted on kvm2 — we need to add the servers on
rustdesk — research best way to set that up."

## Measured state (2026-09-15)

`pmoves-kvm2` answers **21115, 21116, 21117, 21118, 21119** (TCP) on BOTH the tailnet
name and the **public IP** - hbbs and hbbr are live for fleet AND internet clients.
21114 (Pro http API) closed, correct for OSS. DNS is DONE: `id.pmoves.ai` and
`relay.pmoves.ai` created in the Cloudflare pmoves.ai zone (DNS-only, A -> kvm2 public
IP via the funnel-delivered `HOSTINGER_KVM2_IP`; resolution verified). DNS-only is
load-bearing: the core ports need direct TCP/UDP - only the optional web-client
WebSocket ports (21118/21119) are ever proxyable. KVM2 also runs nginx :80/443 and the
`fleet-rustdesk-fix` Make target exists for server-side repairs.

## Official contract (rustdesk.com/docs/en/self-host, accessed 2026-09-15)

| Field (client → Network → ID/Relay Server) | Value | Why |
|---|---|---|
| **ID Server** | `id.pmoves.ai` (**live in Cloudflare since 2026-09-15**, DNS-only A -> kvm2 public IP; also resolvable on-tailnet as `pmoves-kvm2`) | hbbs rendezvous; required field; domain over IP per canonical docs |
| **Relay Server** | `relay.pmoves.ai` (**live**, same record shape) | hbbr; canonical docs: "often optional because RustDesk can infer it" - set it explicitly anyway for determinism, or bake it server-side via hbbs `-r`/`RELAY-SERVERS` |
| **API Server** | leave EMPTY | Pro-only feature (account login/web console); OSS deployment, not applicable |
| **Key** | contents of **`id_ed25519.pub`** in the hbbs working dir on kvm2 (generated on first hbbs run) | canonical: "required for encrypted connections to your self-hosted server"; clients reject key mismatch - this is what pins fleet clients to OUR servers |

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

## Provenance (canonical, verified 2026-09-15 after an earlier summarizer-only pass)

- Port table + field semantics: `rustdesk/doc.rustdesk.com` (the docs site's own source
  repo - the rendered site is JS-only, so raw fetches 404): `content/self-host/_index.en.md`
  and `content/self-host/client-configuration/_index.en.md`.
- Server flags (KEY/-k, RELAY-SERVERS/-r, default ports hbbs 21116 / hbbr 21117):
  `rustdesk/rustdesk-server` README.
- Live measurements: tailnet + public port probes from SPARK; DNS resolution checks;
  Cloudflare record creation via the funnel-delivered `CLOUDFLARE_API_TOKEN`
  (zone pmoves.ai `2637f857...`).
- `pmoves/Makefile` `fleet-rustdesk-fix`; `.claude/CATALOG.md` kvm2 entry.
