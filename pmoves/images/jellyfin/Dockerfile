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
USER jellyfin
