# Next.js NEXT_PUBLIC Environment Variables

**Date:** 2025-12-22
**Source:** PR #345 CodeRabbit review

## Issue

`NEXT_PUBLIC_*` env vars were set to internal Docker hostnames:
```yaml
- NEXT_PUBLIC_FLUTE_GATEWAY_URL=http://flute-gateway:8055
- NEXT_PUBLIC_FLUTE_WS_URL=ws://flute-gateway:8056
```

These hostnames resolve inside Docker network but **fail in browser** because:
1. `NEXT_PUBLIC_*` vars are embedded at **build time**
2. Browser JavaScript runs **client-side**, outside Docker network
3. Browser cannot resolve internal Docker DNS names

## Pattern

**Use env var overrides with localhost fallback for client-side URLs:**

```yaml
# Good - allows override, defaults to host-accessible localhost
- NEXT_PUBLIC_FLUTE_GATEWAY_URL=${NEXT_PUBLIC_FLUTE_GATEWAY_URL:-http://localhost:8055}
- NEXT_PUBLIC_FLUTE_WS_URL=${NEXT_PUBLIC_FLUTE_WS_URL:-ws://localhost:8056}
```

## Server-Side vs Client-Side

| Variable | Scope | Can use Docker hostname? |
|----------|-------|-------------------------|
| `FLUTE_GATEWAY_URL` | Server-side | Yes |
| `NEXT_PUBLIC_FLUTE_GATEWAY_URL` | Client-side | No - use localhost |

## Detection

```bash
# Find NEXT_PUBLIC vars with Docker hostnames
grep "NEXT_PUBLIC.*http://[a-z-]*:" pmoves/docker-compose.yml
```

## Related

- Next.js documentation on environment variables
- `.claude/context/flute-gateway.md`
