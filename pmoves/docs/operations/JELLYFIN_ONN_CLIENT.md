# Jellyfin on ONN (Walmart) Devices (PMOVES Homelab)

Covers streaming the PMOVES Jellyfin host (`media.pmoves.ai`, tailnet `<jellyfin-host-tailnet-addr>`)
from Walmart ONN hardware: the ONN 4K Pro Google TV box (primary target) and ONN
Android tablets. Companion docs: FLEET_APP_HOSTING_SECURITY.md and
GLINET_EGRESS_SCENARIOS.md (fleet hosting posture + tailnet gateway context).

Fleet ground truth (verified 2026-09-16):

- `media.pmoves.ai` runs **Jellyfin Server 10.11.11** (container `bbe221863662`,
  Kestrel) with valid TLS (chain verifies clean; `/web/` returns 200).
- The hostname is **tailnet-only split DNS**: public resolvers return NXDOMAIN
  (Cloudflare DoH check); it resolves to `<jellyfin-host-tailnet-addr>` only inside the tailnet.
- Per fleet posture (FLEET_APP_HOSTING_SECURITY.md / L1-L4 model), media stays at
  **L3 (tailnet mesh)** — no public L4 ingress. Clients must reach the tailnet.

## 1. Device primer

| Device | SoC / OS | Video out | Fleet role |
|---|---|---|---|
| ONN 4K Pro Google TV box (2024, $50) | Amlogic S905X4 (4x Cortex-A55 @ 2 GHz, Mali-G31 MP2), Google TV / Android 12, 3 GB RAM [1] | 4K60, HDR10, HDR10+, Dolby Vision [1] | Primary TV client |
| ONN 4K box (2023, $20) | Amlogic S905Y4 (Cortex-A35), Android 12 [1] | 4K60, HDR10/10+ (no DV) [1] | Secondary TV client |
| ONN Android tablets (2020-2026 lineup) | Budget Unisoc/MediaTek/Snapdragon (e.g. 2026 8.1" Core: Snapdragon 685; older Pro: MT8768WA) [2][3] | 1080p-2000x1600 panels, mostly SDR/HDR10 | Casual tablet playback |

## 2. Client choice

| Client | Platforms | Install | Verdict for ONN |
|---|---|---|---|
| **Jellyfin for Android TV** (`org.jellyfin.androidtv`) | Android TV / Google TV, NVIDIA Shield, Fire TV [4] | Play Store, Amazon Appstore, F-Droid, APK archive [5]; minSdk 23 (Android 6.0+) [6] | **Recommended** for the 4K Pro / 4K box; leanback UI, remote-friendly |
| **Jellyfin for Android** (`org.jellyfin.mobile`, jellyfin-android repo) | Phones/tablets [7] | Play, F-Droid, Amazon Appstore, direct APK [7] | Use on ONN tablets (phone UI scales fine at 10-11") |
| **Finamp** (`com.unicornsonlsd.finamp`) | Android + iOS [8] | Play (redesign beta), F-Droid, GitHub APKs [8] | Music-only companion; pairs well with ATV app for audio |
| **Swiftfin** | iOS / tvOS only (VLC-based) [9] | App Store / TestFlight [9] | **N/A on ONN** — Apple platforms only; Android equivalent of its engine is Kodi |

Notes:

- The official Android TV app is genuinely first-party (jellyfin org, GPL-2.0)
  [4][5]; there is no ONN-specific fork needed — it is just another Google TV
  device with Play access.
- Finamp's redesign beta is "fully functional and should be stable" for daily
  use [8]. It talks only to Jellyfin (no streaming services) [8].
- Fallback when a stubborn file won't behave: Kodi (plays via Jellyfin plugin or
  direct UPnP) — sideload via Downloader app; ONN boxes allow unknown sources.

## 3. Codec constraints of ONN hardware

Amlogic S905X4 (ONN 4K Pro) hardware decode [10][11]:

- **AV1** up to 4K (Amlogic documents 4Kp120-class AV1 decode for S905X4 [11])
- **HEVC/H.265** incl. 10-bit, **VP9** Profile 2, **H.264/AVC** — all 4K60
- HDR: HDR10, HDR10+, **Dolby Vision** (device output; Liliputing spec table [1])
- No hardware **Dolby Vision Profile 7 dual-layer** handling in ExoPlayer-class
  clients; the Jellyfin ATV app still has open issues around DV: P7 fallback /
  TrueHD passthrough broken on some devices (#5794), DV files partially black
  (#5094), and 0.19.2 once regressed HEVC-DV to unnecessary transcode (#5093)
  [12]. Practical rule: **prefer DV Profile 8 or plain HDR10 remuxes; expect
  P7 web-DL rips to transcode.**
- Client capability reporting is imperfect: incomplete player capabilities have
  blocked direct play (#5316), and tonemapping may force transcode (#4672) [12].

ONN tablets: budget SoCs (Snapdragon 685-class, Unisoc T606-class, MediaTek)
  hardware-decode H.264/H.265 fine, but **hardware AV1 decode is generally
  absent at this tier** (UNVERIFIED per-chip — test with a sample file). Panels
  are mostly SDR/HDR10, so DV content tone-maps poorly client-side: let the
  server transcode DV/HDR to H.264/H.265 SDR for tablets.

Subtitle/audio caveats (both device classes):

- PGS/ASS subtitles frequently force burn-in transcode; use SRT where possible.
- TrueHD/Atmos passthrough is flaky on Android TV (#5794, #5414) [12]; prefer
  AC-3/E-AC-3 or FLAC cores for guaranteed direct play.

## 4. Direct play vs transcode burden on the 5090 host

Goal: **maximize direct play**; the 5090 is the safety net, not the plan.

| Content | ONN 4K Pro | ONN tablet | 5090 burden if it can't direct play |
|---|---|---|---|
| H.264 / HEVC 8/10-bit, AC3/EAC3/AAC | Direct play | Direct play (<=1080p) | none |
| AV1 (>=1080p) | Direct play (HW [11]) | Transcode to H.264 | 1 NVENC session, cheap |
| Dolby Vision P7 + TrueHD | Transcode or fail [12] | Transcode | HEVC/H.264 + audio-downmix session |
| DV P8 / HDR10+ | Usually direct play | Tone-map transcode | HDR->SDR tone-map session |
| PGS/ASS subs | Burn-in transcode | Burn-in transcode | Occasional, heavy at 4K |

Host capacity: the 5090's **9th-gen NVENC / 6th-gen NVDEC** handle AV1 and HEVC
encode plus (first on consumer GeForce) **4:2:2 decode/encode** [13], so even
broadcast-capture 4:2:2 sources can be served after remux. Consumer GeForce
NVENC session caps per Wikipedia (citing Tom's Hardware) [17]: 3 streams before
March 2023, 5 from March 2023, 8 from January 2024, and **12 from November 2025
onward — today's baseline**. One ONN stream plus a tablet stream is comfortably
inside that envelope; a fleet movie night still is not — another reason to keep
libraries in direct-play-friendly encodes (P8/HDR10, EAC3, SRT).

## 5. Tailnet access from the device

`media.pmoves.ai` is tailnet-only (public DNS NXDOMAIN — see ground truth), so
the device needs one of the two sanctioned L3 paths:

**Option A - Tailscale Android app on the device (preferred) [14]†**

- Install Tailscale from Play on the ONN box/tablet (the Play build ships the
  TV form factor; Amazon Appstore build covers Fire TV; requires Android 8+
  [14]).
- Log the device in as a tagged node (`tag:pmoves` lane), then simply open
  `https://media.pmoves.ai` in the Jellyfin apps — MagicDNS resolves it, TLS is
  already valid fleet-CA/public-chain.
- Device becomes a first-class tailnet member: full ACL lanes, per-device
  observability, works off-LAN (hotel/wifi) with no router dependency.
- † headscale caveat: PMOVES runs **headscale**, not Tailscale SaaS. The Android
  client supports pointing at a custom coordination-server URL during login
  (change/login-server override) — the official walkthrough is the headscale
  Android guide: https://headscale.net/stable/usage/connect/android/ (verified
  live 2026-09-16).

**Option B - GL.iNet router route (zero-install) [15]**

- Behind the GL.iNet (`tag:gateway`, subnet router advertising its LAN /24,
  route approved in headscale), the ONN device reaches `<jellyfin-host-tailnet-addr>` with NO
  Tailscale installed — traffic is attributed to the gateway's identity [15].
- ACL prerequisite: `tag:gateway` is granted reach to `tag:pmoves:*` [15][16],
  which covers the media host.
- DNS gotcha: devices behind the subnet router are NOT tailnet members and get
  NO MagicDNS [15] — but `media.pmoves.ai` is split-DNS anyway, so **configure
  the Jellyfin client with the raw IP `https://<jellyfin-host-tailnet-addr>`** (accept the cert
  only if it carries the IP SAN; otherwise use the hostname once the router
  pins a DNS override for `media.pmoves.ai -> <jellyfin-host-tailnet-addr>` in dnsmasq).
- If the router is also using a KVM exit node, keep its DNS upstream PUBLIC
  (private-IP resolver breaks internet during exit-node use) [15].

| | Option A (Tailscale on device) | Option B (GL.iNet route) |
|---|---|---|
| Install effort | App + headscale login | None on device |
| DNS | MagicDNS hostname | Raw 100.x IP / router override |
| Works off-LAN | Yes | No (must be on gateway LAN) |
| ACL identity | Own node identity | Attributed to `tag:gateway` [15] |
| Posture fit | Strongest (per-device) | Fine at home; matches current ACTIVE travel-router scenario [15] |

## 6. Fleet posture alignment (FLEET_APP_HOSTING_SECURITY.md)

- Media is an **L3-only service**: no Cloudflare Tunnel/Funnel route, no public
  DNS (verified NXDOMAIN). Do NOT add media to L4 without a posture change —
  public ingress is owned by kvm2 (Cloudflare primary, Funnel alternate) per
  TAILSCALE_FLEET_POSTURE.md.
- Enroll ONN devices under `tag:pmoves` (Option A) so the existing full-mesh
  ACL (`tag:pmoves -> tag:pmoves:*` [16]) applies unchanged; no new ACL rules
  required. Guests/partners deliberately have NO lane to media.
- Recovery: a factory-reset ONN box just re-enrolls (headscale pre-auth key,
  same tag); Option B needs nothing — replace the box, join gateway WiFi, point
  the app at `<jellyfin-host-tailnet-addr>`.

## 7. Deployment recipe (ONN 4K Pro)

1. Play Store (on device) -> install **Jellyfin for Android TV** [5].
2. Install **Tailscale** [14]; log in against the headscale control server with
   the device's pre-auth key (tag `tag:pmoves`); confirm `media.pmoves.ai`
   resolves (MagicDNS).
3. Jellyfin app -> Add Server -> `https://media.pmoves.ai` -> sign in.
4. Settings -> Playback: enable HW decoding; leave audio-downmix on; prefer
   direct play defaults. Test: one HEVC-HDR10 file, one DV P8 file, one AV1
   file; check the server dashboard shows "Direct playing".
5. Tablet extras: install Jellyfin for Android (or Finamp for music) and cap
   streaming bitrate/profile to avoid needless 4K transcodes to an SDR panel.

## References

- [1] Liliputing, ONN 4K Pro Google TV specs (S905X4, 3 GB, WiFi 6, DV/HDR10+):
  https://liliputing.com/walmarts-new-onn-4k-google-tv-streamer-is-a-50-box-with-an-upgraded-processor-memory-storage-and-ports/
- [2] 9to5Google, ONN Android 16 tablet lineup 2026 (Snapdragon 685 etc.):
  https://9to5google.com/2026/05/18/walmart-onn-new-android-tablets-2026/
- [3] Liliputing, ONN Pro tablets 2020 (MT8768WA):
  https://liliputing.com/walmart-expands-its-budget-android-tablet-lineup-with-onn-pro-models/
- [4] jellyfin-androidtv README (target platforms):
  https://github.com/jellyfin/jellyfin-androidtv
- [5] Jellyfin downloads/clients page (store matrix):
  https://jellyfin.org/downloads/
- [6] jellyfin-androidtv `gradle/libs.versions.toml` (minSdk 23):
  https://github.com/jellyfin/jellyfin-androidtv/blob/master/gradle/libs.versions.toml
- [7] Jellyfin for Android (official mobile client):
  https://jellyfin.org/downloads/
- [8] Finamp README (redesign beta, Android/iOS, install sources):
  https://github.com/finamp-app/finamp
- [9] Swiftfin (iOS/tvOS only): https://github.com/jellyfin/Swiftfin
- [10] Wikipedia, Amlogic SoC overview (S905X4 family):
  https://en.wikipedia.org/wiki/Amlogic
- [11] CNX-Software, Amlogic S905X4 AV1 4K decode:
  https://www.cnx-software.com/2019/10/20/amlogic-s905x4-s908x-s805x2-av1-1080p-4k-8k-media-processors/
- [12] jellyfin-androidtv DV/transcode issues: #5794, #5094, #5093, #5316,
  #4672, #5414 — https://github.com/jellyfin/jellyfin-androidtv/issues
- [13] Wikipedia, GeForce RTX 50 series (9th-gen NVENC, 6th-gen NVDEC,
  4:2:2 support): https://en.wikipedia.org/wiki/GeForce_RTX_50_series
  and https://videocardz.com/newz/nvidia-geforce-rtx-50-series-adds-support-for-422-color-format-video-decoding-and-encoding
- [14] Tailscale Android client, Google Play listing (Android 5.0+, TV
  category): https://play.google.com/store/apps/details?id=com.tailscale.ipn
- [15] PMOVES GL.iNet egress scenarios (subnet router, gateway ACL,
  MagicDNS members-only, exit-node DNS caveat):
  docs/operations/GLINET_EGRESS_SCENARIOS.md (same repo)
- [16] Fleet ACL source of truth: configs/tailscale-acl-policy.json
  (tag:gateway -> tag:pmoves:* reach, tag:pmoves full mesh)
- [17] Wikipedia, Nvidia NVENC (consumer session caps: 3 pre-2023, 5 from
  2023, 8 from Jan 2024, 12 from Nov 2025; citing Tom's Hardware):
  https://en.wikipedia.org/wiki/Nvidia_NVENC and
  https://www.tomshardware.com/news/nvidia-increases-concurrent-nvenc-sessions-on-consumer-gpus
