# The branded Jellyfin image was never built — and that is what happened to SSO (2026-08-04)

**Brief for `KNOWN_ROAD=dockerfile:handoff:jellyfin-branded-image-never-shipped-2026-08-04.md`.**

## The finding

There are **two** Jellyfin Dockerfiles in this repo. The one with all the PMOVES work
in it is not the one that gets built.

| File | Contents | Built? |
|---|---|---|
| `PMOVES-Jellyfin/Dockerfile` (fork submodule) | branded labels, Ezeqielle OIDC plugin baked to `/opt/pmoves/oidc-plugin`, `pmoves-entrypoint.sh`, healthcheck, `ENTRYPOINT` override | **no** |
| `pmoves/images/jellyfin/Dockerfile` | `FROM jellyfin/jellyfin:latest` + `apt-get upgrade`. 19 lines. That is the whole file. | **yes** |

`.github/workflows/integrations-ghcr.matrix.json` builds `pmoves-jellyfin` from
`context: pmoves/images/jellyfin`, `dockerfile: pmoves/images/jellyfin/Dockerfile`,
`ref: main`. It never touches the fork.

So `ghcr.io/powerfulmoves/pmoves-jellyfin:pmoves-latest` is **stock upstream Jellyfin
with an apt upgrade, wearing a PMOVES name.**

## Confirmed at runtime on z890

```
image                     ghcr.io/powerfulmoves/pmoves-jellyfin:pmoves-latest
image_created             2026-08-01          <- built 7 days AFTER the OIDC commit
ENTRYPOINT                [/jellyfin/jellyfin]  <- upstream's, not pmoves-entrypoint.sh
/opt/pmoves/oidc-plugin   ABSENT
/config/plugins/          only "configurations" — no OIDC plugin
ServerName                d7679059898b        <- raw container ID, never branded
StartupWizardCompleted    false
```

The fork commit that bakes the plugin is `f80afdee0e` (2026-07-25). The shipped image
was built 2026-08-01 — *after* it — and still has none of it, because the build was
never looking at the fork.

**This is the answer to "what happened to SSO."** The OIDC plugin work is complete and
correct; it has simply never been inside a running container. Nothing regressed —
it never shipped.

## Two further SSO gaps, independent of the image

These are NOT fixed by this PR and need separate work:

1. **Traefik is not running.** No Traefik container exists on z890. `pmoves-jellyfin`
   carries the routing labels (`Host('media.pmoves.ai')` → `:8096` over
   `pmoves_external`), but with no Traefik they are inert — and the container
   publishes no host port. Jellyfin currently has **no ingress path at all**; it is
   reachable only from inside the Docker network.
2. **Nothing is behind forward-auth.** `pmoves-sso-auth` is `Up (healthy)` on
   `8080/tcp` (internal). Sweeping every running container, **zero** carry a
   `traefik.http.routers.*.middlewares` label. The forward-auth gateway merged in
   #2221/#2229 is running and protecting nothing, because no service was ever put
   behind it.

Note these are two different SSO mechanisms: the baked plugin is *in-app* OIDC (log
into Jellyfin with GoTrue), forward-auth is *gateway-level* (auth once at the edge).
The room needs a decision on which one is authoritative for Jellyfin; running both
will double-prompt.

## What this PR changes

Folds the fork's work into the Dockerfile that actually ships:

- branded labels, OIDC plugin bake, `pmoves-entrypoint.sh`, healthcheck, `ENTRYPOINT`
- keeps the existing `apt-get upgrade` hardening (Trivy gate)
- adds `apt-get purge unzip` after the plugin unzip so the build tool does not stay in
  the final image
- **pins the base to `10.11.11`** (verified present upstream) instead of `:latest` —
  an unpinned base makes the published image unreproducible and silently re-bases on
  every rebuild. `10.11.11` is what the fleet runs today.

Scope is the Dockerfile only. Deliberately **not** included: see the compose drift
below, which is a separate concern with a behavioural wrinkle of its own.

## Separate: compose declares a third-party Jellyfin

`docker-compose.jellyfin-ai.yml` pins `lscr.io/linuxserver/jellyfin:10.11.0` in two
places (the `x-jellyfin-base` anchor and the `jellyfin` service). That is a
third-party public image, against the project's "hardened project images, never random
public containers" rule, and a *different Jellyfin distro* from the one the rest of the
fleet runs. `docker-compose.external.yml` already does the right thing:
`${JELLYFIN_IMAGE:-ghcr.io/powerfulmoves/pmoves-jellyfin:pmoves-latest}`.

Left for its own PR because the swap is **not** cosmetic: the linuxserver image runs as
root and drops to `PUID`/`PGID`, while the official image (which the PMOVES image
extends) runs as the `jellyfin` user and ignores those variables entirely. The overlay
sets `PUID`/`PGID` in `x-jellyfin-env`, so switching images silently changes file
ownership behaviour on the config and media mounts. It needs its own review and a
`compose:` Known Road.

## Follow-ups

- [ ] Rebuild + publish `pmoves-jellyfin`, then confirm on a fresh container:
      `ENTRYPOINT` is `pmoves-entrypoint.sh`, `/opt/pmoves/oidc-plugin` exists, and
      `/config/plugins/oidc-rbac_1.0.8/Jellyfin.Plugin.OIDC.dll` is copied in on start.
- [ ] Retire `PMOVES-Jellyfin/Dockerfile` or add a CI check that the two stay in sync —
      a second, unbuilt Dockerfile is exactly how this drifted.
- [ ] Point `docker-compose.jellyfin-ai.yml` at the PMOVES image (needs a `compose:`
      Known Road and a decision on the `PUID`/`PGID` semantics change above).
- [ ] Bring Traefik up so `media.pmoves.ai` resolves at all.
- [ ] Decide in-app OIDC vs forward-auth for Jellyfin, then wire the chosen one.
- [ ] Complete the startup wizard (admin credential from the CHIT secrets pipeline —
      the service is publicly routed, so do not hand-roll one) and provision libraries.
      Exclude `incoming` (staging) and `playlists` (m3u store).

Related: `juicefs-cross-node-storage-blocker-2026-08-04.md` (why the libraries will be
empty even once they exist), #2221/#2229 (forward-auth gateway).
