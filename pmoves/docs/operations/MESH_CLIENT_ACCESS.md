# Mesh client access — Tailscale split-DNS + Jellyfin/mobile + services (2026-08-22)

How you (DARKXSIDE) and mobile/Android clients reach the self-hosted services over the
tailnet, with real certs and no per-machine hosts hacks. Written for the mesh-first
architecture ([[vision_tailnet_mesh_pinokio_customdomains]]).

## The one primitive: how names resolve on the mesh

- Services run on nodes (Jellyfin/notebook/etc. on the 5090; llama.cpp on the KVM4s) and are
  served on `*.pmoves.ai` names by Traefik (TLS via Let's Encrypt) — **no host ports**,
  reachable only through the proxy.
- A CoreDNS resolver (`pmoves-mesh-dns`) runs on **KVM2** (always-on) and answers the service
  names → the serving node's tailnet IP; it forwards everything else (apex/www/mail) upstream
  so the public site + email are unaffected. Currently mapped → 5090:
  `notebook` · `health` · `wealth` · `auth` · `media` · `jellyfin`.pmoves.ai.
- **Tailscale split-DNS** routes `pmoves.ai` queries from every tailnet device to that KVM2
  resolver. **This is the one switch that turns the whole thing on.**

## STEP 1 — Turn on split-DNS (Tailscale admin console — 30 seconds, YOUR hands)

The Tailscale REST API is global-nameservers-only; per-domain split-DNS is console-only.

1. Open the **Tailscale admin console** → **DNS** tab.
2. Under **Nameservers**, click **Add nameserver → Custom**.
3. **Nameserver IP** = **`pmoves-kvm2`'s tailnet IP** (Machines list → `pmoves-kvm2`; the
   `100.x` address). *(It's the always-on anchor, not the 5090.)*
4. Turn **ON** the **Restrict to domain** toggle → enter `pmoves.ai`.
5. **Save.** Leave **"Override local DNS" OFF** (split-DNS is already scoped to `pmoves.ai`).

### Verify (from any device on the tailnet)
```
nslookup health.pmoves.ai      # → the 5090 tailnet IP (100.x) = split-DNS live
```
If it still returns your local router or NXDOMAIN, the toggle didn't save.

## STEP 2 — Jellyfin on mobile / Android (the media client)

Jellyfin is served at **`https://media.pmoves.ai`** (Traefik, real LE cert, Jellyfin's own
login — no SSO gate in front). Media files live on **JuiceFS** storage behind it (see below);
you point the *app* at Jellyfin, not at JuiceFS.

**Prerequisite:** the phone must be **on the tailnet** — install the **Tailscale** app, sign
in to the same tailnet, keep it connected. Then split-DNS (Step 1) makes `media.pmoves.ai`
resolve on the phone.

1. Install **Jellyfin** (Android/iOS) — or **Finamp** for music, **Swiftfin** on iOS.
2. Add server: **`https://media.pmoves.ai`** (with `https://`).
3. Log in with your Jellyfin account (the server's own users, not Tailscale).

That's it — works on any tailnet device, LAN or cellular, because the traffic rides the
tailnet. No port-forwarding, no public exposure.

> If `media.pmoves.ai` shows a cert warning on first hit, the `media` router just needs its
> DNS-01 cert to issue — `make -C pmoves up-edge` on the 5090 nudges Traefik to request it
> (the resolver fix in #2658 covers it). auth/health/wealth already issued.

## STEP 3 — The other services (browser, on the tailnet)

Same pattern, in a browser on a tailnet device (SSO login once):
- `https://notebook.pmoves.ai` — Open Notebook
- `https://health.pmoves.ai` — wger (fitness); the wger **phone app** uses `https://health.pmoves.ai` + an API token (Token auth path, no SSO redirect)
- `https://wealth.pmoves.ai` — Firefly III (finance)
- `https://auth.pmoves.ai/login` — the SSO login page

## JuiceFS — where the media lives (storage, not a client)

JuiceFS is the distributed object store (S3 gateway, replacing MinIO) that backs media +
artifacts across nodes. The `pmoves-juicefs-gateway` is healthy on the 5090. You don't point a
phone at JuiceFS — Jellyfin reads media from the JuiceFS-mounted library and serves it. Cross-
node mount runbook: `docs/operations/JUICEFS_CROSS_NODE_MOUNT_RUNBOOK.md`.
(Open item: `pmoves-jellyfin-ai` is pinned to a Knuckles JuiceFS path with shared-mount
propagation not present on the 5090 — a separate node-mount decision, tracked; the main
`pmoves-jellyfin` server is now healthy and independent of it.)

## Pinokio custom domains (after Step 1)

Pinokio auto-serves `http://localhost:<PORT>` → `https://<PORT>.localhost` via its Caddy
(admin API `:2019`). For real `*.pmoves.ai` names served by Pinokio apps, add a Caddy route +
a matching entry in the KVM2 resolver — this layers on **after** split-DNS is live, so it's
sequenced after Step 1.

## llama.cpp on the KVM4s (CPU inference anchors)

`pmoves-llama` (llama.cpp server, Qwen2.5-3B Q4) runs on **kvm4-1** and **kvm4-2**, bound to
each node's tailnet IP `:8081`, OpenAI-compatible:
```
curl http://pmoves-kvm4-1:8081/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"hi"}]}'
```
(First request after deploy waits on the model download; CPU inference is modest — these are
always-on fallbacks; heavy inference comes from fleet GPU passthrough.)
