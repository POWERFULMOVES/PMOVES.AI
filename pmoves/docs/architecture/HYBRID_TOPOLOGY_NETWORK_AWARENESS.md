# Hybrid Topology & Service Network-Awareness — Design Spec (DRAFT for review)

> **Status:** design spec, grounded in the three vendors' official docs (Docker, Tailscale,
> Pinokio 8) + the existing PMOVES topology code. Build to this once reviewed. Private,
> self-hosted server — license/exposure choices are the operator's (see §7).
>
> **Goal:** every service *knows and can report* which networks it is on, across a **hybrid**
> topology of four domains: Docker-internal tiers · Docker-external · Tailscale mesh · Pinokio.
> Extend `services/common/topology.py::TopologyContext` — do not reinvent.

## 1. The four network domains

| Domain | What it is | Reachability | PMOVES today |
|--------|-----------|--------------|--------------|
| **Docker-internal** | user-defined bridge nets with `internal: true` | service-to-service by **name** via embedded DNS `127.0.0.11`; **no internet** | `pmoves_api`, `pmoves_app`, `pmoves_bus` |
| **Docker-external** | bridge net with internet/host egress | outbound internet + `host.docker.internal`; where model downloads happen | `pmoves_external` |
| **Tailscale mesh** | cross-node / cross-device overlay | `tailscale serve` → `https://<node>.<tailnet>.ts.net` (tailnet-private) | exit nodes, gateway kit, Jellyfin-over-TS (planned) |
| **Pinokio** | native local-first apps (not Docker) | binds **localhost** ports; P8 "Phone" panel = QR + local URL; "Home Server" share | Ultimate-TTS :7860, other GPU apps |

### Grounded facts (official docs)
- **Docker:** *"Once connected to a user-defined network, containers can communicate … using container names."* `internal: true` *"block[s] external network access"* while keeping inter-container comms. Embedded DNS = `127.0.0.11`. A container *"may be connected to different types of network"*; routing priority across them is controlled by **`gw-priority`**.
- **Tailscale:** `tailscale serve <target>` maps a local port to a MagicDNS name with auto-TLS; **Serve = tailnet-private (members only)**, **Funnel = public internet**. `-bg` persists across reboots.
- **Pinokio 8:** local-first. Apps bind localhost; the **Phone** panel exposes a QR + local URL (gated on router readiness); a **Home Server** share exists. No built-in reverse-proxy/tunnel documented → **remote exposure = pair Pinokio's port with Tailscale Serve.**

## 2. The reachability matrix (how a caller reaches a service)

| Caller ↓ / Target → | Docker svc (same host) | Docker svc (other node) | Pinokio app (host) | Anything, from a phone |
|---|---|---|---|---|
| **Docker container** | service **name** on a shared net | node's **Tailscale** name:port | `host.docker.internal` **on `pmoves_external`** | — |
| **Host tool** | `localhost:<published>` | node Tailscale name | `localhost:<port>` | — |
| **Other tailnet device** | Tailscale **Serve** URL | Tailscale name/Serve | Serve the Pinokio port | MagicDNS / Serve |

**The Flute→TTS bug, explained by the docs:** flute-gateway is multi-homed on `pmoves_api/app/bus` (internal) **+** `pmoves_external`. Its default route landed on an internal tier with no host path → `host.docker.internal` = "network unreachable." **Fix per Docker docs: set `gw-priority` so `pmoves_external` is the default-route network** for services that must reach the host/internet. This is a real, grounded fleet-wide fix, not a one-off.

## 3. Extend `TopologyContext` (the code change)

`services/common/topology.py` already models `TopologyMode` (DOCKED/HYBRID/STANDALONE) + `external_services`. Add:

```python
# new fields on TopologyContext
docker_networks: frozenset[str]     # tiers this service is on (pmoves_api/app/bus/external)
tailscale: TailscaleInfo | None     # {node, tailnet, serve_url, tags} if tailnet-exposed
pinokio_endpoints: dict[str,str]    # {app_slug: "http://host.docker.internal:PORT"} for native apps
```
- Resolve from env: `PMOVES_NETWORKS` (compose injects the service's `networks:` list), `TAILSCALE_SERVE_URL`/`TS_NODE`/`TS_TAGS`, `PINOKIO_ENDPOINTS` (json map).
- Keep backward-compat with `DOCKED_MODE`/`TOPOLOGY_MODE`.
- Add helpers: `on_network(name)`, `is_tailnet_exposed()`, `pinokio_url(slug)`, `resolve(target)` → picks Docker-name vs Tailscale-name vs host-gateway per the matrix.

## 4. Service self-reporting (make the fleet self-describing)

Every service enriches `/healthz` (or adds `/topology`) to emit:
```json
{"service":"media-video","mode":"docked",
 "docker_networks":["pmoves_app","pmoves_bus","pmoves_external"],
 "tailscale":{"exposed":false},
 "pinokio_reachable":["ultimate-tts@host.docker.internal:7860"]}
```
The two new media services (media-audio/media-video) are the first adopters; roll the helper out from `services/common`.

## 5. Registry & namespace integration

- **`PORT_REGISTRY.md`** stays the port source-of-truth (ranges + assignments); `service_registry.py` already resolves URLs with `external_host`/`external_port`.
- **GHCR namespace** `ghcr.io/powerfulmoves/*` = the image registry; every service image lives there.
- Network-awareness reads from these, never hard-codes.

## 6. Auto-networking rules (fleet convention)

1. Internal tiers = `internal: true`; only services needing internet/host join `pmoves_external`.
2. Any service on `pmoves_external` **and** an internal tier sets **`gw-priority`** so `pmoves_external` is the default route (fixes the host-unreachable class).
3. Cross-node service calls use **Tailscale names**, never a node's LAN IP (see `feedback_no_tailscale_ips`).
4. Native GPU apps (Pinokio) are reached by Docker via `host.docker.internal` (needs `extra_hosts: host-gateway`) and by remote devices via **Tailscale Serve** of the app's port.
5. Public exposure is **Serve (tailnet-private) by default**; Funnel only by explicit operator decision.

## 7. Private-server note (license/exposure = operator's call)
This is a private, self-hosted fleet. The Apache/MIT/BSD rule governs what is **shipped/distributed**, not what is **run privately**. **YOLO (AGPL) is fine to run on the Jetsons/private nodes** — media-video will offer YOLO as a first-class detector (ideal on Jetson/TensorRT) with **DETR (Apache) as the selectable default** for any shippable path. Exposure (Serve vs Funnel) is likewise the operator's call.

## 8. Sources
**Official:** Docker networking — https://docs.docker.com/engine/network/ · Docker compose networking — https://docs.docker.com/compose/how-tos/networking/ · Tailscale Serve — https://tailscale.com/kb/1242/tailscale-serve · Pinokio 8 — https://cocktailpeanutlabs.github.io/p8/
**Internal:** `services/common/topology.py`, `services/common/service_registry.py`, `pmoves/docs/operations/PORT_REGISTRY.md`, `.claude/context/tier-architecture.md`, `NETWORKING_STACK_REVIEW.DRAFT.md`.
