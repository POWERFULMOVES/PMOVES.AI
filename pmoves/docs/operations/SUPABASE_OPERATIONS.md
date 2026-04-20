# Supabase Operations Runbook

Operational guidance for the PMOVES Supabase stack (13 services on the
`supabase-local` profile). This runbook captures the non-obvious tuning,
diagnosis, and recovery knowledge that would otherwise be reinvented
every time an agent hits one of these issues.

> Last updated: 2026-04-20
> Origin: Phase 9C infra-hardening session (crash-loop diagnosis + fixes)
> Related runbook: [DAMAGE_CONTROL_RECOVERY.md](./DAMAGE_CONTROL_RECOVERY.md)

---

## Kong tuning (worker-count OOM class)

### Symptom

`pmoves-supabase-kong-1` shows `(healthy)` briefly then either OOM-kills
or the host-port forward (`HostConfig.PortBindings` declared, but
`NetworkSettings.Ports` stays empty) never activates.

### Root cause

Kong reads `/proc/cpuinfo` from the **host**, not the `cpus:` cgroup
limit, to decide how many nginx workers to spawn. On a 24-core host
with the default config it spawns 24 workers × ~80 MB each loading the
full bundled plugin set → ~1.9 GB of resident memory before accepting a
single request. The 256 MB memory limit in the original compose file
triggered OOM before Kong finished binding its listen socket, leaving
Docker Desktop's port forwarder in a half-configured state.

### Canonical settings

In `pmoves/docker-compose.yml` under `supabase-kong`:

```yaml
environment:
  - KONG_PLUGINS=bundled          # not 'bundled,jwt' — jwt is already included
  - KONG_NGINX_WORKER_PROCESSES=1 # pin to match cpus: 0.5 budget
  - KONG_PROXY_BIND=0.0.0.0       # not 127.0.0.1 (see next section)
deploy:
  resources:
    limits:
      cpus: '0.5'
      memory: 512M                # ~2x the single-worker footprint
```

Baseline footprint: ~90 MiB resident (17% of the 512M cap).

## Kong host-port binding (Docker Desktop Windows quirk)

### Symptom

```
$ docker inspect pmoves-supabase-kong-1 --format '{{.HostConfig.PortBindings}}'
map[8000/tcp:[{127.0.0.1 8000}] 8001/tcp:[{127.0.0.1 8001}]]

$ docker inspect pmoves-supabase-kong-1 --format '{{.NetworkSettings.Ports}}'
map[8000/tcp:[] 8001/tcp:[]]

$ curl http://localhost:8000/
curl: (7) Failed to connect to localhost port 8000
```

HostConfig has the mapping, but NetworkSettings shows it empty —
the host-side forwarder never activated.

### Root cause

Docker Desktop on Windows silently skips the host-side forwarder for
explicit `127.0.0.1:<port>` binds on *some* multi-port services. The
exact trigger condition is not fully characterized upstream; empirically
switching the host-bind address to `0.0.0.0` always works. Single-port
services (Flute Gateway on 127.0.0.1:8055) are **not** affected;
multi-port Kong always is on current builds.

### Fix

Default `KONG_PROXY_BIND` to `0.0.0.0` in `docker-compose.yml`:

```yaml
ports:
  - ${KONG_PROXY_BIND:-0.0.0.0}:${SUPABASE_KONG_PROXY_PORT:-8000}:8000
  - ${KONG_ADMIN_BIND:-0.0.0.0}:${SUPABASE_KONG_ADMIN_PORT:-8001}:8001
```

Operators who need LAN-isolation must override **BOTH** bind vars in
`env.shared` — the proxy (8000) and the admin API (8001) have
independent defaults, and setting only `KONG_PROXY_BIND` leaves the
admin API exposed on 0.0.0.0 (the remote-management plane):

```bash
# Loopback-only isolation (requires Docker Desktop build where the
# multi-port 127.0.0.1 quirk is resolved upstream):
KONG_PROXY_BIND=127.0.0.1
KONG_ADMIN_BIND=127.0.0.1
```

Setting one without the other is worse than the 0.0.0.0 default —
it gives a false sense of isolation while leaving the admin plane
reachable.

### Diagnosis rule

When any container shows `HostConfig.PortBindings` populated but
`NetworkSettings.Ports` empty, **check for OOM before blaming the
network layer**:

```bash
docker events --since 2m --filter container=<name> | grep -E "oom|die"
docker stats --no-stream <name>
```

An empty events-grep with low memory pressure points to the Docker
Desktop Windows multi-port forwarder quirk. OOM events point to the
worker-count multiplication above.

---

## Realtime `DB_ENC_KEY` sizing

### Symptom

`pmoves-supabase-realtime-1` enters a restart loop with:

```
(crypto 5.5.3) crypto.erl:1695: :crypto.crypto_one_time(:aes_128_ecb,
"f7ebfc13eecdf70e7f5451a079886790", <<...>>, true)
** 2nd argument: Bad key size
```

### Root cause

Supabase Realtime's Erlang crypto layer consumes `DB_ENC_KEY` as a
**raw byte string**, not as hex. AES-128-ECB requires exactly 16 bytes.
A 32-character hex value (which is 16 bytes when hex-decoded) becomes
32 raw bytes when Realtime reads it unmodified — which is the wrong
AES key size and crashes.

### Fix

`pmoves/bootstrap/registry.json` entry for `SUPABASE_REALTIME_ENC_KEY`
must be:

```json
{
  "key": "SUPABASE_REALTIME_ENC_KEY",
  "generate": {
    "type": "random_urlsafe",
    "length": 16
  }
}
```

Not `random_hex, 32` (which produces 32 ASCII chars, wrong size).

**Regenerating an existing legacy 32-char value:** the `bootstrap_env.py`
format check described below is **intentionally lax** for
`random_urlsafe` — it accepts any length and any character set,
because tightening the check would rotate working n8n / wger / jellyfin
passwords that were generated with slightly-off legacy tooling. That
leniency means a 32-char legacy `SUPABASE_REALTIME_ENC_KEY` will **not**
be caught by `make env-setup ARGS=--accept-defaults` and Realtime will
keep crash-looping with `Bad key size`.

**Manual recovery for a legacy REALTIME_ENC_KEY:**

```bash
cd pmoves && python -c "
import secrets, re
from pathlib import Path
p = Path('env.tier-supabase')
text = p.read_text(encoding='utf-8')
new_val = secrets.token_urlsafe(16)[:16]
text = re.sub(r'^SUPABASE_REALTIME_ENC_KEY=.*$',
              f'SUPABASE_REALTIME_ENC_KEY={new_val}',
              text, count=1, flags=re.MULTILINE)
p.write_text(text, encoding='utf-8')
print(f'regenerated; len={len(new_val)}')
"
make -C pmoves supa-restart
```

This is the same inline script used during the Phase 9C session.

---

## `VAULT_ENC_KEY` and other `random_hex` self-heal

### Symptom

Fernet-based vault services fail with `Invalid token` or
`Non-hex character at position N`, often after an env.shared edit or
secrets hydration round-trip that mangled the value.

### Root cause

Earlier versions of `bootstrap_env.py` only regenerated secrets when
the slot was **empty or placeholder**. A slot holding a corrupted value
(e.g., non-hex chars mid-string after a botched merge) was treated as
"already set" and never regenerated.

### Fix

`pmoves/scripts/bootstrap_env.py` now runs a format check
(`value_matches_spec()`) before deciding a slot is set: if the existing
value fails the declared generator's format, it's treated as empty and
regenerated.

**Scope of the check (deliberately asymmetric):**

| Generator type | Check | Rationale |
|---|---|---|
| `random_hex` | Length + character set (`0-9a-fA-F`) | Fernet / vault keys require hex; a non-hex byte breaks decryption immediately, so strict is safe |
| `random_urlsafe` | Always passes (length and charset both ignored) | Legacy values from `openssl rand -base64 ... \| tr -d '='` have `+/` chars and frequently wrong lengths; tightening would rotate working n8n / wger / jellyfin passwords |
| `passphrase` | Always passes | Same rationale as urlsafe |

### Recovery command

```bash
make -C pmoves env-setup ARGS=--accept-defaults
```

On the first run after the fix, this will print `[warn] <KEY> fails
<generator> format check — regenerating` for every corrupted **hex**
slot and write fresh values. Idempotent on clean values.

### What this does NOT catch

Legacy `random_urlsafe` slots with wrong length or wrong character set
pass through unchanged. The known case is `SUPABASE_REALTIME_ENC_KEY`
set as 32 hex chars from the old registry spec — see the manual
recovery block in the Realtime section above for the one-shot fix.

---

## Studio + Edge Functions crash-loop fixes (PR #1328 context)

### Studio: `getaddrinfo EAI_AGAIN <short-id>`

Next.js 16+ reads `process.env.HOSTNAME` for its server bind address.
Docker sets `HOSTNAME` to the container's short ID by default; Next.js
resolves the short ID as a DNS name before binding, and the embedded
Docker DNS (`127.0.0.11`) has no record for it → `EAI_AGAIN` → exit.

**Fix:** Pin `HOSTNAME=0.0.0.0` in the Studio environment block.

### Edge Functions: `failed to lookup address information`

`supabase/edge-runtime` cold-loads Deno standard library modules from
`https://deno.land/...` at worker-bootstrap time. Docker's embedded
DNS intermittently fails to forward external queries on Docker Desktop
Windows.

**Fix:** Pin upstream resolvers on the service:

```yaml
dns:
  - 1.1.1.1
  - 8.8.8.8
```

---

## Crash-loop diagnosis workflow

When any `pmoves-supabase-*` container is in `Restarting`:

```bash
# 1. What is the error?
docker logs <name> --tail 20

# 2. Memory pressure / OOM?
docker events --since 2m --filter container=<name> | grep -E "oom|die"
docker stats --no-stream <name>

# 3. Network config correct?
docker inspect <name> --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}'
# Must include both pmoves_api and pmoves_data for most Supabase services.

# 4. Internal Kong reachable?
docker run --rm --network pmoves_api curlimages/curl:latest \
  -sS -o /dev/null -w "%{http_code}\n" http://pmoves-supabase-kong-1:8000/
# Expect 404 (alive, route not configured) — not 000 (unreachable).

# 5. Restart count climbing?
docker inspect <name> --format 'Restarts: {{.RestartCount}} | StartedAt: {{.State.StartedAt}}'
```

### Symptom → fix map

| Error fragment | Root cause | Fix location |
|---|---|---|
| `Bad key size` (AES) in Realtime | `DB_ENC_KEY` wrong size | `bootstrap/registry.json` `random_urlsafe 16` |
| `Non-hex character` | Corrupt `random_hex` secret | `make env-setup ARGS=--accept-defaults` |
| `EAI_AGAIN <short-id>` | Next.js resolving container ID | `HOSTNAME=0.0.0.0` in service env |
| `deno.land ... name resolution` | External DNS via embedded resolver | `dns: [1.1.1.1, 8.8.8.8]` on service |
| `container oom` events | Kong worker-count multiplication | `KONG_NGINX_WORKER_PROCESSES=1` |
| `NetworkSettings.Ports` empty on multi-port | Docker Desktop Windows quirk | `KONG_PROXY_BIND=0.0.0.0` |

---

## Stack lifecycle commands (Known Roads)

| Operation | Make target |
|---|---|
| Start stack | `make -C pmoves supa-start` |
| Stop stack | `make -C pmoves supa-stop` |
| Stop both CLI + compose | `make -C pmoves supa-stop-all` |
| Full restart | `make -C pmoves supa-restart` |
| Status snapshot | `make -C pmoves supa-status` |
| Health check | `make -C pmoves supa-health` |
| Runtime reconcile (CLI vs compose) | `make -C pmoves supa-runtime-reconcile` |

**Never** use raw `docker compose up -d supabase-*` — the damage-control
hooks will block it because it bypasses the `COMPOSE_ENV_FILES` chain
that Make targets enforce.

---

## Related

- `.claude/CLAUDE.md` — Known Roads table and PR workflow
- `pmoves/docs/operations/DAMAGE_CONTROL_RECOVERY.md` — hook deadlock recovery
- `pmoves/scripts/supabase/generate-keys.sh` — JWT + secret generation
- `pmoves/scripts/bootstrap_env.py` — registry-driven env population + self-heal
- `pmoves/tools/brand_defaults.py` — post-secrets-funnel alias layer
- `pmoves/bootstrap/registry.json` — declarative service variable registry
