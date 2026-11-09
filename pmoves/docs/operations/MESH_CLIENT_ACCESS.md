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
- **Tailscale split-DNS** routes `pmoves.ai` queries from tailnet devices to that KVM2
  resolver. **This is the one switch that turns the whole thing on.**

> **Access is identity-scoped, not tailnet-wide.** Reaching the KVM2 resolver *and* the
> 5090's HTTPS port requires the device be an **owner/admin identity or a `tag:pmoves`
> device** — per `pmoves/configs/tailscale-acl-policy.json`, ordinary members and the
> partner/guest roles have no route to either, so split-DNS alone won't grant them access.
> Enroll your phone under your owner login (or tag it `tag:pmoves`).

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
login — no SSO gate in front). You point the *app* at Jellyfin, not at the storage behind it;
where that storage lives today vs. where it's headed is in **JuiceFS** below.

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

**Target:** JuiceFS is the distributed FS (S3 gateway, replacing MinIO) that will back media +
artifacts across nodes; you never point a phone at it — Jellyfin reads its library from the
mount and serves it.

**Current state (be accurate):** `docker-compose.external.yml` binds Jellyfin's `/media` to
`${JELLYFIN_MEDIA_DIR:-./data/jellyfin/media}` — a **5090-local directory**, NOT the shared
JuiceFS mount yet. So a freshly-set-up library shows local/empty content, not shared media.
The `pmoves-juicefs-gateway` is healthy on the 5090, but the cross-node `pmoves-media` FS is
not mounted here: remote nodes can't reach the B850 metadata engine (`supabase-db` sits on
`internal: true` networks). Backing Jellyfin with the shared FS means, in order:
1. land the metadata-reachability lane — scoped `juicefs_meta` role → mount cutover → rotate
   `supabase_admin` → tailnet-expose `supabase-db`
   (`docs/handoffs/juicefs-meta-scoped-role-and-tailnet-exposure-2026-08-18.md`);
2. mount `pmoves-media` on the 5090 (`docs/operations/JUICEFS_CROSS_NODE_MOUNT_RUNBOOK.md`);
3. repoint `JELLYFIN_MEDIA_DIR` at that mount, then
   `make -C pmoves rebuild-external-svc SVC=jellyfin-ext`.

(Open item: `pmoves-jellyfin-ai` is pinned to a Knuckles JuiceFS path with shared-mount
propagation absent on the 5090 — a separate node-mount decision, tracked; the main
`pmoves-jellyfin` server is healthy and independent of it.)

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
