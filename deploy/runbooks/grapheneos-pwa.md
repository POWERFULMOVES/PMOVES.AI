# GrapheneOS PWA Deployment Runbook (Pixel 10 Pro)

## Overview
Deploy PMOVES.AI as a Progressive Web App on a Google Pixel 10 Pro running GrapheneOS, with Tailscale for private network access.

## Strategy

1. Build PWA from `pmoves/ui/` (Next.js app)
2. Host on Hostinger VPS with HTTPS (Let's Encrypt)
3. Access via Tailscale for private network, public HTTPS for user-facing
4. Install as PWA on GrapheneOS via Chromium

## Prerequisites

- Hostinger VPS deployed (see hostinger-vps-deploy.md)
- PMOVES.AI frontend build working locally
- Pixel 10 Pro with GrapheneOS installed
- Tailscale installed on Pixel 10 Pro
- Domain name configured (optional, can use Tailscale MagicDNS)

## Steps

### 1. Build Next.js Frontend

```bash
cd pmoves/ui/
npm install
npm run build
# If static export is supported:
npm run export  # outputs to out/
```

If Next.js doesn't support static export (uses server features):
- Use `next start` on the VPS
- Or restructure for static export (remove server components)

### 2. Configure PWA Manifest

Ensure `pmoves/ui/public/manifest.json` exists:
```json
{
  "name": "PMOVES.AI",
  "short_name": "PMOVES",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#0a0a0a",
  "theme_color": "#6366f1",
  "icons": [
    { "src": "/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/icon-512.png", "sizes": "512x512", "type": "image/png" }
  ]
}
```

### 3. Deploy to Hostinger VPS

```bash
# Copy build output to VPS
scp -r pmoves/ui/out/ root@<vps-ip>:/var/www/pmoves/

# Or via rsync
rsync -avz pmoves/ui/out/ root@<vps-ip>:/var/www/pmoves/
```

### 4. Configure HTTPS

```bash
# Install Certbot
apt-get install -y certbot python3-certbot-nginx

# Get certificate (requires domain)
certbot --nginx -d pmoves.yourdomain.com

# Or use Tailscale Funnel for external access without a domain
tailscale funnel 443
```

### 5. Install PWA on GrapheneOS

1. Open Chromium on Pixel 10 Pro
2. Navigate to `https://pmoves.yourdomain.com` (or Tailscale URL)
3. Chromium will show "Install app" banner (or tap menu → "Install app")
4. Confirm installation
5. PWA appears as standalone app in launcher

### 6. Configure Tailscale on Pixel 10 Pro

```bash
# Install Tailscale from F-Droid (GrapheneOS compatible)
# Or: https://tailscale.com/download/android

# Authenticate
tailscale up --authkey=$TS_AUTHKEY

# Access PMOVES services via Tailscale MagicDNS
# e.g., http://pmoves-hostinger:8080
```

### 7. Test Offline Functionality

GrapheneOS is privacy-focused — test that the PWA works with:
- Service worker caching for offline access
- Tailscale reconnection handling
- Background sync for queued operations

## GrapheneOS-Specific Considerations

| Feature | Status | Notes |
|---------|--------|-------|
| PWA install | ✅ Supported | Chromium on GrapheneOS supports full PWA |
| Push notifications | ⚠️ Requires FCM | GrapheneOS restricts background wakeups — use UnifiedPush as alternative |
| Background sync | ⚠️ Restricted | GrapheneOS battery optimization may block sync |
| Camera/Mic | ✅ Supported | Requires per-app permission grant |
| Location | ✅ Supported | Requires per-app permission grant |

## Push Notification Alternative: UnifiedPush

Since GrapheneOS restricts Google FCM:
```bash
# Install ntfy on Hostinger VPS
docker run -d --name ntfy \
  -p 8081:80 \
  -v ntfy_data:/var/lib/ntfy \
  binwiederhier/ntfy serve

# Install UnifiedPush distributor on Pixel 10 Pro from F-Droid
# Configure ntfy endpoint in PMOVES frontend
```

## TODO

- [ ] Verify Next.js static export works
- [ ] Create PWA icons (192x192 and 512x512)
- [ ] Test PWA install on GrapheneOS Chromium
- [ ] Configure UnifiedPush for notifications
- [ ] Test offline functionality
- [ ] Set up Tailscale Funnel for external access
- [ ] Add service worker for caching

## References

- GrapheneOS: https://grapheneos.org/
- PWA Manifest: https://developer.mozilla.org/en-US/docs/Web/Manifest
- UnifiedPush: https://unifiedpush.org/
- ntfy: https://ntfy.sh/
- Tailscale Funnel: https://tailscale.com/kb/1223/funnel

Added: 2026-04-17
