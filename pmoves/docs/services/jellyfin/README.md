# Jellyfin External Service

PMOVES now ships a convenience wrapper around the upstream Jellyfin Docker image that persists config/cache, mounts a
curated media tree, and exposes the server on `http://localhost:8096` via `pmoves/docker-compose.external.yml`.

## Compose Layout

- `./data/jellyfin/config` → bind-mounted to `/config` (settings, users, plugin packages)
- `./data/jellyfin/cache` → `/cache` (thumbnails, transcoding temp artefacts)
- `./data/jellyfin/transcode` → `/transcodes` (runtime transcoding workspace)
- `./data/jellyfin/media` → `/media` (library roots – Movies/TV/Music/Audiobooks/Podcasts/Photos/HomeVideos)

Create the tree with:

```bash
make -C pmoves jellyfin-folders
```

Drop assets into the relevant subfolders or mount additional host paths by editing the compose file. Set
`JELLYFIN_PUBLISHED_URL` in `env.shared` when you expose the server beyond localhost so deep links in Discord/Gateway
payloads resolve correctly.

## Plugin & Kodi Integration

1. After `make up-external-jellyfin`, open `http://localhost:8096` and run through the onboarding wizard, pointing Movies,
   TV, Music, etc. at the folders above.
2. Install the **Kodi Sync Queue** plugin from Dashboard → Plugins → Catalog → search for “Kodi” (stable repository). This
   enables real-time sync events for Jellyfin for Kodi clients.
3. Optional: if the plugin catalog is empty, add the stable manifest URL
   (`https://repo.jellyfin.org/releases/plugin/manifest-stable.json`) under Dashboard → Plugins → Repositories.
4. On each Kodi device, install **Jellyfin for Kodi** from the official add-on repository (Download → Video add-ons →
   Jellyfin), sign in with the same base URL/API key, and enable automatic sync.

## Maintenance Tips

- Back up `./data/jellyfin/config` to preserve users, libraries, and plugin installs before upgrades.
- Use `docker logs cataclysm-jellyfin` to monitor scheduled tasks such as library scans or plugin updates.
- When migrating media between machines, keep the folder names identical (Movies/TV/etc.) so the library definitions stay
  valid without recreating paths.
