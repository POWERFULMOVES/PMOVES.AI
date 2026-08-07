# DARKXSIDE Fan-Out Brief — Haven MANET + Reticulum Sovereign Mesh

> **GRAPHITI_MARK:** DARKXSIDE-FANOUT::HAVEN-RETICULUM-MESH::2026-08-06
> **From:** CRUSH-GLM52 (SPARK)
> **To:** DARKXSIDE (operator + hardware deployment) → Agent Zero (orchestration) → Archon (RNS integration)
> **Priority:** P1 — Physical mesh layer for offline PMOVES operations
> **Hardware:** 2× Raspberry Pi 5 + 2× Jetson Orin Nano + Haven parts (MM8108 HaLow, RNode LoRa boards)
> **Companion docs:** `docs/Haven-v3.md`, `docs/Reticulum-Network-Blueprint-v1.md`

## Architecture — PMOVES Rides on Physical Mesh

```
PMOVES.AI Agents (CHIT, Geometry Bus, NATS, Crush, Agent Zero)
    ↓ rides on
Tailscale/Headscale (fleet mesh VPN — operational, KVM hub at pmoves-kvm4-2)
    ↓ extended by
Reticulum (encrypted identity-based L7 routing — NEW, rides on Tailscale TCP interfaces)
    ↓ transports over
Haven MANET (802.11s HaLow mesh + BATMAN-adv — 4 physical nodes)
    ↓ physical layer
Wi-Fi HaLow (900MHz, 3.7+ mile range) + LoRa RNodes (extreme range, 500-byte MTU)
```

### Why This Matters

1. **Offline operation** — Haven nodes self-heal, no internet needed. PMOVES agents coordinate over pure mesh when WAN is down.
2. **CGP packets fit LoRa** — CHIT Geometry Bus was designed for this: 500-byte MTU, compact state vectors, holographic compression (documented in `pmoves/docs/PMOVESCHIT/Integrating Math into PMOVES.AI.md`).
3. **Fordham Hill pilot** — community mesh for the Bronx neighborhood. Haven provides the physical layer, PMOVES provides the AI layer.
4. **Disaster response** — St. Maarten tenant. Haven mesh deploys instantly, PMOVES agents coordinate on it.
5. **Grant proposal §3.1** — "Resilient connectivity — Tailscale, Headscale, MANET overlays" Q4 2026 target.
6. **Sovereign identity** — Reticulum's cryptographic identity addressing aligns with CHIT signing cards. Agents have identity on the mesh independent of any cloud.

## Fleet Node Plan — 4 Mesh Nodes

### Hardware Allocation

| Node | Hardware | Role | Haven Type | RNS Type |
|------|----------|------|------------|----------|
| **Haven-Alpha** | Pi 5 + MM8108 HaLow + 4-cell battery hat | Mesh backbone | Full Haven (OpenWRT + 802.11s + BATMAN-adv) | RNS on node (Advanced) |
| **Haven-Bravo** | Pi 5 + MM8108 HaLow + 4-cell battery hat | Mesh backbone | Full Haven | RNS on node (Advanced) |
| **Haven-Charlie** | Jetson Orin Nano (existing fleet) | Edge compute + GPU | RNS bridge (joins via WiFi from Alpha/Bravo) | RNS only (Easy) |
| **Haven-Delta** | Jetson Orin Nano (existing fleet) | Edge compute + GPU | RNS bridge (joins via WiFi from Alpha/Bravo) | RNS only (Easy) |

### Why 2 Pi + 2 Jetson Works

The Haven docs say "any two compatible devices create a working link." The 2 Pis form the **HaLow long-haul backbone** (3.7+ mile range at 900MHz). The 2 Jetsons bridge into the mesh via standard WiFi from the Pis' AP and run `rnsd` — they get full Reticulum identity routing + ATAK + PMOVES agent coordination. The Jetsons also bring **GPU compute** to the mesh edge — they can run Ollama inference, ComfyUI rendering, and Agent Zero workflows entirely offline.

The 3rd Pi 5 already has an enclosure (per operator). The 2 Jetsons + 1 Pi 5 need enclosures — **3D printable on the Snapmaker/BambuLab via OrcaSlicer**.

### Network Topology

```
                    Internet (optional)
                        |
                   [KVM4-2 / SPARK]
                   Tailscale Hub
                   NATS :4222
                        |
          Tailscale TCP Interface (port 4243)
                        |
              ┌─── Haven-Alpha (Pi 5) ───┐
              │   HaLow 900MHz backbone  │
              │   RNS (Advanced mode)    │
              │   BATMAN-adv + 802.11s   │
              └──────────┬───────────────┘
                         │
                    HaLow mesh
                         │
              ┌─── Haven-Bravo (Pi 5) ───┐
              │   HaLow 900MHz backbone  │
              │   RNS (Advanced mode)    │
              └──┬───────────────────┬───┘
                 │ WiFi AP            │ WiFi AP
         ┌───────┴──────┐    ┌───────┴──────┐
         │ Haven-Charlie│    │ Haven-Delta  │
         │ Jetson Orin  │    │ Jetson Orin  │
         │ RNS (Easy)   │    │ RNS (Easy)   │
         │ Ollama GPU   │    │ ComfyUI GPU  │
         │ Agent Zero   │    │ Agent Zero   │
         └──────────────┘    └──────────────┘
```

## DARKXSIDE Provisioning Plan

### Phase 1: Hardware Build (DARKXSIDE — physical)

1. **Assemble 2 Pi 5 Haven nodes** per `docs/Haven-v3.md`:
   - Pi 5 + MM8108 HaLow radio + 4-cell battery hat
   - Flash OpenWRT/MorseMicro image (`github.com/buildwithparallel/openwrt-morse-rpi5`)
   - Configure 802.11s mesh + BATMAN-adv on channel 28, 8MHz width
   - Set TX power to 26 dBm (MM8108 integrated PA)
   - Configure WPA3-SAE encryption (Type III)

2. **Flash RNode LoRa boards** for extreme-range sidecar:
   - Use `pmoves-reticulum-rnodes` repo (already forked)
   - Pre-built `.bin` at `releases/tag/v1.75-neopixel`
   - LoRa params: 915 MHz / 125 kHz / SF7-9 / CR6 / 17 dBm

3. **Print enclosures** via OrcaSlicer → Snapmaker/BambuLab:
   - Pi 5: MOROSX case (public domain on Printables)
   - Jetson Orin Nano: search Printables for "Jetson Orin Nano case" or design in OrcaSlicer
   - Slice and print at `http://<spark-ip>:8141`

4. **Install RNS on Jetsons** (both):
   ```bash
   pip3 install rns
   # Config: see RNS Easy Mode below
   ```

### Phase 2: RNS Configuration (Archon — implementer)

#### Easy Mode (Jetsons — no OpenWRT needed)

Each Jetson runs RNS over WiFi, discovering the Haven mesh transparently:

```ini
# /root/.reticulum/config on Jetson
[reticulum]
share_instance = Yes
enable_transport = Yes
instance_control_port = 37428

[interfaces]
[[Haven Mesh]]
type = AutoInterface
enabled = Yes
devices = wlan0
group_id = pmoves

[[Tailscale Bridge]]
type = TCPClientInterface
enabled = Yes
target_host = pmoves-kvm4-2
target_port = 4243
```

#### Advanced Mode (Pi nodes — full Haven)

```ini
# /root/.reticulum/config on Pi (OpenWRT)
[reticulum]
share_instance = Yes
enable_transport = Yes
instance_control_port = 37428

[interfaces]
[[HaLow Mesh Bridge]]
type = AutoInterface
enabled = Yes
devices = br-ahwlan
group_id = pmoves

[[LoRa RNode]]
type = RNodeInterface
enabled = Yes
port = /dev/ttyUSB0
frequency = 915000000
bandwidth = 125000
spreadingfactor = 7
codingrate = 6
```

#### Tailscale Long-Haul Bridge (on KVM4-2)

```ini
# /root/.reticulum/config on KVM4-2
[reticulum]
share_instance = Yes
enable_transport = Yes

[interfaces]
[[Fleet Bridge]]
type = TCPServerInterface
enabled = Yes
listen_ip = 0.0.0.0
listen_port = 4243
```

This makes KVM4-2 the Reticulum hub — any PMOVES node on the tailnet can join the mesh overlay via TCP. Haven nodes in the field connect through it. The blueprint doc proved this works (Florida→Venezuela demo).

### Phase 3: PMOVES Integration (Archon — implementer)

1. **NATS subjects** — Reticulum ↔ PMOVES bridge:
   - `reticulum.message.received.v1` — inbound mesh message (from Haven/LoRa)
   - `reticulum.message.sent.v1` — outbound mesh message (to Haven/LoRa)
   - `haven.mesh.node.joined.v1` — new Haven node detected
   - `haven.mesh.node.left.v1` — Haven node went offline
   - `haven.mesh.health.v1` — periodic mesh health (every 30s)

2. **RNS bridge service** — `pmoves/services/reticulum-bridge/`:
   - Python daemon that runs `rnsd` and bridges to NATS
   - Subscribes to RNS announcements → publishes `haven.mesh.node.joined.v1`
   - Listens on NATS `reticulum.message.sent.v1` → sends via RNS
   - CHIT-signs every message (attribution on the mesh)
   - Port 8220

3. **Agent registry** — add entries:
   - `haven_alpha` / `haven_bravo` — Pi mesh backbone nodes
   - `haven_charlie` / `haven_delta` — Jetson edge compute nodes
   - `reticulum_bridge` — the NATS↔RNS bridge service

4. **CATALOG** — add Reticulum bridge + Haven nodes

5. **Compose service** — `reticulum-bridge` in `docker-compose.yml`:
   - Profile: `["mesh"]`
   - Port 8220
   - Networks: `pmoves_app`, `pmoves_data`, `pmoves_external`
   - Env: `RNS_CONFIG_PATH`, `NATS_URL`
   - Volume: `/dev/ttyUSB0` (for RNode LoRa, if local)

6. **CHIT + Geometry Bus alignment** — CGP packets over LoRa:
   - CGP state vector fits in 500 bytes (Reticulum MTU)
   - The `param_surface` {temperature, top_k, speaking_rate} maps to LoRa params
   - Every mesh message is CHIT-signed (provenance on the mesh)
   - Agent identity = Reticulum cryptographic identity = CHIT signing card

### Phase 4: ATAK Integration (DARKXSIDE — field deployment)

1. Install ATAK on Android EUDs
2. Configure CoT bridge on Pi nodes (per blueprint §"ATAK data flow")
3. ATAK multicast → CoT bridge → Reticulum → remote ATAK
4. No TAK server needed — pure mesh

### Phase 5: PMOVES Agent on Mesh (Agent Zero — orchestration)

1. Agent Zero on Jetson Haven nodes coordinates via Reticulum bridge
2. NATS messages bridge to RNS → reach other Haven nodes
3. Ollama inference runs locally on Jetson GPU (qwen3:30b fits in Jetson memory)
4. ComfyUI renders on Jetson for offline creator pipeline
5. CHIT trail signing works offline — signs locally, syncs when WAN returns

## Enclosure Printing Plan (OrcaSlicer)

| Enclosure | Printer | Model Source | Status |
|---|---|---|---|
| Pi 5 Haven (×2) | Snapmaker or BambuLab | MOROSX on Printables | Need to slice |
| Jetson Orin Nano (×2) | Snapmaker or BambuLab | Printables search or custom | Need to find/design |
| RNode handheld | Snapmaker or BambuLab | Handheld RNode STLs (Printables) | Need to slice |

**OrcaSlicer:** `http://<spark-ip>:8141`
**Obico monitoring:** `http://<spark-ip>:3334` (view on phone)

## Pinokio Apps for Maker Pipeline

Pinokio apps that extend the maker stack:
- `orcaslicer` — OrcaSlicer as a Pinokio app (already running as container)
- `obico` — Obico monitoring
- `moonraker` — Klipper control (for Klipper-converted printers)
- `octoprint` — OctoPrint (for OctoPrint-connected printers)

These can be registered in the `pmoves/configs/pinokio-apps/` registry (from the creator-collab lane).

## PMOVES Mesh vs Tailscale

| | Tailscale (operational) | Haven + Reticulum (NEW) |
|---|---|---|
| **Layer** | L3 VPN overlay | L2 mesh + L7 identity routing |
| **Requires internet?** | Yes (DERP relay coordination) | No (pure mesh) |
| **Range** | Global (via internet) | 3.7+ miles (HaLow) / tens of miles (LoRa/drone) |
| **Identity** | Tailscale account | Cryptographic public key hash |
| **Encryption** | WireGuard | Mandatory (no plaintext possible) |
| **Use case** | Fleet coordination over internet | Offline/disaster/community mesh |

**They compose:** Reticulum's TCP interface rides on Tailscale when internet is available, and falls back to pure Haven mesh when it's not. The agent doesn't know the difference.

## Next Actions

1. **DARKXSIDE:** Assemble 2 Pi 5 Haven nodes (flash, configure HaLow mesh)
2. **DARKXSIDE:** Flash RNode LoRa boards (sidecars for extreme range)
3. **DARKXSIDE:** Print enclosures via OrcaSlicer (Pi 5 + Jetson cases)
4. **DARKXSIDE:** Install `rnsd` on Jetsons + KVM4-2 (Tailscale bridge)
5. **Agent Zero:** Dispatch Archon to implement reticulum-bridge service
6. **Archon:** Build Phase 3 (NATS subjects + bridge service + registry + CATALOG)
7. **Agent Zero:** Validate mesh messaging end-to-end

## Three-Body

- **Delivery:** DARKXSIDE (hardware) + Archon (software)
- **Control:** DARKXSIDE (field deployment + review gate)
- **Memory:** AGNOTE trail + this brief + CHIT-signed mesh messages

---

*Prepared by CRUSH-GLM52 (SPARK). Haven is the physical manifestation of the PMOVES MOF — every mesh node is a pore in the lattice, every Reticulum identity is a CHIT signature. When the internet goes down, the mesh stays up. When the mesh goes down, the agents keep thinking. When the agents come back online, the trail syncs. Sovereign by design.*
