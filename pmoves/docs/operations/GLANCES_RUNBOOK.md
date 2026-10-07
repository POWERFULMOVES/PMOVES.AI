# Glances Runbook — the sanctioned host probe on every node

**Status:** ACTIVE · **Created:** 2026-10-07 (Z890-CLAUDE, lane `feat/glances-fleet-runbook`)
**Pinned release:** Glances **4.5.7** (`glances>=4.5.7,<4.6`) · **Fork:** `POWERFULMOVES/Pmoves-Glancer` (registered in `pmoves/config/fork_registry.json`)
**Make targets:** `make -C pmoves glances-check` · `make -C pmoves glances-fetch`

---

## 1. Purpose

Glances is the **one sanctioned way to answer "how is this host doing?"** on any
PMOVES node — Windows, WSL2, Linux, Jetson. It replaces ad-hoc sweeps
(`Get-Process | sort WS`, `Get-CimInstance Win32_*`, `top`, `free -g`, `df -h`,
`docker stats`) that every agent re-invents, formats differently, and that leak
addresses into notes.

What it gives you in one call: CPU, load, memory, swap/pagefile, per-GPU memory /
utilisation / temperature, every filesystem, Docker containers (with an explicit
"unreachable" state), top processes, and Glances' own threshold alerts.

What it is **not**: a log reader, a WSL manager, or a remote-access tool. See
[§6 Blind spots](#6-blind-spots--what-glances-cannot-see).

Background: Glances was "configured and deployed nowhere"
(`pmoves/docs/handoffs/fleet-bringup-todos-2026-09-01.md:54-69`); the
config fragments that exist (`pmoves/config/profiles/hermes/glances.json`,
`pmoves/config/profiles/hermes/z890-glances.conf`) predate this runbook and are
not wired to anything.

## 2. Install (uv, pinned 4.5.x)

House rule: **uv, never pip.** The bring-up venv is `pmoves/.venv-pmoves`.

Extras that matter (upstream `pyproject` extras, verified against the 4.5.7 wheel metadata):

| extra | what it unlocks | install where |
|---|---|---|
| `containers` | Docker/Podman SDK — without it the containers plugin is silently absent | every node running Docker |
| `gpu` | `nvidia-ml-py` — without it **GPUs are invisible** | every NVIDIA node |
| `web` | FastAPI/uvicorn for `glances -w` (REST + WebUI) | only nodes that run the loopback server (§4) |

`tools/bringup/requirements.txt` currently pins bare `glances>=4.5.0,<5.0` (no
extras), so a node installed only through `venv-bringup` sees **no GPU and no
containers** — measured on z890 2026-10-07 (`gpu: []`, no docker watcher). Add the
extras explicitly:

### Windows (PowerShell or Git Bash)

```bash
cd pmoves
uv venv .venv-pmoves            # only if the venv does not exist yet
uv pip install --python .venv-pmoves/Scripts/python.exe "glances[containers,gpu]>=4.5.7,<4.6"
cd .. && make -C pmoves glances-check
```

**Git Bash uv-misdetection workaround.** `make -C pmoves venv-bringup INCLUDE_BRINGUP=1`
currently fails on Windows nodes: `pmoves/scripts/install_all_requirements.sh:32-40`
finds `uv` on PATH (under Git Bash that *is* the Windows `uv.exe`, e.g.
`~/.local/bin/uv.exe`), then treats the bare name `uv` as a Linux binary that
"cannot target Windows interpreters" and drops to pip. pip then churns ~40
requirement files into the shared venv and dies at
`services/consciousness-service/requirements.txt` (hash mode). Until that is
fixed (follow-up F1), **install the bring-up set directly with uv**:

```bash
cd pmoves
uv pip install --python .venv-pmoves/Scripts/python.exe -r tools/bringup/requirements.txt
uv pip install --python .venv-pmoves/Scripts/python.exe "glances[containers,gpu]>=4.5.7,<4.6"
```

### Linux / WSL2 distro / Jetson

```bash
cd pmoves
uv venv .venv-pmoves            # only if missing
uv pip install --python .venv-pmoves/bin/python "glances[containers,gpu]>=4.5.7,<4.6"
make -C pmoves glances-check    # from the repo root
```

Drop `gpu` on nodes without an NVIDIA driver (it is harmless but useless). For a
user-level tool outside the repo: `uv tool install "glances[containers,gpu]>=4.5.7,<4.6"`.

### Verify

```text
$ make -C pmoves glances-check
glances binary: .venv-pmoves/Scripts/glances.exe
glances version: 4.5.7 (need >= 4.4)
python API: GlancesAPI() OK, 35 plugins
docker watcher: reachable
gpu plugin: 1 GPU(s) visible
glances-check: OK
```

`glances-check` resolves `GLANCES_BIN` (explicit pin) > `pmoves/.venv-pmoves`
(Windows layout, then POSIX) > `PATH`, and exits 2 with the uv line above when
Glances is missing. Target source: `pmoves/mk/preflight.mk` (Glances block).

## 3. One-shot usage (the default — no daemon needed)

### 3.1 `make -C pmoves glances-fetch`

Runs `glances --fetch` with `PYTHONIOENCODING=utf-8` and the PMOVES template
`pmoves/config/glances/pmoves-sitrep.jinja`. Real output, z890, 2026-10-07 (disk
rows trimmed):

```text
== PMOVES sitrep :: PMOVES-Z890 :: Windows 11 SP0 64bit :: up 1:47:11 :: glances 4.5.7 ==
CPU     42.0% of 20 logical cores | load 0.00/0.00/0.00
MEM     85.1% used 26.8G / 31.5G | available 4.70G  ! WARNING
SWAP     5.8% used 3.73G / 64.0G
GPU0   NVIDIA GeForce RTX 3090 Ti | mem 7.4% | util 7% | 32C
DISK    76.7% 709G / 925G C:\
DISK    85.0% 3.09T / 3.64T D:\
DOCKER reachable: 53 containers | 0 unhealthy/restarting/exited
  mem  1.90GB pmoves-agent-zero-1
WSLVM  vmmemWSL 3.68GB (11.7% of RAM) -- the WSL2/Docker VM; .wslconfig caps it
TOP MEM (excl. processes without a cmdline, e.g. vmmemWSL)
  1. Everything.exe 1.60GB | 2.4% CPU
ALERTS 1
  WARNING MEM max 86.4 (ongoing)
== GLANCES CANNOT SEE: WSL distro state, Windows event logs, .wslconfig -- see GLANCES_RUNBOOK.md "Blind spots" ==
```

When Docker cannot be asked, the template says so instead of printing `0`:

```text
DOCKER unreachable: daemon down or socket/pipe not exposed -- container count UNKNOWN (not 0)
DOCKER not probed: glances[containers] extra (docker SDK) not installed -- this is NOT "0 containers"
```

Why a PMOVES template rather than the stock one:

- **No addresses.** The stock template prints `gl.ip['address']` in its header
  (upstream `glances/outputs/glances_stdout_fetch.py`, 4.5.7). Ours never reads
  the `ip`, `network`, `connections` or `ports` plugins, nor the container
  `ports` field — output is safe to paste into PRs and register notes.
  `GLANCES_TEMPLATE=` (empty) gets the stock template and prints a warning.
- **"Unreachable" is not "zero".** 2026-10-06 showed why: a sitrep that says
  "0 containers" while Docker Desktop is wedged reads as "stack is down by choice".
- **vmmemWSL is shown.** Upstream `GlancesAPI.top_process()` drops every process
  whose `cmdline` is empty (`glances/api.py`, 4.5.7). On Windows that includes
  `vmmemWSL` — the WSL2/Docker VM and usually the biggest memory consumer.
  The template reads it from `processlist` directly. (Upstream issue: follow-up F7.)
- **ASCII only.** Glances opens `--fetch-template` with the platform default
  encoding (cp1252 on Windows); a non-ASCII template breaks Windows nodes.
- **Windows console + emoji.** Without `PYTHONIOENCODING=utf-8`, `glances --fetch`
  with the stock (emoji) template crashes on a Windows console. The make target
  sets it; set it yourself if you call Glances directly.

Direct call (any node): `PYTHONIOENCODING=utf-8 glances --fetch --fetch-template pmoves/config/glances/pmoves-sitrep.jinja`.
Glances renders the template with Jinja2 autoescape on, so a value containing
`&` or `<` prints HTML-escaped.

### 3.2 Python API (Glances >= 4.4)

```python
from glances import api

gl = api.GlancesAPI()                       # takes ~2-5 s: primes every plugin once
gl.plugins()                                # ['alert', 'containers', 'cpu', 'fs', 'gpu', 'mem', ...]

mem = gl.mem.get_raw()                      # dict: total/used/available/percent ...
swap = gl.memswap.get_raw()
gpus = gl.gpu.get_raw()                     # [] => no driver OR nvidia-ml-py missing
fs = {m: gl.fs[m]["percent"] for m in gl.fs.keys()}

# Processes: iterate the raw list (top_process() hides cmdline-less ones, see 3.1)
procs = gl.processlist.get_raw()
vmmem = [p for p in procs if p["name"] in ("vmmemWSL", "vmmem")]
top = gl.top_process(limit=5, sorted_by="memory_percent")

# Containers: distinguish "can't ask" from "none running"
dw = gl.containers.watchers.get("docker")   # None => glances[containers] not installed
if dw is None or dw.client is None:
    containers = None                       # UNKNOWN, not zero
else:
    containers = [c for c in gl.containers.get_raw() if c["engine"] == "docker"]

print(gl.auto_unit(mem["used"]), "used of", gl.auto_unit(mem["total"]))
```

Plugins are attributes of `gl`, refreshed on access with a ~2 s cache TTL.
`gl.sensors.get_raw()` is `[]` on Windows (psutil has no sensor support there).

### 3.3 REST API (only where §4 runs a server)

`/api/4/status` (liveness), `/api/4/quicklook`, `/api/4/mem`, `/api/4/fs`,
`/api/4/gpu`, `/api/4/containers`, `/api/4/all`. With `--password` the API
requires HTTP basic auth (user `glances` unless `-u` is given).

## 4. Start-up wiring per node type

### 4.0 The security rule (non-negotiable)

`glances -w` **binds all interfaces with no authentication by default**
(`-B/--bind` defaults to the all-interfaces wildcard address; Glances `main.py` and upstream quickstart
"default binding address"). Process lists, command lines, mounts and container
names are reconnaissance gold. Therefore:

1. **Bind loopback:** `-B localhost` (verified on z890 with 4.5.7: listens on the
   IPv4 and IPv6 loopback only, nothing else).
2. **Set a password:** `--password`. Run it **once interactively** to set and save
   the hash (`<user>.pwd` under `%APPDATA%\glances` on Windows,
   `~/.config/glances` on Linux), so later unattended starts do not prompt.
   A loopback server is still reachable from any web page open in a local
   browser (DNS rebinding — the upstream quickstart has a section on it);
   the password is the defence.
3. **Tailnet, not LAN/WAN:** expose to the fleet only through Tailscale Serve
   (`tailscale serve --bg --https=<tailnet-port> http://localhost:61208`), never
   a published port, never `-B` on a LAN/tailnet interface, never public.
4. Add `--disable-plugin ip,cloud` (the `ip` plugin looks up the public address
   over the internet; `cloud` probes cloud metadata endpoints).
5. **Do not run `pmoves/scripts/claws/setup-glances.sh` as written** — it violates
   1-3 (follow-up F4).

There is deliberately **no make target that starts a server**.

### 4.1 Windows nodes (z890 and friends) — no admin needed

Per-user Startup folder launcher (no elevation; runs at the user's logon):

```powershell
# <PMOVES_ROOT> = your clone root. One-time: set the password interactively first:
#   & "<PMOVES_ROOT>\pmoves\.venv-pmoves\Scripts\glances.exe" -w -B localhost --password
$g = '<PMOVES_ROOT>\pmoves\.venv-pmoves\Scripts\glances.exe'
$cmd = "@echo off`r`nset PYTHONIOENCODING=utf-8`r`nstart `"pmoves-glances`" /min `"$g`" -w -B localhost --port 61208 --password --disable-plugin ip,cloud`r`n"
Set-Content -Encoding ascii -Path (Join-Path ([Environment]::GetFolderPath('Startup')) 'pmoves-glances.cmd') -Value $cmd
```

Remove it by deleting `pmoves-glances.cmd` from `shell:startup`. A Task Scheduler
"at logon" trigger is the alternative when the node must start Glances before
anyone logs on, but creating logon/boot-triggered tasks usually needs an
elevated prompt — use it only with the operator's explicit OK.

Do **not** run the Glances Docker image on Windows: under Docker Desktop
`--pid host` is the WSL2 VM, not Windows, so it reports the wrong machine.

### 4.2 Linux nodes — systemd user unit

`~/.config/systemd/user/pmoves-glances.service`:

```ini
[Unit]
Description=Glances (PMOVES host probe, loopback only)
After=network-online.target

[Service]
ExecStart=%h/<PMOVES_ROOT_REL>/pmoves/.venv-pmoves/bin/glances -w -B localhost --port 61208 --password --disable-plugin ip,cloud
Restart=on-failure

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload && systemctl --user enable --now pmoves-glances
loginctl enable-linger "$USER"     # start at boot without a login session (may need sudo/polkit)
```

Set the password once interactively before enabling (§4.0 rule 2). The repo's
`pmoves/scripts/claws/setup-glances.sh` is **not** the sanctioned path until
follow-up F4 lands. A compose service for Glances does not exist yet (F3).

### 4.3 Per node type

| node type | one-shot (`glances-fetch`) | loopback server at logon/boot | notes |
|---|---|---|---|
| Windows workstation / data tier (z890) | yes — before any update, restart or heavy job | Startup folder (§4.1) | Glances runs on Windows, not inside WSL; pair with §6 commands |
| WSL2 distro on a Windows host | optional | no — run it on the Windows side | inside a distro Glances sees the VM, not the host |
| Linux GPU node (5090, 4090, Spark) | yes | systemd user unit (§4.2) | `gpu` extra required |
| VPS / KVM (egress, always-on) | yes | systemd user unit, Tailscale Serve only | fills the missing hardware blocks (handoff T3) |

## 5. Showtime integration

**What "Showtime" is on main today** (`grep -ri showtime`; cross-checked with the showtime triage lane 2026-10-07):

- Make (`pmoves/mk/preflight.mk`): `flight-check`, `flight-check-retro`,
  `preflight` / `preflight-retro`, `showtime` -> `bringup-showtime` (runs
  `flight-check-retro` with `RETRO_FLAGS=--strict`), `smoke-showtime`,
  `showtime-update` (CHIT+OAuth-gated updater), `showtime-links[-open|-strict]`.
- Tools: `pmoves/tools/flight_check_retro.py` (`ENDPOINTS` :124,
  `CRITICAL_NAMES` :127), `pmoves/tools/flightcheck/retro_flightcheck.py`,
  `showtime_verify_links.py` (`main()` :277 writes
  `pmoves/docs/evidence/showtime_links.json` + `SHOWTIME_VERIFY_LINKS.{md,html}`),
  `showtime_watch.py`, `showtime_trigger_update.py`.
- Service `pmoves/services/showtime-api/` (`app.py`): `/healthz`, `/metrics`,
  `/health/all` (:241), `/updater/gate` (:253), `/sse/events`, `/agents`,
  `/notebook/feed`, `/cgp/validate`. `health_probe.py` `SERVICE_CATALOG` (:21,
  copied from `flight_check_retro.ENDPOINTS`) feeds `probe_all()` and its state
  machine `showtime | hold | preflight`; `updater.py` has `evaluate_gate()` (:150)
  and `run_update()` (:360).
- `/stage/` live flip (dl-4.2, #2100): `website/stage/*` +
  `website/persona/showtime-live.js` subscribe to showtime-api `/sse/events`, with a
  `/health/all` poll fallback. Notebook Showtime mount: dl-3.2.
- Concept doc: `pmoves/docs/ROOMS_ON_A_STAGE.md`.

**No showtime code references Glances today.** Showtime only asks "are the
**services** up?"; nothing asks "does the **host** have the headroom to bring
them up or update them?" -- the question 2026-10-06 needed answered.

**Hook points, cleanest first** (only #1 is usable now; #2-#5 are follow-up F5,
deliberately not done in this lane -- no showtime code is edited here):

1. **Operator road, today (no code):** run `make -C pmoves glances-fetch` before
   `bringup-showtime`, `smoke-showtime` or `showtime-update`. Hold if `MEM` shows
   `!! CRITICAL` (>= 90 %), any `DISK` shows `!! >=90%`, or `DOCKER` is not
   `reachable`.
2. **Recommended runtime hook -- a NON-CRITICAL "Host" tier entry** in
   `health_probe.SERVICE_CATALOG` **and** `flight_check_retro.ENDPOINTS`, pointing
   at the node's loopback Glances REST API (`/api/4/status`; §4 server, basic
   auth), and kept **out of `CRITICAL_NAMES`** so a node without Glances can never
   fail `bringup-showtime` (`--strict`). It then surfaces for free in
   `/health/all`, the `/stage/` live flip and `showtime-links`.
3. **`showtime-sitrep` make target** next to `showtime-links`, running
   `glances-fetch`; optionally a non-fatal `$(MAKE) --no-print-directory
   glances-fetch || true` first step in `bringup-showtime` / `smoke-showtime`
   (same pattern as the existing `showtime-links || true`).
4. **`updater.run_update()` headroom gate:** the updater pulls images and
   restarts services; a pre-pull check via `glances.api` (mem/disk thresholds,
   vmmemWSL size) that refuses to proceed is the direct antidote to the
   2026-10-06 failure class.
5. **Docs:** link this runbook from `pmoves/docs/ROOMS_ON_A_STAGE.md` / the
   preflight docs when #2 lands.

Known, separate bug (another lane owns it): showtime's retro probes still hit
Archon `:8091/healthz`, `/mcp/describe` and `:3737`, which Archon 0.6.0 no longer
serves (#2943), so strict showtime likely fails on Archon regardless of Glances.
Do not read that failure as a host problem.

Orphaned showtime commits exist on `origin/fix/consolidate-archon` and the local
branch `feat/showtime-updater`; another agent is triaging them. Do not build on
or salvage them from this runbook's lane.

## 6. Blind spots — what Glances cannot see

| blind spot | why | narrow read-only command |
|---|---|---|
| WSL distro state (Running/Stopped, version) | not a process/plugin concept | `wsl -l -v` · `wsl --status` |
| Windows event logs (Docker Desktop / WSL service errors, updates) | Glances reads no logs | `Get-WinEvent -LogName Application -MaxEvents 50 \| ? ProviderName -match 'Docker\|Wsl'` · `Get-WinEvent -LogName System -MaxEvents 50 \| ? ProviderName -match 'Hyper-V\|vmcompute\|Wsl'` |
| `.wslconfig` (the cap on the WSL2/Docker VM's memory/swap) | a file, not a metric | `Get-Content $env:USERPROFILE\.wslconfig` |
| Docker Desktop version / pending auto-update | not exposed | `docker version --format '{{.Client.Version}} / {{.Server.Version}}'` |
| Which processes run *inside* the WSL VM | Windows-side Glances sees only `vmmemWSL` | `docker stats --no-stream` (if Docker is reachable) |
| vmmemWSL in `top_process()` | upstream drops cmdline-less processes | the PMOVES template's `WSLVM` line |
| Sensors on Windows | psutil limitation | GPU temp still comes from the `gpu` plugin |

All of these are **read-only**. None of them starts, stops or reconfigures WSL
or Docker.

## 7. Incident: 2026-10-06, z890 — Docker Desktop auto-update under a live stack

**What happened**

1. Docker Desktop **auto-updated 4.93 → 4.94 while the PMOVES stack was running**
   on z890 (a data-tier node).
2. The update's restart found the WSL **VHD already attached** and Docker Desktop
   failed with **`Wsl/Service/E_UNEXPECTED`**.
3. Host **memory was near exhaustion** at the time, which made every recovery step
   slower and riskier.

**How Glances fits**

- *Before:* `glances-fetch` would have shown `MEM ... !! CRITICAL` and the
  `WSLVM` size — the "do not update/restart now" signal.
- *During:* `glances-fetch` keeps working when Docker is down and says
  `DOCKER unreachable` instead of "0 containers"; pair it with the §6 commands
  (`wsl -l -v`, `Get-WinEvent`) — Glances alone cannot see the WSL/VHD state.

**Prevention**

- On data-tier nodes, turn off Docker Desktop's automatic update download/apply
  (Settings → Software updates; docs below). Update in a planned window: stop the
  stack with `make -C pmoves down-all` (graceful reverse order), then update.
- Never restart Docker Desktop or WSL while `MEM` is critical; free memory first.

**Recovery ladder (least destructive first; stop at the first rung that works)**

1. Diagnose read-only: `glances-fetch`, `wsl -l -v`, `wsl --status`, `Get-WinEvent` (§6).
2. Quit Docker Desktop from the tray, wait for `vmmemWSL` to fall, start it again.
3. Terminate only the Docker VM distro: `wsl --terminate docker-desktop`
   (other distros keep running).
4. **`wsl --shutdown` — last resort on a data-tier node.** It kills **every**
   distro and every container at once, including databases mid-write. Use it only
   after the data-tier containers are confirmed stopped or already dead, record
   the decision in the register, and run the data-tier health checks
   (e.g. `SUPABASE_SAFE_RESTART_RUNBOOK.md`) after bring-up.

Note: `BRING_UP_WSL2.md:179-185` currently recommends `wsl --shutdown` as the
*first* troubleshooting step for "Docker daemon not responding" — that contradicts
this ladder (follow-up F6).

## 8. Follow-ups (recorded, not fixed in this lane)

| id | item | where |
|---|---|---|
| F1 | uv misdetection under Git Bash: `uv` resolves to Windows `uv.exe` but is treated as a Linux binary and discarded → pip fallback → hash-mode failure | `pmoves/scripts/install_all_requirements.sh:32-40` |
| F2 | `glances-autodetect.ps1` does not use Glances at all; VRAM falls back to WMI `AdapterRAM` (4 GB cap) so the RTX 3090 Ti reports 4 GB, and no profile matches → node type `unknown` | `deploy/provision/glances-autodetect.ps1:164-170, :379` |
| F3 | No compose/service wiring for Glances (per-node, loopback, Tailscale Serve); compose files are protected — needs its own lane | handoff `fleet-bringup-todos-2026-09-01.md:54-69` |
| F4 | `claws/setup-glances.sh` binds all interfaces with no password (Docker `-p PORT:61208`, native `glances -w`), uses unpinned `latest-full`, pip fallback, deprecated `py3nvml`, `/api/3` paths | `pmoves/scripts/claws/setup-glances.sh:25-30,40-47,57,65` |
| F5 | Showtime hooks 2-5 in §5 (non-critical Host tier entry kept out of `CRITICAL_NAMES`; `showtime-sitrep` target; updater headroom gate; ROOMS_ON_A_STAGE link) | `services/showtime-api/health_probe.py`, `tools/flight_check_retro.py`, `pmoves/mk/preflight.mk`, `services/showtime-api/updater.py` |
| F6 | `BRING_UP_WSL2.md` recommends `wsl --shutdown` first | `pmoves/docs/operations/BRING_UP_WSL2.md:179-185` |
| F7 | Upstream: `GlancesAPI.top_process()` hides cmdline-less processes (vmmemWSL) — file upstream / patch in Pmoves-Glancer | `glances/api.py` (4.5.7) |
| F8 | `tools/bringup/requirements.txt` installs bare `glances` (no `containers`/`gpu` extras) with a loose `<5.0` ceiling | `pmoves/tools/bringup/requirements.txt` |
| F9 | `z890-glances.conf` describes old hardware (GTX 1650 / 32 GB / Windows 10) and another user's export paths | `pmoves/config/profiles/hermes/z890-glances.conf:1-53` |

## 9. Sources

Upstream (Glances 4.5.7):

- Python API: https://glances.readthedocs.io/en/latest/api/python.html
- Command reference (`--fetch`, `--fetch-template`, `-B`, `--password`, `--disable-plugin`): https://glances.readthedocs.io/en/latest/cmds.html
- Quickstart (web server mode, default bind address, password, DNS rebinding): https://glances.readthedocs.io/en/latest/quickstart.html
- REST API v4: https://glances.readthedocs.io/en/latest/api/restful.html
- Install / extras: https://glances.readthedocs.io/en/latest/install.html
- Release: https://github.com/nicolargo/glances/releases/tag/v4.5.7
- Installed source read for this runbook: `glances/api.py` (`GlancesAPI`, `top_process`), `glances/outputs/glances_stdout_fetch.py` (stock template, template loading), `glances/main.py` (`-B` default, `--password`), `glances/plugins/containers/engines/docker.py` (watcher `client is None` on connect failure)

Platform:

- Tailscale Serve: https://tailscale.com/kb/1242/tailscale-serve
- WSL commands (`wsl -l -v`, `--terminate`, `--shutdown`): https://learn.microsoft.com/en-us/windows/wsl/basic-commands
- `.wslconfig`: https://learn.microsoft.com/en-us/windows/wsl/wsl-config
- Docker Desktop settings (software updates): https://docs.docker.com/desktop/settings-and-maintenance/settings/

Repo:

- `pmoves/configs/cli_tools.yaml` (glances entry), `pmoves/tools/bringup/requirements.txt`
- `pmoves/mk/preflight.mk` (Glances block; showtime targets)
- `pmoves/config/glances/pmoves-sitrep.jinja`
- `pmoves/config/fork_registry.json` (`Pmoves-Glancer`)
- `pmoves/docs/handoffs/fleet-bringup-todos-2026-09-01.md:54-105`
