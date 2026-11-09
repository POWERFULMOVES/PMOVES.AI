# Handoff — Jellyfin crash-loop: fork image's default `--webdir` points at an empty dir (2026-08-22)

**Node:** 5090 (POWERFULMOVES) · **Lane:** media (Jellyfin, mobile-client reachability) · **Author:** 5090-CLAUDE (Claude Opus 4.8)

## Symptom
`pmoves-jellyfin` (service `jellyfin-ext` in `pmoves/docker-compose.external.yml`) crash-loops:

```
[ERR] Main: The server is expected to host the web client, but the provided content
directory is either invalid or empty: /jellyfin/web
```

## Root cause
The fork image `ghcr.io/powerfulmoves/pmoves-jellyfin:pmoves-latest` ships its default
`CMD` as `--webdir /jellyfin/web`, but the web client lives at **`/jellyfin/jellyfin-web`**
(2262 files, `index.html` present); `/jellyfin/web` is **empty (0 files)**. Measured in the
image:

```
/jellyfin/web        : 0
/jellyfin/jellyfin-web : 2262   (has index.html)
```

The bad path is the image's CMD, not the compose (no `webdir` string exists in any compose),
so the compose must override it.

## Fix (this change)
Add a `command:` override to the `jellyfin-ext` service in
`pmoves/docker-compose.external.yml` pointing `--webdir` at the real web-client dir:

```yaml
    command: ["--webdir", "/jellyfin/jellyfin-web"]
```

The service's entrypoint (`/usr/local/bin/pmoves-entrypoint.sh`) forwards CMD args to
Jellyfin, so this replaces the broken default. No image rebuild needed.

## Deploy / verify
Recreate just this service (other external services + Traefik untouched):
```
make -C pmoves rebuild-external-svc SVC=jellyfin-ext
```
Use this target, not raw `docker compose up` (the damage-control guard blocks raw compose),
and not `rebuild-edge-svc` (that's the traefik/sso overlay and won't reach it). The target
prints a service-aware verify hint; the `jellyfin-ext` service maps to container
`pmoves-jellyfin` (its `container_name`), whose logs should show the HTTP listener start
instead of the web-client error. Then `media.pmoves.ai` (Traefik router, `certresolver=cf`,
port 8096, no forward-auth — Jellyfin's own auth) serves the UI.

## Mobile/Android reachability (the point)
`jellyfin-ext` has **no host ports** — it's reachable only via Traefik at `media.pmoves.ai`.
For mobile clients over the tailnet: add `media.pmoves.ai` → 5090 to the KVM2 mesh resolver
(the CoreDNS `pmoves-mesh-dns`), and once the Tailscale split-DNS for `pmoves.ai` is live,
point the Jellyfin app at `https://media.pmoves.ai` (real LE cert once the `media` router
issues via DNS-01 — the #2658 resolver fix covers it). Interim: publish `8096` on the tailnet
IP if a domain-free `http://<node>:8096` is wanted before split-DNS.
