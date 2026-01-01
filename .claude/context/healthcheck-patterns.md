# Docker Healthcheck Patterns - Multi-Arch Compatible

**Purpose:** Define healthcheck patterns that work across all container images (amd64/arm64, minimal/full).

## Golden Rule: Use What's Available

Different base images include different tools:
- **Alpine/minimal images**: curl, wget, sh, cat, grep
- **Python images**: python3, curl, wget
- **Node images**: node, curl, wget
- **Minimal images (ollama, etc.)**: ONLY curl, sh

**Never assume python3 exists** - many production images are minimal.

## Standard Patterns (Ranked by Preference)

### 1. curl -sf (Best - Works Everywhere)

```yaml
healthcheck:
  test: [ "CMD", "curl", "-sf", "http://localhost:PORT/healthz" ]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 30s
```

**Use for:** All HTTP/HTTPS services
**Works in:** Alpine, Debian, Ubuntu, Python, Node, ollama, minimal images
**Flags:**
- `-s` = silent (no progress meter)
- `-f` = fail on HTTP errors (404, 500, etc.)

### 2. wget -q (Alternative)

```yaml
healthcheck:
  test: [ "CMD", "wget", "-q", "--spider", "http://localhost:PORT/healthz" ]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 30s
```

**Use for:** Images without curl but with wget
**Works in:** Most Debian/Ubuntu images

### 3. /bin/sh with netcat (Last Resort)

```yaml
healthcheck:
  test: [ "CMD", "sh", "-c", "nc -z localhost 6379 || exit 1" ]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 30s
```

**Use for:** TCP port checks (no HTTP endpoint)
**Works in:** Alpine, minimal images with netcat

## Service-Specific Patterns

### Python Services (FastAPI, Flask, etc.)

```yaml
# GOOD - Uses curl
healthcheck:
  test: [ "CMD", "curl", "-sf", "http://localhost:8080/healthz" ]

# BAD - Uses python3 (not in minimal images)
healthcheck:
  test: [ "CMD", "python3", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8080/healthz')" ]
```

### Node Services

```yaml
healthcheck:
  test: [ "CMD", "curl", "-sf", "http://localhost:3000/api/health" ]
```

### Database Services

**PostgreSQL:**
```yaml
healthcheck:
  test: [ "CMD-SHELL", "pg_isready -U pmoves -d pmoves" ]
```

**Redis:**
```yaml
healthcheck:
  test: [ "CMD", "redis-cli", "ping" ]
```

**Qdrant:**
```yaml
healthcheck:
  test: [ "CMD", "curl", "-sf", "http://localhost:6333/health" ]
```

**ClickHouse:**
```yaml
healthcheck:
  test: [ "CMD", "curl", "-sf", "http://localhost:8123/ping" ]
```

### Message Queues

**NATS:**
```yaml
healthcheck:
  test: [ "CMD", "wget", "-q", "--spider", "http://localhost:8222/varz" ]
  # Or use nc if monitoring port not available
  # test: [ "CMD", "sh", "-c", "nc -z localhost 4222" ]
```

**NATS with JetStream:**
```yaml
healthcheck:
  test: [ "CMD", "curl", "-sf", "http://localhost:8222/varz" ]
```

## Common Mistakes

### Mistake 1: Using python3 in Non-Python Images

```yaml
# WRONG - Fails in ollama, minimal Alpine images
healthcheck:
  test: [ "CMD", "python3", "-c", "import urllib.request; ..." ]

# CORRECT
healthcheck:
  test: [ "CMD", "curl", "-sf", "http://localhost:PORT/healthz" ]
```

### Mistake 2: Not Verifying HTTP Status

```yaml
# WRONG - Returns 200 even for 404/500 errors
healthcheck:
  test: [ "CMD", "curl", "http://localhost:PORT/healthz" ]

# CORRECT - -f flag ensures HTTP errors fail
healthcheck:
  test: [ "CMD", "curl", "-sf", "http://localhost:PORT/healthz" ]
```

### Mistake 3: Missing start_period

```yaml
# WRONG - Service fails healthcheck before it's ready
healthcheck:
  test: [ "CMD", "curl", "-sf", "http://localhost:PORT/healthz" ]
  interval: 30s
  timeout: 10s
  retries: 3

# CORRECT - Gives service time to start
healthcheck:
  test: [ "CMD", "curl", "-sf", "http://localhost:PORT/healthz" ]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 30s  # Critical for GPU services
```

## Migration Guide: python3 → curl

Find all python3 healthchecks:
```bash
grep -n "python3.*-c.*urllib" docker-compose.yml
```

Replace pattern:
```yaml
# FROM:
test: [ "CMD", "python3", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:XXXX/PATH', timeout=5)" ]

# TO:
test: [ "CMD", "curl", "-sf", "http://localhost:XXXX/PATH" ]
```

## Healthcheck Endpoint Requirements

Every service MUST expose a `/healthz` endpoint that:
- Returns HTTP 200 + `{"status": "ok"}` when healthy
- Returns HTTP 503 when unhealthy
- Returns quickly (< 1 second)
- Does NOT require authentication

Example (FastAPI):
```python
@app.get("/healthz")
def healthz():
    """Health check endpoint for Docker health checks."""
    return {"status": "ok"}
```

Example (Flask):
```python
@app.route("/healthz")
def healthz():
    return {"status": "ok"}, 200
```

## Quick Reference

| Tool | Available In | Use Case |
|------|--------------|----------|
| `curl -sf` | ✅ All images | HTTP checks (PREFERRED) |
| `wget -q --spider` | ✅ Most images | HTTP checks (alternative) |
| `nc -z` | ✅ Alpine/minimal | TCP port checks |
| `python3 -c` | ⚠️ Python images only | Avoid in healthchecks |
| `node -e` | ⚠️ Node images only | Avoid in healthchecks |
| `pg_isready` | ✅ PostgreSQL | Postgres readiness |
| `redis-cli ping` | ✅ Redis | Redis readiness |

## Pre-Commit Checklist

Before committing healthcheck changes:
- [ ] Uses `curl -sf` or equivalent (not python3)
- [ ] Includes `start_period` (30s minimum for GPU services)
- [ ] Test against actual running container
- [ ] Endpoint returns HTTP 200, not 404
- [ ] Works on both amd64 and arm64

## Related Documents

- `.claude/learnings/pr355-production-hardening-2025-12.md` - Original healthcheck hardening
- `.claude/context/testing-strategy.md` - Testing workflow
- `.claude/context/services-catalog.md` - Complete service listing
