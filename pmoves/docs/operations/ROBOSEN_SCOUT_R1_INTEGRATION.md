# Robosen Scout K1 + Rabbit R1 Integration (PMOVES Homelab)

Covers integrating the Robosen "Scout" robot — the **Interstellar Scout K1
Series** (K1 / K1 Pro) [1] — with the **Rabbit R1** so pmoves agents running on
Jetson edge nodes can make it walk and talk. Companion docs:
GLINET_EGRESS_SCENARIOS.md (egress posture), fleet NATS conventions from
`chit/secrets_manifest_v2.yaml`.

Fleet ground truth:

- Dispatch bus is **NATS** at `nats://nats:4222` with per-worker / spark
  credentials already provisioned as docker secrets (`nats_url_worker`,
  `nats_spark_password`).
- Robot control is **local BLE only** on the Jetson node; no cloud dependency
  for motion.

## 1. Summary verdict

| Question | Answer | Basis |
|---|---|---|
| Official Robosen SDK/API? | **None public.** Control surfaces are the mobile app, onboard voice, and Robosen Hub (Studio) programming | [1][2][3] |
| Practical programmatic control | Community-reverse-engineered **BLE GATT protocol** (service `0xFFE0`, char `0xFFE1`) — proven on K1 by `robosen-js` | [10][11] |
| R1 official agent surface | **rabbit agent** (rabbithole `Settings -> Nodes`) bridging R1 voice to Claude Code / Hermes / OpenClaw sessions | [6] |
| R1 computer-control surface | **DLAM** (USB-C + Chrome screen-share, BYOK) | [7] |
| Public rabbithole REST API? | **Not published.** Journal scraping via captured access token works (unofficial) | [13][14][15] |
| Minimum demo | 1 NATS -> BLE walk command + 1 spoken line (R1 TTS reads agent reply) | §6 |

## 2. Robosen Scout (K1) programming surfaces

### 2.1 What the robot is

| Spec | Value | Source |
|---|---|---|
| Product | Interstellar Scout K1 / K1 Pro, bipedal humanoid | [1] |
| Actuators | 17 servo motors, 40 microchips, 1700+ components | [1] |
| Radio | **BLE Bluetooth 4.2** | [1] |
| Control methods | Mobile app **or** onboard voice control | [1] |
| Voice command words | K1: 41, K1 Pro: 81 (plus 6 original command words) | [1] |
| Pre-installed actions | K1: 44, K1 Pro: 75 (voice + app) | [1] |
| Battery / size | 2000 mAh, 0.94 kg, 176×99×349 mm | [1] |
| Ports | DC charging + **USB data line interface** | [1] |

Note: "Robosen Scout" in fleet vocabulary maps to the K1 series; do not confuse
with Robosen Transformers flagships, which share the app family but different
firmware [1][3].

### 2.2 Official surfaces (documented by Robosen)

1. **Mobile app** — remote control, action library, custom-action unlocks,
   programming lessons. iOS 13+/Android 8+ per the Download Center [1][3].
2. **Onboard voice** — offline wake-word command set (41/81 commands on
   K1/K1 Pro). This is a *listener*, not an injectable TTS surface: agents
   cannot push arbitrary speech through it [1].
3. **Robosen Hub / Studio** (`hub.robosen.com`) — web editor for pose/action
   programming plus community action download ("Popular Actions", per-product
   Studio + Download tabs) [2]. Actions authored here land in the app/robot
   library and can then be triggered by index over BLE [10][11].
4. **Manuals & support** — product manuals page and technical-support contact;
   the K1 manual is the authority for charging/safe-operation limits [4].

### 2.3 BLE protocol (community-reverse-engineered — primary control path)

Robosen publishes no protocol docs; the following comes from the `robosen-js`
project (K1-specific, tested) [10][11] and is consistent with independent
reverse engineering on the sibling Optimus platform [12].

GATT geometry (from the K1 command spec shipped with `robosen-js`) [11]:

| Item | Value |
|---|---|
| Manufacturer ID | `15b1` |
| Service UUID | `ffe0` (`0xFFE0`) |
| Characteristic UUID | `ffe1` (`0xFFE1`) |
| Frame header | `ffff` (`0xFFFF`) |

Verified opcode map (frame `type` byte) [11]:

| Opcode | Meaning | | Opcode | Meaning |
|---|---|---|---|---|
| `00` | instruct / handshake payload | | `0d` | volume (0–140, step 20) |
| `01–08` | move compass directions (`01`=forward/N, `08`=turn left) | | `0f` | state query |
| `0a` | transform | | `10` | user names |
| `0b` | handshake | | `11/13` | autoStand / autoOff |
| `0c` | **stop** | | `14/16` | action / folder names |
| `17` | **action trigger** | | | |

Command catalog (K1 `robot.json`): System 16, Info 11, Config 9, Sound 12,
Move 17, Joint 64, Action 16, ProAction 58 [11]. Move frames carry a duration
parameter (min 500 ms, default 2000 ms, max 10000 ms). Built-in audio IDs:
`AppSysMS` program range 101–111, joint range 201–216 [11].

Ready-made tooling: `robosen-js` (npm `robosen-js`, CLI `k1`) gives REPL,
controller, scripted sequences, optional LLM prompt/voice front-ends, and
record/playback of joint sequences [10]. Example programmatic walk [10]:

```js
import { K1 } from "robosen-js";
const k1 = new K1();
await k1.on();          // connect over BLE
await k1.volume(60);
await k1.moveForward(); // opcode 01
await k1.wait(2000);
await k1.stop();        // opcode 0c
await k1.end();
```

Caveats: unofficial, unsponsored, may break on firmware updates; single BLE
central at a time (the phone app and bridge contend) [10][12].

### 2.4 Voice command hooks — what an agent can and cannot do

- **Can:** trigger actions that include speech (K1 speaks its built-in lines
  during actions/announcements), set volume, play built-in audio IDs — all over
  BLE [11].
- **Cannot (officially):** upload arbitrary TTS audio to the robot. No public
  audio-upload API; the app/Hub custom-action flow is the only sanctioned way
  to bundle custom sounds [2][3].
- **Fleet answer for "talk":** use the R1's speaker for arbitrary agent speech
  (§4.3), and K1 built-in action/announcement audio for robot personality.

## 3. Rabbit R1 capabilities

### 3.1 Device surfaces (official)

| Surface | What it does | Agent relevance |
|---|---|---|
| PTT voice | Hold push-to-talk, speak prompt, get spoken + text answer | Natural voice in/out for agents [5] |
| rabbithole (`hole.rabbit.tech`) | Web portal: journal of conversations, notes, recordings, photos; intern tasks; settings | Persistent transcript + note triggers [5][8] |
| rabbit agent + nodes | Installable agent bridge on any computer; R1 gets swipe-to agent pages for **Claude Code CLI, Hermes Agent, OpenClaw**; hold PTT to drive the session | **The sanctioned R1 -> our stack hook** [6] |
| DLAM (`dlam.rabbit.tech`) | Plug-and-play computer agent; R1 as mic/driver over USB-C + Chromium screen share; BYOK OpenAI/Anthropic key | Alternative GUI control path [7] |
| intern | Cloud agent for reports/sites/etc. | Not robot-relevant [5] |

Historical LAM/teach-mode URLs (`rabbit.tech/teachmode`,
`rabbit.tech/lam-playground`) now serve generic r1 marketing — the LAM-branded
web-action stack is not the current integration path; third-party agents and
DLAM are [16].

### 3.2 rabbit agent mechanics (how R1 triggers our code) [6]

1. In rabbithole: `settings -> nodes -> register node`, copy the per-OS install
   command (endpoint `agent.rabbit.tech/install.sh`).
2. Run it in a terminal on the Jetson node (not inside an agent view).
3. On the R1 home screen, swipe to the agent page (Claude Code / Hermes /
   OpenClaw), `click to refresh`, then **hold PTT and speak** to start a
   session; notebook icon lists/starts sessions.
4. Uninstall: `nodes -> remove` in rabbithole, or
   `curl -fsSL https://agent.rabbit.tech/install.sh | bash -s -- --uninstall`.

This means: a CLI agent (e.g., OpenClaw) running on the Jetson with a small
"scout" tool/skill becomes **voice-triggerable from the R1**, and its textual
replies are **read aloud by the R1** natively — no extra TTS plumbing.

### 3.3 Unofficial surfaces (community, ToS/fragility risk)

| Tool | Pattern | Latency |
|---|---|---|
| `r1tool` [13] | Playwright + rabbithole access token (from `fetchUserJournal` payload); journal export as JSON, image bulk download | on-demand scrape |
| Rabbitt integrations [14] | Poll journal for "Save this as a note: ..." entries -> run local actions | ~10 s detect + ~10 s act |
| `rabbithole-api` [15] | Thin JS client for rabbithole endpoints | on-demand |

Use only as fallback triggers; prefer the official rabbit agent path.

## 4. Bridge architecture (pmoves -> Jetson -> robot + R1)

### 4.1 Component map

```
[ pmoves spark / LLM agent ]
        |  NATS publish  (nats://nats:4222, subject pmoves.robot.k1.>)
        v
[ Jetson edge node ]
  1. k1-ble-bridge   (Node + robosen-js, or Python + bleak)
     - BlueZ; connect ffe0/ffe1; single-writer mutex
     - subscribes pmoves.robot.k1.cmd, publishes pmoves.robot.k1.evt
     - watchdog: opcode 0c stop on timeout / lost link
  2. rabbit-agent + CLI agent (OpenClaw or Claude Code)
     - registered rabbithole node [6]
     - "scout" tool -> NATS publish; replies spoken by R1
  3. (optional) rabbithole journal watcher  [13][14] - note-phrase triggers
        |                         |
        v                         v
 [ Robosen K1 over BLE ]   [ Rabbit R1 voice I/O ]
```

### 4.2 Motion path (deterministic)

- Subject contract: `pmoves.robot.k1.cmd`
  `{"op":"move","dir":"forward","ms":2000}` | `{"op":"action","id":17,"name":"..."}`
  | `{"op":"stop"}` | `{"op":"volume","value":60}`.
- Bridge maps `dir` to opcode `01–08`, clamps `ms` to 500–10000, always sends
  stop (`0c`) after the move, and ACKs on `pmoves.robot.k1.evt` with battery /
state read via opcode `0f` [11].
- NATS auth reuses the existing worker/spark credentials pattern
  (`nats_url_worker`, `nats_spark_password` in `chit/secrets_manifest_v2.yaml`).

### 4.3 Voice path ("talk")

Two independent channels, pick per demo:

1. **R1 speaker (arbitrary speech, recommended):** agent reply text from the
   rabbit-agent session is spoken by the R1 itself — zero TTS infra [5][6].
2. **K1 speaker (robot personality):** BLE triggers built-in audio IDs
   (101–111) or actions with embedded lines; volume via opcode `0d` [11].
   Custom uploaded voice lines only via the official app/Hub custom-action
   flow [2].

### 4.4 Safety rules (v1)

- One BLE writer ever (app or bridge, never both); bridge holds the lock.
- Rate-limit motion: max 1 motion command per 2 s; reject `transform` and
  ProActions in v1.
- Hard stop subject `pmoves.robot.k1.stop` fans to opcode `0c` immediately;
  bridge auto-stops on NATS disconnect (watchdog).
- Robot operates on a table enclosure / clear floor; battery above 20% (state
  opcode `0f`) before walking.
- rabbit agent runs as an unprivileged user; rabbithole account is a dedicated
  fleet account; scraped tokens (if used) live in docker secrets, never in
  repo.

## 5. Jetson node prerequisites

- BlueZ + `bluetoothctl` pairing with K1 (first pair via the Robosen app to
  validate the robot, then forget it on the phone so the bridge owns the link).
- Node 18+ (`npm i -g robosen-js`) for the reference bridge, or Python 3.10+
  with `bleak` re-implementing the ffe0/ffe1 frames from `robot.json` [10][11].
- NATS client credentials (existing fleet secrets).
- For the R1 hook: rabbithole account + rabbit agent install + OpenClaw or
  Claude Code CLI [6]. DLAM optional (needs a Chromium GUI session + BYOK key,
  awkward on headless Jetson) [7].

## 6. Minimum first demo (one walk + one spoken line)

**Goal:** speak to the R1 -> Scout walks 2 s -> R1 speaks an agent line.

1. **BLE smoke test (no R1):** on Jetson, `k1` REPL -> `Volume 60`,
   `Move Forward`, wait 2 s, `Stop`. Exit criteria: robot walks and halts [10].
2. **NAT motion:** wrap step 1 as the bridge; from any node:
   `nats pub pmoves.robot.k1.cmd '{"op":"move","dir":"forward","ms":2000}'`
   -> robot walks, event ACK appears on `pmoves.robot.k1.evt`.
3. **R1 voice-in:** register rabbit agent on the Jetson (rabbithole -> nodes)
   [6]; in the CLI agent define one command, e.g. `scout_walk()` -> publishes
   the NATS subject from step 2.
4. **Demo run:** hold R1 PTT: *"Tell Scout to walk forward for two seconds."*
   -> agent calls `scout_walk()` -> K1 walks 2 s and stops -> agent replies
   *"Scout is walking forward."* -> **R1 speaks the line** (native TTS) [5][6].
5. **Robot-voice variant (optional):** same run, plus bridge sends volume 80
   and a built-in action/audio ID so the K1 itself vocalizes [11].

Success criteria: end-to-end latency PTT-release -> first step < 5 s; clean
stop every run; zero unrecoverable BLE locks across 10 consecutive demos.

## 7. Risks & unknowns

| Risk | Impact | Mitigation |
|---|---|---|
| BLE protocol unofficial; firmware update breaks it | Motion path dead | Pin robot firmware; keep `robot.json` opcode map versioned; app control as fallback [10][11][12] |
| No public rabbithole API | Journal triggers fragile | Prefer official rabbit agent; scraping only as fallback [6][13][14] |
| Single BLE central | App/bridge contention | One-writer lock; phone app only for maintenance |
| R1 depends on rabbit cloud (rabbithole auth, PTT routing) | Voice loop down | NATS CLI path still works; DLAM as alternate voice UI [7] |
| K1 falls / trips | Hardware damage | Enclosure, rate limits, v1 motions only (walk/turn/stop) |

## 8. References

Official Robosen:

- [1] Robosen — Interstellar Scout K1 Series product page (specs, BLE 4.2,
      voice/app control, USB data line): https://www.robosen.com/us/k1-pro-interstellar-scout
- [2] Robosen Hub / Studio (action editor + community downloads):
      https://hub.robosen.com/us
- [3] Robosen Download Center (iOS 13+/Android 8+ apps, K1 app):
      https://www.robosen.com/us/download-center
- [4] Robosen Manuals: https://www.robosen.com/us/manuals

Official Rabbit:

- [5] rabbit r1 user guide (PTT, rabbithole journal, DLAM, intern):
      https://rabbit.tech/r1-user-guide
- [6] rabbit support — "How to use third-party agents on rabbit r1"
      (rabbit agent install via rabbithole nodes, PTT sessions, uninstall):
      https://rabbit.tech/support/article/agents-on-rabbit-r1
- [7] rabbit — "Get started using DLAM on r1" (USB-C, Chromium, BYOK):
      https://www.rabbit.tech/blog/get-started-using-dlam-on-r1
- [8] rabbithole portal: https://hole.rabbit.tech/
- [9] rabbit support hub: https://rabbit.tech/support
- [16] Legacy LAM pages now redirect to general r1 marketing:
      https://rabbit.tech/teachmode / https://rabbit.tech/lam-playground

Community (unofficial, clearly labeled):

- [10] `oklemenz/RobosenJS` — K1 BLE control library + CLI:
      https://github.com/oklemenz/RobosenJS
- [11] RobosenJS K1 command spec (GATT UUIDs, opcode map, catalog):
      https://github.com/oklemenz/RobosenJS/blob/main/src/K1/robot.json
- [12] `Corom/Robosen-Optimus-SDK` — independent BLE RE (Optimus):
      https://github.com/Corom/Robosen-Optimus-SDK
- [13] `nesdeq/r1tool` — rabbithole journal export via Playwright + token:
      https://github.com/nesdeq/r1tool
- [14] `GikitSRC/rabbitt_integration` — R1 note-save -> local action trigger:
      https://github.com/GikitSRC/rabbitt_integration
- [15] `meowstercatel/rabbithole-api` — JS client for rabbithole:
      https://github.com/meowstercatel/rabbithole-api

Internal: `chit/secrets_manifest_v2.yaml` (NATS URLs/credentials pattern),
GLINET_EGRESS_SCENARIOS.md (fleet egress posture).
