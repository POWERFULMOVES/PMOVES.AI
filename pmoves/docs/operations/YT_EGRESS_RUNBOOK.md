# YT Egress Routing Runbook

**Phase:** 9Q
**Last updated:** 2026-04-16
**Exit node:** `pmoves-kvm4-1` (Hostinger datacenter IP `31.97.42.207`)

## When to Activate

Turn the egress sidecar on when PMOVES.YT starts returning HTTP 403s on
public YouTube videos that should be accessible. Symptoms:

- `curl -X POST http://localhost:8077/yt/ingest ...` returns
  `Failed to download via Invidious companion: 403 Client Error`
- `docker logs pmoves-pmoves-yt-1` shows YouTube 403 responses with
  `&c=WEB` in the signed playback URLs
- `ingest.transcript.ready.v1` events stop firing for channel-monitor
  submissions
- Downstream pipeline (Hi-RAG v2 knowledge freshness, Publisher-Discord
  notifications, conch-consciousness-analysis skill) goes quiet

YouTube rotates anti-bot rules periodically. The residential IP
fingerprint blocks are "set and forget" — once the home IP enters a
blocklist, every request from it gets 403'd regardless of yt-dlp client
strategy, PO tokens, or cookie freshness. Egress routing moves the
outbound surface to Hostinger's datacenter range, which YouTube treats
differently.

## Preflight

Before activation, confirm KVM4-1 is advertising as exit node:

```bash
make -C pmoves yt-egress-preflight
```

Expected output:
```
[yt-egress] Preflight: checking KVM4-1 Tailscale status...
[yt-egress] KVM4-1 reachable on tailnet.
```

If the preflight fails:

1. SSH to KVM4-1 and confirm exit-node advertisement:
   ```bash
   ssh kvm4-1 "tailscale status --peers=false && tailscale status | grep 'exit node'"
   ```
2. If not advertising, re-apply:
   ```bash
   ssh kvm4-1 "sudo tailscale set --advertise-exit-node"
   ```
3. In Tailscale admin UI, approve KVM4-1 as an exit node
   (Admin Console → Machines → pmoves-kvm4-1 → Edit route settings
   → "Use as exit node").
4. KVM4-1 setup history: see
   `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md:475` (2026-04-12 by
   4090-CLAUDE).

The older `deploy/provision/kvm2-exit-node.sh` script targets KVM2 and
was never activated for the YT egress path. It's kept for historical
reference; KVM4-1 is the production exit node.

## Activation

```bash
make -C pmoves up-yt-egress
```

This:
1. Starts `tailscale-yt-egress` sidecar (userspace Tailscale joining the
   tailnet, auth via existing `TAILSCALE_AUTHKEY` in `env.shared`).
2. Waits 20 seconds for exit-node handshake to complete.
3. Recreates `pmoves-yt`, `bgutil-pot-provider`, `invidious-companion`,
   `invidious` with `HTTP_PROXY=http://tailscale-yt-egress:1080` set.
4. Runs verification (see next section).

## Verification

```bash
make -C pmoves yt-egress-verify
```

Expected output:

```
--- Host IP (residential baseline) ---
<your residential IP, e.g. 71.190.90.179>

--- PMOVES.YT container egress IP (expected: 31.97.42.207 or Hostinger range) ---
31.97.42.207

--- Test ingest (dQw4w9WgXcQ, short known-good video) ---
{"ok": true, "ingest_id": "..."}
```

If the test ingest returns `{"detail": "Failed to download..."}`:
- Wait 60 seconds and retry (sidecar may still be establishing route)
- Check sidecar logs: `docker logs pmoves-tailscale-yt-egress`
- Check that bgutil + companion also got the proxy env:
  `docker exec pmoves-pmoves-yt-1 env | grep -i proxy`
- If the IP still shows residential, the sidecar tailnet join likely
  failed — check `TAILSCALE_AUTHKEY` validity in `env.shared`.

## Deactivation (rollback)

```bash
make -C pmoves down-yt-egress
```

Stops the sidecar and recreates the 4 services without proxy env. PMOVES.YT
reverts to residential IP egress. Use when:

- Investigating whether the sidecar itself is causing issues
- KVM4-1 is offline/under-maintenance and YT egress needs to fall back
- After YouTube re-allows the home IP (rare but possible)

## Status Check

```bash
make -C pmoves yt-egress-status
```

Shows:
- Tailscale sidecar status (peers, exit-node state)
- Running state of the 5 affected containers (sidecar + 4 YT services)

## Troubleshooting

### Sidecar stuck at "joining tailnet"

```bash
docker logs pmoves-tailscale-yt-egress
```

Common causes:
- `TAILSCALE_AUTHKEY` in `env.shared` has expired. Regenerate via
  Tailscale admin UI and run `make -C pmoves env-setup` to propagate.
- Network firewall blocking port 41641 UDP (Tailscale DERP). Usually
  OK because Tailscale falls back to TCP relay, but verify with
  `tailscale netcheck` from any other PMOVES node.

### Exit node marked "not advertising" after it was working

Tailscale tagged auth keys can expire. Check via Tailscale admin UI:
- Machine `pmoves-kvm4-1` → Details
- "Key expiry" should be disabled for tagged/shared nodes
- If expired, re-auth with fresh key via the kvm4-1 setup procedure

### YT still 403s even with sidecar active

Three possible causes:
1. **YouTube blocks Hostinger range too.** Unlikely but possible during
   aggressive anti-bot sweeps. Test by pulling a recent known-public
   video via `curl` from the container. If that also 403s, the IP itself
   is blocked.
2. **Cookies are expired.** See the cookies section below (Phase 9Q.2
   addresses this properly).
3. **Invidious companion is down.** Tier 2 fallback is critical when
   Tier 1 yt-dlp hits 403s. Check
   `docker ps --filter "name=invidious-companion"` and restart via
   `docker compose up -d --force-recreate invidious-companion` if needed.

### All traffic going through proxy (not just YouTube)

By design — the sidecar catches all outbound HTTP/HTTPS from the 4 YT
services. `NO_PROXY` carves out internal Docker DNS targets (minio, nats,
supabase-kong, etc.) so service-to-service traffic stays on
`pmoves_app`. If a target is missed and traffic breaks, extend `NO_PROXY`
in `docker-compose.yt-egress.yml` for the affected service.

## Cookies Workflow (Phase 9Q.2 — forward reference)

The current `pmoves/config/cookies/darkxside.youtube.cookies.txt` file is
a **manual workaround** — operator exports browser cookies once, copies
to disk, hopes they don't expire. This is brittle.

The real process (not yet built) uses Google OAuth2 + Playwright headless
Chromium to automatically harvest fresh cookies weekly, store them
encrypted in MinIO, and surface them to `pmoves-yt` via a NATS event
(`yt.cookies.refreshed.v1`). Tracked as Phase 9Q.2 (task #44).

Until that ships, refresh the cookies file manually on expiry:

```bash
# On any machine with a logged-in YouTube session:
yt-dlp --cookies-from-browser chrome \
  --cookies darkxside.youtube.cookies.txt \
  https://www.youtube.com/
# Copy file to PMOVES host:
scp darkxside.youtube.cookies.txt pmoves:pmoves/config/cookies/
# Restart pmoves-yt to pick up (no compose rebuild needed):
make -C pmoves up-pmoves-yt
```

## Related Files

- `pmoves/docker-compose.yt-egress.yml` — sidecar + proxy overrides
- `pmoves/mk/egress.mk` — Make targets
- `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md:475` — KVM4-1 exit node setup
- `pmoves/docs/operations/FLEET_REMOTE_ACCESS_RUNBOOK.md` — tailnet topology
- `pmoves/docs/operations/TAILSCALE_NODE_HYGIENE.md` — stale node cleanup
- `PMOVES.YT/pmoves_yt_service/yt.py` — 3-tier YT fallback implementation

## NATS Subjects Affected

When egress is active and a video successfully ingests, these subjects
fire normally:
- `ingest.file.added.v1`
- `ingest.transcript.ready.v1`
- `ingest.summary.ready.v1`
- `ingest.chapters.ready.v1`

No new subjects introduced by Phase 9Q. Egress is a transport-layer
concern, invisible to event consumers.
