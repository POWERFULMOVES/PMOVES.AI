# PMOVES Integration – Jellyfin Docker + GHCR

Publishes a custom Jellyfin image to GHCR and adds a pmoves-net compose file so the service can be launched within a PMOVES mesh.

Usage:
```bash
docker network create pmoves-net || true
make -C ../PMOVES.AI jellyfin-folders  # ensure Movies/TV/Music folders exist
docker compose -f docker-compose.pmoves-net.yml up -d
# UI: http://localhost:8096
```

Image: `ghcr.io/POWERFULMOVES/PMOVES-jellyfin:main`.

After first boot, install the **Kodi Sync Queue** plugin from Dashboard → Plugins → Catalog to keep Jellyfin for Kodi
clients synchronized.citeturn1search1
