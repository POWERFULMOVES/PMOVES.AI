#!/usr/bin/env bash
# Surgical CPU-mode rescue for pmoves-media-audio when the nvidia prestart
# hook is broken (ld.so assertion / driver rpc error). NO node restart.
# Preserves the GPU config to a backup JSON, replaces the container with a
# runc CPU twin inheriting env.shared (funnel token included).
# GPU restore later: make -C pmoves media-audio-gpu-restore
set -euo pipefail
OLD=pmoves-media-audio-1
TWIN=pmoves-media-audio-cpu
PM=$(cd "$(dirname "$0")/.." && pwd)

state=$(docker inspect "$OLD" --format '{{.State.Status}}' 2>/dev/null || echo missing)
if [ "$state" = "running" ]; then
  echo "media-audio is running - no rescue needed" >&2
  exit 0
fi

img=$(docker inspect "$OLD" --format '{{.Config.Image}}' 2>/dev/null || true)
if [ -z "$img" ]; then
  img=$(grep -E '^\s*image:' "$PM/docker-compose.media.yml" | head -1 | awk '{print $2}')
fi
[ -n "$img" ] || { echo "cannot determine image" >&2; exit 1; }

docker inspect "$OLD" > "${PM}/docs/operations/media_audio_gpu_config_backup.json" 2>/dev/null || true
net=$(docker inspect "$OLD" --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{end}}' 2>/dev/null || true)
net=${net:-pmoves_api}

docker rm -f "$OLD" >/dev/null 2>&1 || true
docker rm -f "$TWIN" >/dev/null 2>&1 || true

echo "launching CPU twin ($img, network $net)"
docker run -d --name "$TWIN" \n  --runtime runc \n  --env-file "$PM/env.shared" \n  -e NVIDIA_VISIBLE_DEVICES= \n  --network "$net" \n  "$img"

sleep 5
docker ps --format '{{.Names}} | {{.Status}}' | grep -E 'media-audio'
tok=$(docker exec "$TWIN" printenv HF_TOKEN 2>/dev/null || true)
if [ -n "$tok" ]; then echo "HF_TOKEN: ${tok:0:5}... (${#tok}ch) - funnel token inherited"; else echo "WARN: HF_TOKEN unset in twin"; fi
echo "GPU restore when the hook is healthy: make -C pmoves media-audio-gpu-restore"
