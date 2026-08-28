# pmoves.ai — DNS record bank

Every hostname the fleet already declares, in one place, so the zone can be filled in
a single pass instead of discovered one 404 at a time.

**Measured 2026-08-05:** `pmoves.ai` resolves and is **Cloudflare-proxied**. **None of
the seven subdomains below have any record.** Every `Host(...)` rule in the repo is
therefore unreachable — Traefik can be running perfectly and still never match a
request, because no client can resolve the name.

## The names

Extracted from every `Host(...)` rule across `pmoves/docker-compose*.yml`.

| Hostname | Serves | Declared in | Auth |
|---|---|---|---|
| `auth.pmoves.ai` | `sso-auth` — login, OIDC provider, forward-auth verifier | `docker-compose.traefik.yml:26-30` | is the IdP |
| `health.pmoves.ai` | wger | `docker-compose.external.yml:42` | forward-auth |
| `wealth.pmoves.ai` | Firefly III | `docker-compose.external.yml:82` | forward-auth |
| `notebook.pmoves.ai` | Open Notebook | `docker-compose.external.yml:189` | forward-auth |
| `media.pmoves.ai` | Jellyfin | `docker-compose.external.yml:216` | in-app OIDC, **no** forward-auth |
| `persona.pmoves.ai` | persona living-doc | `docker-compose.persona.yml` | public by design |
| `chit.pmoves.ai` | CHIT tour | `docker-compose.chit-tour.yml` | public by design |

`auth.pmoves.ai` is the keystone — every forward-auth redirect lands there. Create it
first; without it a 401 redirects the browser nowhere.

## What record to create depends on the ingress path

Two mutually-exclusive designs are configured in-repo. **Pick one per node**, then use
the matching column.

| | **Direct** (Traefik owns 80/443) | **Tunnel** (cloudflared) |
|---|---|---|
| Defined in | `docker-compose.traefik.yml` | `docker-compose.core.yml:1189`, profile `cloudflare` |
| Record | `A` → host's public IP | `CNAME` → `<tunnel-id>.cfargotunnel.com` |
| Proxy (orange cloud) | **off** — Traefik terminates TLS via ACME | **on** — required for tunnels |
| Needs | public IP, 80/443 reachable, `CLOUDFLARE_DNS_API_TOKEN` | `CLOUDFLARE_TUNNEL_TOKEN`, no inbound ports |
| TLS | Let's Encrypt via ACME DNS-01 (`certresolver=cf`) | Cloudflare edge certificate |
| Fits | **Hostinger KVMs** — they have real public IPs | **z890 / home nodes** — no public IP needed |

Running the Direct path from a home workstation means exposing a residential
connection and forwarding 80/443. For anything served off z890, prefer the Tunnel.
For a public, always-on edge, prefer a KVM.

Do not mix per hostname without meaning to: a proxied record pointed at an ACME-direct
Traefik will serve Cloudflare's certificate to the client and Traefik's to Cloudflare,
so Cloudflare SSL mode must be **Full (strict)** or the request fails.

## Creating them

The Cloudflare MCP available to coding agents is **Developer Platform only** —
D1 / KV / R2 / Workers / Hyperdrive / docs search. It has **no DNS record tools**, so
DNS cannot be created or read through it. Two working paths:

**Dashboard** — https://dash.cloudflare.com → `pmoves.ai` → DNS → Records → Add record.
Repeat per row above. TTL `Auto`. Set the proxy toggle per the table.

**API** — a token scoped `Zone:DNS:Edit` on `pmoves.ai`:

```bash
# Zone id
curl -s -H "Authorization: Bearer $CF_DNS_TOKEN" \
  "https://api.cloudflare.com/client/v4/zones?name=pmoves.ai" | jq -r '.result[0].id'

# One record (repeat per name)
curl -s -X POST -H "Authorization: Bearer $CF_DNS_TOKEN" -H "Content-Type: application/json" \
  "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records" \
  --data '{"type":"A","name":"auth","content":"<PUBLIC_IP>","ttl":300,"proxied":false}'
```

No literal IPs are recorded in this file on purpose — substitute at run time from the
secrets pipeline.

## Verify

```bash
python -c "
import socket
for h in ['auth','health','wealth','notebook','media','persona','chit']:
    n=h+'.pmoves.ai'
    try: print(f'{n:<24}', sorted({a[4][0] for a in socket.getaddrinfo(n,None,socket.AF_INET)}))
    except Exception: print(f'{n:<24} NO A RECORD')
"
```

Use this rather than `nslookup | grep Address` — the first `Address:` line nslookup
prints is the **DNS server**, not the answer, which reads as a successful resolution
when the name does not exist.

## Before any of this proves SSO works

DNS is necessary, not sufficient. Also required, in order:

1. `make -C pmoves up-edge` — Traefik has **never run** on this fleet.
2. **Recreate wger / firefly / open-notebook.** Their routers carry
   `pmoves-forward-auth@file` in `docker-compose.external.yml:45,85,192`, but the
   running containers predate those labels (created 2026-07-21 / 07-25; #2221 merged
   07-25) and carry none. `make -C pmoves edge-health` reports this explicitly.
3. `CLOUDFLARE_DNS_API_TOKEN` (Direct path) or `CLOUDFLARE_TUNNEL_TOKEN` (Tunnel), and
   `SSO_FORWARD_AUTH_SECRET` — without the last one, header trust never engages and
   apps fall back to their own logins.

See [`EDGE_TRAEFIK_SSO_RUNBOOK.md`](./EDGE_TRAEFIK_SSO_RUNBOOK.md).
