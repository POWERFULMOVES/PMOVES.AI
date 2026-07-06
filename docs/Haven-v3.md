# Haven – MANET IP Mesh Radio (Field Manual)

> Downloaded 2026-07-03 from the public Notion page linked in `Haven-v3.txt`.
> Source: https://app.notion.com/p/dataslayer/Haven-MANET-IP-Mesh-Radio-255938546f6280ea90abe7a58142d314
> Author: Data Slayer / Build With Parallel. This captures the manual's prose +
> architecture. The deep hardware-build toggles (Gear/BOM shopping tables,
> Setting-Up steps, Building-OpenWRT-from-scratch, Regulatory, Applications,
> Advanced) are present on the live page but were NOT re-extracted here — their
> affiliate-link tokens trip the browser tool's output filter. To capture that
> build detail cleanly, use duplicate-then-fetch: hit Notion's "Duplicate" on the
> public page to copy it into your workspace, then the Notion MCP `fetch` returns
> the entire block tree (companion `Reticulum-Network-Blueprint-v1.md` was fully
> expanded and captured). The architecture below is what matters for the PMOVES
> mesh/egress reconciliation.

## Haven 2 is Here

Most of the build — components, assembly, field tests, mesh config — is shared across Haven 1 and Haven 2. Where they diverge, look for the Haven 1 and Haven 2 waypoints throughout this manual.

### What's new in Haven 2?

- Raspberry Pi 5 — quad-core ARM @ 2.4 GHz, up to 16 GB RAM
- Morse Micro MM8108 — ~33% more throughput, better range, native multi-region support
- 4-cell battery hat — doubles field runtime over the previous 2-cell Waveshare hat
- Mesh VPN — WireGuard + Tailscale built in, Headscale-compatible for fully self-hosted control
- LoRa sidecar support — connect a Meshtastic / Reticulum RNode board (Heltec, RAK4631, Seeed XIAO, Walter, Muzi Works Base Duo, Null Hop Mesh Toad) and the drivers are already there

## Living Field Manual

This guide evolves with every Haven update. Lifetime access to all future improvements, fixes, and mission builds.

## Start Here — How Haven Networks Actually Work

Haven is a mesh networking system, which means it requires at least TWO compatible devices to create a working link (think walkie-talkies — one device alone cannot form a network).

Advanced users can extend Haven further by adding sovereign routing layers like **Reticulum**, enabling encrypted identity-based networking on top of the mesh.

### Minimum Setup

Any two compatible Wi-Fi HaLow devices. They do NOT both need to be full Haven builds. Examples that work:

- Two Haven nodes
- One Haven node + a Morse Micro USB dongle
- One Haven node + a Heltec HaLow dongle
- Two HaLow client devices (no Haven required)
- Multiple mixed HaLow nodes — any combination should interoperate

Haven is a fully packaged, ready-to-deploy node speaking standard Wi-Fi HaLow mesh (802.11s), so you are not locked into a single hardware type. Once two compatible devices are active, they automatically connect and create a self-healing mesh network.

### Why Two Devices?

Haven uses true mesh networking (802.11s): each node connects directly with others, no central router required, and the network expands as you add more nodes.

### Pro Tip (Cheaper Way to Start)

You don't need two full Haven builds. Many builders start with 1 Haven node + 1 lightweight HaLow client (Morse Micro USB, Heltec dongle, XIAO-based build, etc.) to test range and performance while keeping costs low.

## Why Haven hits different

A commodity-parts alternative to $8,000+ MPU5-class radios — built from gear you can actually buy, mostly from English-speaking allied supply chains, with zero lock-in.

- **Mostly allied supply chain.** Raspberry Pi manufactured in Wales (UK); Morse Micro HaLow silicon designed in Sydney, Australia; most of the rest off-the-shelf from U.S./E.U. distributors (DigiKey, Mouser, Amazon).
- **Standard removable 21700 lithium-ion cells.** No proprietary battery pack.
- **Overclocked HaLow radio.** Up to 27 dBm TX (Haven 1 firmware overclock; Haven 2 reaches 26 dBm via its integrated PA) vs. ~22 dBm on most stock HaLow gear — roughly 3.2× more output power, all within FCC limits.
- **True 802.11s mesh + BATMAN-adv.** Standards-based, self-healing routing on a unified Layer 2 mesh — not a proprietary vendor protocol.
- **Sovereign routing layer.** Optional Reticulum on top for encrypted, identity-based comms — independent of any infrastructure or cloud.
- **Fully open source.** OpenWRT base, OpenMANET / MorseMicro images, install scripts, integrations on GitHub.
- **No recurring fees or subscriptions.** Buy the parts once.
- **Extensible — bring your own payload.** The Pi's USB, GPIO, and I²C are open. Bolt on an RTL-SDR, a LoRa sidecar (Meshtastic / Reticulum RNode), GPS, sensor, display.
- **3D-printable enclosure.** The MOROSX case is public-domain on Printables.
- **You actually understand your radio.** Building it yourself means you learn the entire stack — hardware, OS, mesh routing, antennas, power.

## Key Features

### Wi-Fi HaLow (802.11ah) Long Haul

Haven uses Wi-Fi HaLow for the long-distance link between nodes — operates around 900 MHz in the U.S. (roughly one-third the frequency of 2.4 GHz Wi-Fi). Longer wavelength travels farther and penetrates trees, walls, brush, terrain. Your phone still connects locally over normal Wi-Fi; HaLow is the long-haul backhaul between nodes.

### Transmit Power

Much stock HaLow gear sits around 21–22 dBm (~125–160 mW). Haven can push to 27 dBm (~500 mW) — that's Haven 1's firmware overclock on the MM6108; Haven 2's MM8108 tops out at 26 dBm from its integrated PA. Because dBm is logarithmic, 22→27 dBm is ~3.2× more output (vs 21 dBm, ~4×), while staying below the FCC's 30 dBm EIRP / 1 W ceiling with correct antenna setup.

### Proven Throughput

| Version | HaLow Silicon | Max raw PHY rate |
|---------|---------------|------------------|
| Haven 1 | Morse Micro MM6108 | 32.5 Mbps |
| Haven 2 | Morse Micro MM8108 | 43.3 Mbps |

(Measured with two nodes on channel 28 at 8 MHz channel width — real-world internet download/upload, not just raw point-to-point.)

### Mesh Networking

Every node connects directly with every other node — no central router; the network heals itself if a link goes down.

- **802.11s Mesh** — standards-based Wi-Fi mesh built into Linux/OpenWrt; mesh stations form peer links and forward across multiple wireless hops; uses mesh path selection (HWMP default routing).
- **BATMAN-adv** — makes the mesh behave like one shared Layer 2 network; forwards on MAC addresses instead of IP routes; creates a virtual `bat0` interface so normal apps act like they're on a regular LAN.

### Type III Encryption

WPA3-SAE (aka HaLow "Type 3"). Unlike WPA2-Personal, SAE does not expose a reusable handshake for offline password cracking. Use a strong passphrase.

### Portable 21700 Battery Power

Runs from removable 21700 lithium-ion cells via a Waveshare battery HAT. Haven 1 can use the 2-cell or 4-cell hat; Haven 2 should use the 4-cell for higher power draw.

## Choose Your Build

Two hardware paths, one manual. The mesh works the same on both — only the hardware BOM, OpenWRT image, and build-from-scratch toolchain fork.

| | Haven 1 | Haven 2 (new) |
|---|---------|---------------|
| Compute | Raspberry Pi 4 Model B (8GB) | Raspberry Pi 5 |
| HaLow Radio | Morse Micro MM6108 | Morse Micro MM8108 |
| Max Modulation | 64-QAM (MCS 0–7) | 256-QAM (MCS 0–9) |
| TX Power | 27 dBm (firmware overclock) | 26 dBm (integrated PA) |
| Peak Throughput | ~32.5 Mbps @ 8 MHz | ~43.3 Mbps @ 8 MHz |
| Regions | US-focused | US, EU, GB, AU, CA, JP |
| Status | Battle-tested — hundreds in the wild | New — instructions |
| Best for | Most US builders today | EU/intl, max throughput, future-proofing |
| Power | 2× 21700 hat (9,000 mAh) | 4× 21700 hat (18,000 mAh) |
| OS | OpenMANET | MorseMicro OpenWRT |
| Enclosure | MOROSX public-domain (Printables) | No enclosure yet |

Everything else is shared: networking model, BATMAN mesh config, Mumble PTT, **Reticulum + ATAK stack**, weatherproofing, and the MOROSX case behave identically on both.

## Manual sections (headers; detail in the live toggles)

Gear / BOM / Components · Setting Up Your Haven Nodes · Charging, Battery Life & Daily Use · Weather Proofing · Accessing Your Node + Troubleshooting Connectivity · Haven 1 Case by MOROSX · Building OpenWRT/OpenMANET from scratch · Regulatory & Regional Support · Performance · Applications · Advanced

## Related Builds

- Get the full **Reticulum Network Blueprint** (companion build — see `Reticulum-Network-Blueprint-v1.md`).

## Community

- Discord: https://discord.gg/g7h8Jc7Agt
- Subreddit: r/ModernRadio
- Builder Rebate: https://tally.so/r/44rlgk

## FAQ (selected)

- **Pi 5 support?** Yes, as of Haven 2 (May 2026) — needs the MM8108 chip + the OpenWRT image at `github.com/buildwithparallel/openwrt-morse-rpi5`.
- **Offline ATAK for a whole team?** Yes — works completely offline, no internet/SIM/uplink; each unit is a standalone HaLow mesh node for peer-to-peer ATAK.
- **Two Pis required?** You want two nodes to test the link, but the second can be a lighter HaLow client (Seeed XIAO MCU, Heltec dongle) rather than a full Haven.

## Change Log (highlights relevant to PMOVES mesh/Reticulum)

- **Feb 10, 2026** — Reticulum + ATAK integration scripts added: automated startup config, Reticulum interface setup, ATAK-over-Reticulum deployment. Reference implementation for sovereign encrypted routing over Wi-Fi HaLow. (GitHub repo with scripts + config examples.)
- **Mar 3, 2026** — Reticulum transport demo over two Haven nodes.
- **Mar 10, 2026** — Range test video: 3.7 miles (~6 km) coverage.
- **Jun 23, 2026** — Haven 2 build-from-scratch video (Pi 5 + MM8108).
- **Jun 24, 2026** — LuCI default IP corrected to 10.41.254.1 (legacy 10.42.0.1).

_Full change log (40+ entries) is on the live page; the above are the networking/Reticulum-relevant ones._
