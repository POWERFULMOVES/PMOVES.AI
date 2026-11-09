# Runbook: Persona Room + Voice Host-Affinity Go-Live

**Audience:** a node agent (`fleet-node-deployer`) or operator running on a fleet
node. Every step is a Known-Road `make` target or a self-verifying script — no
interactive prompts. Each step has a **verify** with expected output; a non-zero
exit means **stop and report**, do not continue.

All code is already on `main`: host-affinity routing `#2305`, compose env
passthrough `#2307`, persona compose overlay + render pipeline (see
`docs/handoffs/persona-room-public-edge.md`). This runbook only **enables and
verifies** — it changes no code.

> Run everything from the repo root. Targets are `make -C pmoves <target>`.
> Use Tailscale **hostnames** (`pmoves-<node>`), never raw IPs.

---

## Part A — Persona living-doc room → `persona.pmoves.ai`

Runs on the **edge host** (the node running the Traefik edge). Serves the
RENDERED living-doc (a2ui shell + PreTeXt HTML + Remotion walkthrough) on a
**public** route (no forward-auth). It does NOT expose the OpenRoom operator
desktop (that adapter, Mavis-5090, stays private).

### A0. Preconditions (verify before proceeding)

```bash
# Traefik edge up → the external network must already exist:
docker network inspect pmoves_external >/dev/null 2>&1 \
  && echo "edge network OK" || { echo "STOP: bring up the Traefik edge first (docker-compose.traefik.yml)"; exit 1; }

# DNS: persona.pmoves.ai must resolve to the edge host (Cloudflare; *.pmoves.ai cert):
getent hosts persona.pmoves.ai || nslookup persona.pmoves.ai || \
  echo "WARN: persona.pmoves.ai does not resolve yet — create the DNS record before A3 verify"
```

### A1. Render the static bundle

```bash
make -C pmoves persona-render
# verify: the three surfaces landed
test -f pmoves/rooms/persona/dist/index.html \
  && test -f pmoves/rooms/persona/dist/walkthrough.mp4 \
  && test -f pmoves/rooms/persona/dist/pretext/index.html \
  && echo "bundle OK" || { echo "STOP: render incomplete"; exit 1; }
```

Notes: `persona-render` runs PreTeXt (`uv … pretext build web`) + Remotion
(`npm … render:provenance:file`, pulls headless chromium on first run) and
assembles `rooms/persona/dist/` (gitignored). First run is slow (chromium
download). If the Remotion step fails, the PreTeXt panel + shell still serve; the
walkthrough slot degrades to an "authored" link.

### A2. Bring the service up (Traefik auto-discovers it)

```bash
make -C pmoves up-persona
make -C pmoves persona-health   # container should be Up
```

### A3. Verify the public route

```bash
curl -sS -o /dev/null -w '%{http_code}\n' https://persona.pmoves.ai        # expect 200
curl -sS https://persona.pmoves.ai/pretext/ | grep -qi '<html' && echo "pretext OK"
curl -sS -o /dev/null -w '%{http_code}\n' https://persona.pmoves.ai/walkthrough.mp4  # expect 200/206
```

### A-rollback

```bash
make -C pmoves down-persona
```

---

## Part B — Voice host-affinity routing (any flute-gateway node)

Turns on capability-based cross-node routing: a cast for engine `X` is
host-swapped to the selected up-node's Tailscale hostname (`pmoves-<node>`),
falling back to the single configured URL when disabled / no node up.

### B0. Preconditions

```bash
# flute-gateway must be up and healthy on this node:
curl -sf http://127.0.0.1:8055/healthz >/dev/null \
  && echo "gateway OK" || { echo "STOP: start the voice stack (make -C pmoves up-voice)"; exit 1; }
```

The node(s) you list must be reachable at `pmoves-<node>` over the tailnet and
actually running the target engine (e.g. `ultimate_tts` on port 7860).

### B1. Enable (opt-in; default is fail-open/off)

Set these where the flute-gateway compose reads env (the launch env / env file —
they are **non-secret** config, passed through by `#2307`):

```bash
VOICE_HOST_AFFINITY=1
VOICE_FLEET_NODES=kvm4-2,spark,5090   # the node ids currently UP (comma-sep)
```

Then recreate the gateway so it picks them up:

```bash
make -C pmoves up-voice     # or: docker compose ... up -d flute-gateway
```

### B2. Verify (self-checking — exits non-zero on failure)

```bash
# Assert host-affinity is active and a node was chosen:
make -C pmoves voice-host-affinity-smoke

# Assert a SPECIFIC node:
EXPECT_NODE=kvm4-2 make -C pmoves voice-host-affinity-smoke

# Prove the endpoint works even with routing off (fail-open is a PASS):
REQUIRE_NODE=0 make -C pmoves voice-host-affinity-smoke
```

The smoke wraps `scripts/voice/host_affinity_smoke.sh` (curl + python3 only),
reads `FLUTE_API_KEY` from the running container, POSTs a cast, and asserts the
response `node` field. Override `GATEWAY_URL`, `PROVIDER`, `ENGINE`,
`EXPECT_NODE`, `REQUIRE_NODE` via env.

**Interpreting `response.node`:** the selected node id (e.g. `kvm4-2`) — the cast
was routed to `pmoves-kvm4-2`. Empty/`null` = fail-open (routing disabled, the
engine has no `host_affinity` row, or no listed node is up).

### B-rollback

```bash
# unset VOICE_HOST_AFFINITY (or set =0), then recreate the gateway:
make -C pmoves up-voice
# confirm fail-open:
REQUIRE_NODE=0 make -C pmoves voice-host-affinity-smoke
```

---

## Where it lives

| Thing | Path |
|---|---|
| Routing seam | `pmoves/services/flute-gateway/persona_selector.py` (`resolve_engine_target`) — `#2305` |
| Synthesis wiring | `pmoves/services/flute-gateway/main.py` (`/v1/voice/synthesize`) |
| Compose env passthrough | `pmoves/docker-compose.yml` → `docker-compose.media.yml` — `#2307` |
| Engine→node table | `pmoves/configs/tts-engine-capabilities.yaml` (`host_affinity`) |
| Voice smoke | `pmoves/scripts/voice/host_affinity_smoke.sh` · `make voice-host-affinity-smoke` |
| Persona compose | `pmoves/docker-compose.persona.yml` · `config/nginx/persona.conf` |
| Persona targets | `make persona-render` / `up-persona` / `persona-health` / `down-persona` |
| Persona edge handoff | `pmoves/docs/handoffs/persona-room-public-edge.md` |
