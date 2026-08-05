# PMOVES-Jellyfin — the image that actually ships as
# ghcr.io/powerfulmoves/pmoves-jellyfin, built by integrations-ghcr from
# context pmoves/images/jellyfin.
#
# WHY THIS FILE GREW: the PMOVES branding and SSO work lived only in
# PMOVES-Jellyfin/Dockerfile (the fork submodule), which nothing builds — the GHCR
# matrix points at THIS path. So the published "pmoves-jellyfin" image was plain
# upstream Jellyfin plus an apt upgrade, and every branded/SSO behaviour was absent at
# runtime: no /opt/pmoves/oidc-plugin, ENTRYPOINT still [/jellyfin/jellyfin],
# /config/plugins empty, server name left as the raw container ID. The fork's work is
# folded in here so the shipped artifact IS the branded one.
# See pmoves/docs/handoffs/jellyfin-branded-image-never-shipped-2026-08-04.md
# Keep this in sync with the fork's Dockerfile, or retire that one.

# Pinned, not :latest — an unpinned base makes the published image unreproducible and
# silently re-bases on every rebuild. 10.11.11 is what the fleet runs today.
ARG JELLYFIN_UPSTREAM_IMAGE=jellyfin/jellyfin
ARG JELLYFIN_UPSTREAM_TAG=10.11.11

FROM ${JELLYFIN_UPSTREAM_IMAGE}:${JELLYFIN_UPSTREAM_TAG}

# PMOVES branded labels
LABEL maintainer="PMOVES.AI <ops@cataclysmstudios.com>"
LABEL description="PMOVES-enhanced Jellyfin media server with dual-mode operation"
LABEL org.pmoves.version="1.0.0-hardened"
LABEL org.pmoves.mode="standalone-docked"

USER root

# Minimal hardening: apply OS security updates so Trivy doesn't fail on fixable
# HIGH/CRITICAL. Unchanged from the previous version of this file.
RUN set -eux; \
    if command -v apt-get >/dev/null 2>&1; then \
      apt-get update; \
      apt-get upgrade -y; \
      apt-get autoremove -y; \
      apt-get clean; \
      rm -rf /var/lib/apt/lists/*; \
    elif command -v apk >/dev/null 2>&1; then \
      apk update; \
      apk upgrade --no-cache; \
    fi

# --- PMOVES SSO: bake the Ezeqielle OIDC plugin (RS256/JWKS OIDC client) ---
# Staged OUTSIDE /config because /config is a runtime bind-mount that would shadow a
# plugin baked into /config/plugins. pmoves-entrypoint.sh copies it into place on
# start. Pin the release; oidc-rbac.zip is a FLAT zip (plugin dll +
# Microsoft.IdentityModel/System.IdentityModel dlls + meta.json).
ARG JELLYFIN_OIDC_PLUGIN_VERSION=v1.0.8
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends unzip curl ca-certificates; \
    mkdir -p /opt/pmoves/oidc-plugin; \
    curl -fSsL -o /tmp/oidc.zip \
      "https://github.com/Ezeqielle/jellyfin-plugin-oidc/releases/download/${JELLYFIN_OIDC_PLUGIN_VERSION}/oidc-rbac.zip"; \
    unzip /tmp/oidc.zip -d /opt/pmoves/oidc-plugin; \
    rm /tmp/oidc.zip; \
    chmod -R a+rX /opt/pmoves; \
    apt-get purge -y unzip; \
    apt-get autoremove -y; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/*

COPY pmoves-entrypoint.sh /usr/local/bin/pmoves-entrypoint.sh
RUN chmod +x /usr/local/bin/pmoves-entrypoint.sh

# NO `USER jellyfin` here, deliberately. Upstream jellyfin/jellyfin ships no such
# account — `grep -c jellyfin /etc/passwd` is 0 — so the directive the previous
# version of this file ended on produced an image that cannot start:
#
#   docker: Error response from daemon: unable to find user jellyfin:
#           no matching entries in passwd file
#
# The published image has carried User=[jellyfin] this whole time and only runs
# because the deployment overrides it (the live container is User=[0:0]). Any
# deployment that does not override would fail on start. Upstream runs as root by
# design and expects the operator to set `user:` in compose when they want
# otherwise, so match upstream and leave the choice to the deployment. This keeps
# runtime behaviour identical to what the fleet does today.

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -fSs http://localhost:8096/health || exit 1

EXPOSE 8096

# Copies the baked OIDC plugin into the /config bind-mount on start, then hands off to
# the upstream jellyfin binary unchanged.
ENTRYPOINT ["/usr/local/bin/pmoves-entrypoint.sh"]
CMD ["--webdir", "/jellyfin/web"]
