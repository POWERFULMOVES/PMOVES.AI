# Network planes and package sharing — what is wired vs what is optimized

**Node:** 4090 (Windows, Docker Desktop) · **Date:** 2026-09-03 · **Status:** measured

Every number here was measured on this node in one session. Where a claim is
unverified on other nodes, it says so. Anchors (the make targets and scripts
that reproduce each finding) are named inline so this is reachable by grep from
the failure site, not only from this file.

---

## 1. Three network planes, and why a `ports:` line can be a no-op

```
plane 3   Tailscale mesh ───────── advertises only what plane 2 holds
plane 2   host namespace ───────── published ports + Pinokio engines live here
plane 1   Docker internal bridges ─ pmoves_app/api/bus/data/monitoring
```

Measured on this node:

| network | `internal` |
|---|---|
| `pmoves_data`, `pmoves_api`, `pmoves_app`, `pmoves_bus`, `pmoves_monitoring` | `true` |
| `pmoves_external` | `false` |

Tailscale runs here as a **host service** (`PMOVES-4090`, os `windows`), not a
container, so it shares plane 2. Pinokio engines are host processes — OmniVoice
answered on `:8055`. Compose reaches back to them through
`extra_hosts: host.docker.internal:host-gateway`, which is the **one-way door
from plane 1 to plane 2**.

**Consequence:** Tailscale cannot advertise a port Docker never published.
Publishing to the host is link one; the mesh is link three. Break link one and
the mesh is irrelevant. This is why services declaring a `ports:` line are
still invisible over the tailnet.

Reproduce: `make -C pmoves net-reality PORTS_ONLY=1`

---

## 2. What `internal: true` actually does to published ports

A container attached **only** to internal networks stores its port binding and
never activates it. No error, no warning.

```
PortBindings   map[6333/tcp:[{0.0.0.0 6333}]]   <- what was ASKED
docker port    (empty, exit 0)                  <- what HAPPENED
```

`docker port` exits **0 with empty output** when nothing is published, so
testing `$?` proves nothing — test for a non-empty result.

### This is not in Docker's official documentation

Checked the Compose file reference, engine networking overview, bridge driver
page, and packet-filtering page. The only official statement is:

> `internal`, when set to `true`, lets you create an externally isolated network.

That describes **egress**. Nothing official addresses published **ingress**.

The behavior is tracked at **[moby/moby#36174](https://github.com/moby/moby/issues/36174)**
— open since 2018, filed on **native Linux Engine**, still active 2025-08.
So it is an upstream limitation, **not** a Docker Desktop quirk. Three separate
claims made during this work — "universal Docker behavior", "Docker Desktop
only", and "Linux Engine can publish from an internal bridge" — were all
unsourced. Trust the measurement, not the explanation.

### The upstream workaround does not work here

That thread recommends a normal bridge with
`com.docker.network.bridge.enable_ip_masquerade: "false"` to keep isolation
while allowing publishing. Tested on this node rather than repeated:

| config | publishes | egress |
|---|---|---|
| `internal: true` | no | **blocked** |
| `enable_ip_masquerade: false` | **yes** (`127.0.0.1:18098` → 200) | **REACHED** |

It publishes but does **not** isolate here, because Docker Desktop runs a
second NAT layer inside its VM and disabling the bridge masquerade only removes
the Linux hop. Sound advice on Linux; silently useless on this node. Re-test
per platform before adopting.

---

## 3. The remedy is already specified — do not invent one

`docs/operations/DOCKER_NETWORK_HARDENING.md` already carries both rules:

- **Rule 1** — services not needing LLM API calls or pip installs **must never**
  appear in `pmoves_external`. It is the internet-capable bridge shared with
  Agent Zero, Archon and Hi-RAG. Attaching a service there to solve a
  *publishing* problem is a security regression, not a fix.
- **Rule 4** — on Docker Desktop Windows, bind `0.0.0.0` and restrict at the
  Tailscale ACL layer. Never rely on IP-specific binds on Windows hosts.

The correct tier is the **`x-network-tailnet-published`** anchor
(`internal: false` + the Windows bind caveat), listed in that doc under
"Pending: Network-Tier Hardening Anchors (PR-A)". Verified absent from compose
as of this date — PR-A has not landed, and the doc says it needs the
`COMPOSE_EDIT=1` damage-control override.

### Which services actually need publishing

Settled by evidence, not by role-guessing. `scripts/smoke-tests.sh:335-338`
probes `localhost:6333`, `:7474`, `:7687` — **all connection-refused today**.
Qdrant, Neo4j and Meilisearch have real host-side consumers (smoke tests,
Qdrant backups) and are therefore PUBLISH, whatever their datastore role
suggests. An agent triage pass that reasoned only from service roles marked
those three INTERNAL and was wrong on all three.

---

## 4. Package sharing: Pinokio's model vs ours

**Pinokio's default is sharing; isolation is opt-in.** Measured at
`PINOKIO_HOME` (`C:/pinokio` on this node — discover it with
`.claude/scripts/pinokio-root.sh`, never hardcode):

- `bin/` holds shared runtimes: `miniconda`, `miniforge`, `npm`, `bluefairy`.
  Documented: *"Pinokio-managed shared tools live under `PINOKIO_HOME/bin`"*,
  and every shell activates a global `base` conda env unless told otherwise.
- `cache/` is **environment-variable redirection** — one shared root behind
  every ecosystem's own cache variable:
  `HF_HOME`, `TORCH_HOME`, `PIP_CACHE_DIR`, `UV_CACHE_DIR`,
  `npm_config_cache`, `XDG_CACHE_HOME`, `XDG_DATA_HOME`, `GRADIO_TEMP_DIR`.

No custom package manager. It hijacks the standard cache variables so every
app, whatever its runtime, deduplicates against one store.

**Docker's default is the inverse:** isolation by default, sharing only if you
build for it. Measured cost on this node:

| image | layers | first layer |
|---|---|---|
| `pmoves-omnivoice` | 16 | `270a1170e7e3` |
| `pmoves-hi-rag-gateway-v2` | 20 | `6f9432833129` |
| `pmoves-agent-zero` | 34 | `89671c415fa7` |

Three different first layers — **no shared base**. Each bakes its own
CUDA/torch stack. `docker system df`: 117 images, **221.7 GB**, 56 GB
reclaimable; build cache **40.7 GB** with 0 active.

The optimized pattern already exists in this repo — BuildKit cache mounts
(`RUN --mount=type=cache,...`) — in exactly **two** Dockerfiles:
`services/media-audio/Dockerfile` and `services/media-video/Dockerfile`.
Proven here, never propagated.

**The correspondence:** a BuildKit cache mount pointed at a shared
`UV_CACHE_DIR` / `PIP_CACHE_DIR` / `HF_HOME` is Pinokio's mechanism expressed
in Docker. Same idea, one level down. That makes uv adoption and cache-mount
propagation the same piece of work, not two.

Do **not** reclaim the 56 GB with a raw prune on this node: it frees space
inside the WSL2 VHDX and returns zero host disk. Use `make -C pmoves docker-prune`.

---

## 5. Anchors

| Question | Command / file |
|---|---|
| Is this port really published? | `make -C pmoves net-reality` (`scripts/audit_network_reality.sh`) |
| One service, one port | `bash pmoves/scripts/published-port.sh <svc> <port>` |
| Where is Pinokio on this node? | `bash .claude/scripts/pinokio-root.sh` |
| Which network tier should a service use? | `docs/operations/DOCKER_NETWORK_HARDENING.md` (Rules 1 and 4, PR-A anchors) |
| Upstream cause | [moby/moby#36174](https://github.com/moby/moby/issues/36174) |

`audit_network_reality.sh` shipped in May and went unused for months because it
had **no make target** — no road reached it, so every "check the known roads
first" pass missed it and the work was redone badly. A tool that cannot be
found is not a known road. That is the reason `net-reality` exists.
