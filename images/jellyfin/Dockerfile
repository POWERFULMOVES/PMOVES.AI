ARG JELLYFIN_UPSTREAM_IMAGE=jellyfin/jellyfin
ARG JELLYFIN_UPSTREAM_TAG=latest

FROM ${JELLYFIN_UPSTREAM_IMAGE}:${JELLYFIN_UPSTREAM_TAG}

# Minimal hardening: apply OS security updates so Trivy doesn't fail on fixable HIGH/CRITICAL.
USER root
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

# PMOVES hardened standard: run as non-root pmoves user (UID/GID 65532)
# The upstream jellyfin user has UID/GID 1000, so we need to add our own user.
RUN groupadd -r pmoves --gid=65532 && \
    useradd -r -g pmoves --uid=65532 --home-dir=/config --shell=/sbin/nologin pmoves && \
    # Ensure pmoves user can access Jellyfin directories
    chown -R pmoves:pmoves /config /cache /media /transcodes 2>/dev/null || true

USER pmoves:pmoves
