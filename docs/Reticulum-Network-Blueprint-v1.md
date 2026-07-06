# The Reticulum Network Blueprint

> Downloaded 2026-07-03 from the public Notion page linked in `Reticulum-Network-Blueprint-v1.txt`.
> Source: https://app.notion.com/p/dataslayer/The-Reticulum-Network-Blueprint-30f938546f628095bedfe2fc2d89deaf
> Author: Data Slayer / Build With Parallel.
> All collapsed toggles were expanded before capture — this is the complete
> prose (RNode build, firmware, LoRa config, the Haven technical reference with
> config files, ATAK data flow, and Long-Haul mesh-VPN setup). Embedded videos
> show as "Loading…"; GitHub repos and links are inline.

## What is Reticulum?

Reticulum is an open-source, fully decentralized networking stack and routing layer that implements **cryptography as a base layer**. It sits above hardware, treating LoRa / Wi-Fi / Ethernet / serial as interchangeable interfaces, enabling anonymous, autonomous communication without centralized infrastructure.

### Benefits

- **Hardware-agnostic:** bridge dissimilar radios (LoRa ↔ Wi-Fi) via nodes with multiple interfaces.
- **Link-quality-aware routing:** discovers routes, chooses fast links for big transfers; mesh overhead scales **linearly, not exponentially** (no flooding).
- **Multi-transport:** works across many transports and speeds (Morse/code to fiber) in one network.
- **Identity-based addressing:** encrypted by default with origin obfuscated.
- Open-source, sovereign, autonomous, interoperable.

## How Does Reticulum Compare to Meshtastic?

Both use LoRa radios and form decentralized meshes, but solve different problems. **Meshtastic** is a plug-and-play messaging system (flash a cheap board, open the app, chat). **Reticulum** is a networking stack that treats LoRa/Wi-Fi/Ethernet/serial/internet as interchangeable transports, optimized for flexibility, cryptographic identity, and bridging unlike networks.

| | Meshtastic | Reticulum |
|---|---|---|
| Primary goal | Simple LoRa mesh messaging | Transport-agnostic encrypted networking |
| Setup difficulty | Flash and go | Requires configuration + understanding |
| Transports | LoRa only (+ MQTT bridge) | LoRa, Wi-Fi, Ethernet, serial, internet — simultaneously |
| Routing | Flooding-based mesh | Link-quality-aware, non-flooding |
| Encryption | Optional shared AES key — can be left open (plaintext over air) | **Mandatory** — no way to send unencrypted, even with bad config |
| Identity | Node name / short name | Cryptographic identity (public key hash) |
| Scalability | Best with small networks (flooding grows fast) | Scales linearly |
| Hardware | Specific boards (Heltec, T-Beam) | Anything running Python, or used as an RNode |
| Cross-transport bridging | Limited (MQTT gateway) | Native — one node bridges LoRa ↔ Wi-Fi ↔ Ethernet |
| App ecosystem | Mature mobile (iOS, Android) | Growing — MeshChat, Sideband, NomadNet |

**Not competitors — complementary.** Meshtastic is the frictionless gateway; Reticulum is the composable network stack you reach for when you outgrow a simple LoRa mesh.

**Unattended MCU caveat:** Meshtastic runs entirely on a cheap MCU (flash, box it, deploy). An RNode by itself is *just a radio modem* — no routing/app logic on the MCU; it needs an **RNS instance** running on a connected host — a laptop, SBC, or OpenWrt router running the `rnsd` daemon, or a phone hosting a shared RNS instance via Sideband. So a bare-MCU Reticulum node isn't a drop-in unattended deployment — pair the RNode with a small host (Pi / OpenWrt router) running RNS.

## RNode Build Instructions

### Shopping List (community-contributed)

| Category | Item | Notes |
|----------|------|-------|
| Core Hardware | **LilyGO LoRa32 v2.1 (915 MHz)** — ESP32 + SX1276 + OLED | store.rokland.com / amzn |
| Battery | 3.7V LiPo 700 mAh | handheld RNode |
| Antenna | Shark Tooth tri-band (aesthetic) **or any 915 MHz whip** | 915 MHz center-freq preferred for range |
| LED | WS2812B Mini RGB (NeoPixel Adafruit #1612) | |
| RF (opt) | 10–15 cm IPEX/u.FL → SMA pigtail | |
| Enclosure | Handheld RNode STL files (Printables) | |
| Mechanical | M2×6mm screws (≥18), 3/16" neoprene washers | |
| Tools (if needed) | Hot air rework station, fine-tip iron, 26–30 AWG wire | for SMA removal |

Build based on Mark's guide at **unsigned.io** — but it did **not** work out of the box; the mods below were required.

### Hardware mods

- **Antenna:** Shark Tooth is aesthetic; for range use a ~915 MHz whip (SMA male, 900–928 MHz). US LoRa = 902–928 MHz ISM.
- **SMA → IPEX:** removed onboard SMA, switched to the board's IPEX/u.FL (cleaner fit, less PCB strain). IPEX connectors are fragile — secure the pigtail mechanically. Optional.
- **NeoPixel data pin:** Mark's guide says IO12; **IO12 was unreliable — moved DATA to GPIO 13**, which resolved it. (Firmware config must match.)
- **OLED:** to reposition, gently heat the acrylic backing (heat gun, low) to soften adhesive, separate, clean residue. Don't overheat.

### 3D print specs

- Main enclosure via **JLC3DP** — MJF (PA12-HP Nylon), dyed black. Parts: Case_Top ($3.06), Battery_Door ($1.11), Bottom_Small_Battery ($6.42, used), Bottom_Large ($10.27), Bottom_No_Battery ($4.91).
- Small parts via **CraftCloud** (JLC3DP lacks colors/translucent): Power_Switch (PETG, orange), LED_Window + LED_Guide (ABS, translucent), 100% infill.
- STLs on Printables + GitHub.

## Firmware & Software

All firmware, board configs, and build scripts: **https://github.com/buildwithparallel/reticulum-rnodes**
(clone to flash the working build, modify pin mappings e.g. NeoPixel GPIO, adjust board defs, create variants; future boards land in the same repo under separate board dirs.)

Pre-built `.bin`: **releases/tag/v1.75-neopixel**.

### Flashing the RNode

1. **Web flasher** — https://liamcottle.github.io/rnode-flasher/ (use if you just have a `.bin`)
2. `arduino-cli` from an IDE (use if modifying code)
3. CLI `rnodeconf --flash`

### Client applications

- **MeshChat** — desktop (macOS/Windows/Linux), easiest over USB. Most success. (Sometimes must navigate away + back to see latest messages.)
- **Sideband** — Android `.apk` from the public repo (also desktop: Linux/macOS/Windows). Harder with a direct RNode; effortless over default ethernet/wifi interface.

## LoRa Radio Configuration

For two LoRa radios to talk, **radio parameters must match exactly** (frequency, bandwidth, spreading factor, coding rate) — LoRa does not auto-negotiate like Wi-Fi.

| Param | Example | Effect |
|-------|---------|--------|
| **Frequency** | 915.000 MHz | US 902–928 MHz ISM; must match to share a channel; little range effect |
| **Bandwidth** | 125 kHz (common; also 250/500) | higher BW = faster/shorter airtime/less range; lower = slower/better sensitivity |
| **Spreading Factor** | SF7 (fast) → SF12 (extreme range) | biggest range/rate lever; higher SF = far below noise floor but much longer airtime |
| **Coding Rate** | 6 (default; 5–8) | forward error correction; higher = more redundancy/slower |
| **Transmit Power** | 17 dBm | higher = range + power draw + interference |

**Core tradeoff:** LoRa always trades speed for range — can't maximize both. Balanced default: **915 MHz / 125 kHz / SF7–9 / CR6 / 17 dBm**. All nodes in a LoRa segment must be identical or they won't communicate at all.

## How to Use Your RNode

An RNode is just a radio modem. To send/receive you need: **(1)** matching LoRa parameters on every RNode; **(2)** a **client app on a connected host** (MeshChat desktop over USB, or Sideband mobile over USB/Bluetooth). Demo: Heltec V4 RNode + MeshChat (desktop) ↔ T-Beam LoRa32 RNode + Sideband (Android), same LoRa params, direct over LoRa — no internet/infra/server.

## Reticulum on Haven — Technical Reference

Distilled from the GitHub Reticulum README. **Why:** end-to-end encryption by default · transport-agnostic (WiFi/LoRa/serial) · no central infra (works offline) · small footprint · future-proof (LoRa RNodes for extreme range).

### Two deployment approaches

**Easy — Reticulum on EUDs only (no node install):** mesh nodes act as pure IP routers; each end-user device runs a Reticulum client over WiFi; HaLow transport is invisible. Laptop joins the gate's WiFi AP → `10.41.x.x`; phone joins a heltec node's bridged AP → also `10.41.x.x`; both on the same mesh subnet, IP routes over HaLow transparently. **RNS AutoInterface uses UDP multicast** to auto-discover peers. No RNS config / node SSH / node install needed. Apps: Sideband (Android + desktop), MeshChat (desktop), NomadNet (desktop). **Recommended starting point.**

**Advanced — RNS installed on nodes:** enables transport-node relaying (bridge HaLow mesh ↔ LoRa RNode for extreme range), always-on services (NomadNet/LXMF stores), cross-interface routing (HaLow/LoRa/internet), and store-and-forward buffering for offline EUDs.

### Architecture stack

```
Application Layer:  ATAK, Sideband, LXMF, Custom Apps
Reticulum Stack:    AutoInterface (br-ahwlan) | UDPInterface (broadcast) | TCPInterface (clients)
Network Layer:      br-ahwlan (Linux bridge) ← bat0 (BATMAN-adv) + wlan0 (HaLow) + phy1-ap0 (5GHz)
Physical Layer:     HaLow 916 MHz + 5/2.4 GHz WiFi
```

**How HaLow reaches Reticulum:** `wlan0 (HaLow 916 MHz) → bat0 (BATMAN-adv) → br-ahwlan (Linux bridge) → Reticulum`. Reticulum only sees `br-ahwlan` and sends multicast on it — it travels over HaLow because that's what's bridged in. Swap HaLow for LoRa/ethernet bridged into `br-ahwlan` and Reticulum works with **no config change** (radio-agnostic).

### Install & config

```sh
opkg update && opkg install python3 python3-pip
pip3 install rns
```

Config at `/root/.reticulum/config` (identical on gate/point nodes):

```ini
[reticulum]
share_instance = Yes
enable_transport = Yes
instance_control_port = 37428

[interfaces]
[[HaLow Mesh Bridge]]          # label is arbitrary
type = AutoInterface           # multicast peer discovery
enabled = Yes
devices = br-ahwlan            # Linux device to bind
group_id = reticulum

[[UDP Broadcast]]
type = UDPInterface
enabled = Yes
listen_ip = 0.0.0.0
listen_port = 4242
forward_ip = 10.41.255.255
forward_port = 4242
```

`listen_ip = 0.0.0.0` binds all interfaces so config is IP-agnostic. Different radio: `devices = wlan1` (WiFi) / `eth0` (Ethernet). Restart: `/etc/init.d/rnsd restart`.

### Run & monitor

```sh
/etc/init.d/rnsd start && /etc/init.d/rnsd enable
python3 /root/rns_status.py           # dashboard (version, node hash, HaLow radio, interfaces, TX/RX, per-peer RTT)
python3 /root/rns_status.py <peer_hash>   # live PING/PONG
python3 /root/rns_receive.py          # prints dest hash, waits
python3 /root/rns_send.py <dest_hash> "msg"
rnpath -l                             # view paths
```

### ATAK data flow (CoT bridge)

ATAK sends CoT XML to multicast (SA `239.2.3.1:6969`, Chat `224.10.10.1:17012`) → CoT Bridge intercepts, **zlib-compresses**, **fragments if >400 bytes** → sends over encrypted Reticulum link (AutoInterface over HaLow) → remote node decrypts → bridge reassembles/decompresses → re-publishes to local multicast → remote ATAK receives. **No ATAK config needed** (default multicast). **MTU:** Reticulum has a **500-byte packet MTU** (for LoRa); SA beacons (~300–340 B) fit one packet, chat (~700–800 B) needs 2 fragments (~20 ms latency/fragment).

### Troubleshooting

```sh
python3 /root/rns_status.py           # interface up?
ip link show br-ahwlan                # bridge exists?
tcpdump -i br-ahwlan udp port 4242    # multicast working?
iwinfo wlan0 info                     # HaLow signal (high latency)
rnsd -v                               # start errors
python3 -c "import RNS; RNS.Reticulum()"  # config syntax
```

## Reticulum on Haven / OpenWRT / OpenMANET (Advanced)

GitHub: **https://github.com/buildwithparallel/haven-manet-ip-mesh-radio** — extends Haven from a Wi-Fi HaLow mesh node into a full encrypted identity-based overlay. Haven nodes form an **802.11s + BATMAN-adv** mesh (OpenMANET); Reticulum runs on top as an encrypted overlay. Routing at two layers: **L2/L3 mesh (BATMAN-adv)** + **L7 identity routing (Reticulum)**. Sovereign stack: `Radio → IP Mesh → Reticulum Overlay → Applications`. Transport-agnostic (binds the Linux bridge; swap radios without touching higher layers; mix HaLow + Ethernet; wired backhaul into buildings). Ships live status dashboard, peer visibility, send/receive scripts, mesh inspection.

## Reticulum + ATAK

The repo bridges **ATAK over Reticulum**: intercept ATAK multicast CoT → compress/fragment → transport across Reticulum → re-inject multicast remote-side. ATAK devices operate normally — **no TAK server, no internet, no central infra**. Each Haven node is a translation layer: `ATAK Multicast ↔ Reticulum ↔ Mesh ↔ Reticulum ↔ ATAK Multicast`. Yields encrypted tactical messaging, multi-hop propagation, mesh-resilient location sharing — for disaster response, rural/off-grid, events, field exercises.

## Long Haul (Mesh VPNs) — **most PMOVES-relevant**

If two nodes can't bridge over a local link, bridge them "wormhole style" over the internet with a **mesh VPN — Tailscale, Headscale, or WireGuard** (this is how the author messaged an editor in Venezuela).

**Recommended: TCP Server ↔ TCP Client over the tailnet IP:**
- **Node A (server):** MeshChat → Interfaces → Add → *TCP Server Interface* — Listen IP = Node A's Tailscale IP (`100.x.x.x`), Listen Port e.g. `4243`.
- **Node B (client):** MeshChat → Interfaces → Add → *TCP Client Interface* — Target/Host = Node A's Tailscale IP, Port = same `4243`.

Both on the same tailnet → stable long-haul bridge between disconnected Reticulum segments.

> **PMOVES relevance:** this is the exact `Tailscale / Headscale / WireGuard` substrate the fleet already runs. Reticulum rides **on top of** the mesh VPN as an identity-addressed, encrypted-by-default L7 routing layer — orthogonal to and composable with the **Mullvad WG exit-upstream** (#1945), which handles egress-IP privacy (not identity routing). A PMOVES node could run `rnsd` with a `TCPClientInterface` pointed at a KVM's tailnet IP to join fleet Reticulum segments, while the KVM's Mullvad upstream anonymizes the public egress.

## Bonus Builds

**Drone-mounted Reticulum node (SkyMesh):** Heltec V3 LoRa flashed as a Reticulum node on a drone — altitude line-of-sight extends range by tens of miles. Pre-printed SkyMesh mount or DIY STLs.

## Community

- Discord: https://discord.gg/g7h8Jc7Agt · Subreddit: r/ModernRadio

## Change Log (highlights)

- **Feb 23–24, 2026** — overview + Benefits; RNode build mods (NeoPixel IO12→GPIO 13, SMA→IPEX, OLED removal); firmware repo `buildwithparallel/reticulum-rnodes`.
- **Mar 3–4, 2026** — Reticulum-over-HaLow demo on Linux/OpenWRT (MorseMicro HaLow); hardware/enclosure video; optimal LoRa settings.
- **Mar 21–23, 2026** — Bonus Builds (drone SkyMesh); 3D print schematics; inline shopping-list DB; Meshtastic comparison table; encryption-mandatory callout.
- **Mar 25, 2026** — Sideband Android install video.
- **Apr 18, 2026** — **Long Haul (Mesh VPNs)** added (Tailscale/Headscale/WireGuard), Florida→Venezuela demo; MCU-only vs Meshtastic clarification; 3D print vendor details (JLC3DP MJF Nylon; CraftCloud PETG/ABS).
- **May 14, 2026** — "How to Use Your RNode": matching LoRa params + client app; Heltec V4 + MeshChat ↔ T-Beam LoRa32 + Sideband demo.
```
