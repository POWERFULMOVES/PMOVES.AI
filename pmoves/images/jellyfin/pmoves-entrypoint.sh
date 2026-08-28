#!/bin/sh
# PMOVES SSO — OIDC plugin copy-on-start.
#
# The Ezeqielle jellyfin-plugin-oidc is baked into the image at
# /opt/pmoves/oidc-plugin, but Jellyfin loads plugins from /config/plugins and
# /config is a runtime bind-mount (./data/jellyfin/config). A plugin baked
# directly into /config/plugins would be SHADOWED by that mount and vanish. So
# stage it outside the mount and copy it into place on start — idempotent, and
# self-healing if the plugin dir is ever cleared — then hand off to the upstream
# Jellyfin entrypoint unchanged.
set -e

STAGE="/opt/pmoves/oidc-plugin"
DEST="/config/plugins/oidc-rbac_1.0.8"

if [ -d "$STAGE" ] && [ ! -f "$DEST/Jellyfin.Plugin.OIDC.dll" ]; then
    mkdir -p "$DEST"
    cp -a "$STAGE/." "$DEST/"
    echo "[pmoves-entrypoint] installed OIDC plugin -> $DEST"
fi

exec /jellyfin/jellyfin "$@"
