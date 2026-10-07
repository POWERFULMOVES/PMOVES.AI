# Glances Runbook — the sanctioned host probe on every node

**Status:** ACTIVE · **Created:** 2026-10-07 (Z890-CLAUDE, lane `feat/glances-fleet-runbook`)
**Pinned release:** Glances **4.5.7** (`glances[containers,gpu,web]>=4.5.7,<4.6`, `pmoves/tools/bringup/requirements.txt`) · **Fork:** `POWERFULMOVES/Pmoves-Glancer` (`pmoves/config/fork_registry.json`)
**Make targets:** `make -C pmoves glances-check` · `make -C pmoves glances-fetch`
**PMOVES config:** `pmoves/config/glances/pmoves-glances.conf` · **template:** `pmoves/config/glances/pmoves-sitrep.jinja`

Upstream docs are cited inline as `[gd:<page>]` = `https://glances.readthedocs.io/en/develop/<page>.html`
(develop docs, read 2026-10-07; every flag below was also checked against the
installed 4.5.7 source).

---

## 1. Purpose

Glances is the **one sanctioned way to answer "how is this host doing?"** on any
PMOVES node — Windows, WSL2, Linux, Jetson. It replaces ad-hoc sweeps
(`Get-Process | sort WS`, `Get-CimInstance Win32_*`, `top`, `free -g`, `df -h`,
`docker stats`) that every agent re-invents, formats differently, and that leak
addresses into notes.

One call gives CPU, load, memory, swap/pagefile, per-GPU memory/utilisation/
temperature, every filesystem, Docker containers (with explicit "unreachable" and
"not running" states), the WSL2 VM, top processes and Glances' threshold alerts.
It is **not** a log reader, a WSL manager or a remote-access tool (§6).

Background: Glances was "configured and deployed nowhere"
(`pmoves/docs/handoffs/fleet-bringup-todos-2026-09-01.md:54-69`). The older
fragments `pmoves/config/profiles/hermes/glances.json` and `z890-glances.conf`
are not wired to anything and do not re-enable the `ip` plugin (checked).

## 2. Install (uv, pinned 4.5.x)

House rule: **uv, never pip.** The bring-up venv is `pmoves/.venv-pmoves`, and
`pmoves/tools/bringup/requirements.txt` pins `glances[containers,gpu,web]>=4.5.7,<4.6`.
The extras (verified in the v4.5.7 `pyproject.toml`) matter:

| extra | unlocks | without it |
|---|---|---|
| `containers` | docker/podman/lxd SDKs `[gd:aoa/containers]` | containers plugin silently absent |
| `gpu` | `nvidia-ml-py` for NVIDIA incl. Jetson/Tegra (AMD/Intel/ARM GPUs on Linux need no extra) `[gd:aoa/gpu]` | GPUs invisible (measured on z890: `gpu: []`) |
| `web` | FastAPI/uvicorn/python-jose for `glances -w`, REST + JWT `[gd:api/restful]` | no server (§4) |

```bash
cd pmoves
uv venv .venv-pmoves                                    # only if missing
uv pip install --python .venv-pmoves/Scripts/python.exe -r tools/bringup/requirements.txt   # Windows
uv pip install --python .venv-pmoves/bin/python         -r tools/bringup/requirements.txt   # Linux/WSL/Jetson
cd .. && make -C pmoves glances-check
```

`make -C pmoves venv-bringup INCLUDE_BRINGUP=1` on Windows: this PR fixes the
Git Bash uv misdetection (`pmoves/scripts/install_all_requirements.sh:36-39` — under
Git Bash the bare `uv` *is* `uv.exe`; the script used to discard it and fall back
to pip; it now uses `uv.exe`). The target **still fails later on Windows** at
`services/consciousness-service/requirements.txt` -> `requirements.lock`, which
pins Linux-only wheels (e.g. `nvidia-cufile`) — follow-up F1. Until then use the
direct `uv pip install -r tools/bringup/requirements.txt` above.

```text
$ make -C pmoves glances-check
glances binary: .venv-pmoves/Scripts/glances.exe
glances version: 4.5.7 (need >= 4.4)
python API: GlancesAPI() OK, 35 plugins
docker watcher: reachable
gpu plugin: 1 GPU(s) visible
glances-check: OK
```

`glances-check` resolves `GLANCES_BIN` (pin) > `pmoves/.venv-pmoves` > `PATH`;
missing Glances, a non-importable install or a version below
`GLANCES_MIN_VERSION` (4.4, the Python API floor `[gd:api/python]`) each exit
with a one-line remedy (versions compare at full arity, so `GLANCES_MIN_VERSION=4.5.7`
passes on 4.5.7). A PATH-only install with no interpreter beside it (e.g. `uv tool
install`) gets a binary + version check and a WARNING that the Python API was not
verified. Source: `pmoves/mk/preflight.mk` (Glances block).

## 3. One-shot usage (the default — no daemon)

### 3.1 `make -C pmoves glances-fetch`

Runs `glances -C pmoves-glances.conf --fetch --fetch-template pmoves-sitrep.jinja`
with `PYTHONIOENCODING=utf-8` `[gd:fetch]`. There is no "stock template" mode.

> **The upstream stock fetch template prints the host address** in its header
> (`gl.ip['address']`, `[gd:fetch]`; `glances/outputs/glances_stdout_fetch.py`
> in 4.5.7). Never paste bare `glances --fetch` output into tickets, commits,
> register notes or chat. Use `make -C pmoves glances-fetch`, or pass both
> `-C pmoves/config/glances/pmoves-glances.conf` and
> `--fetch-template pmoves/config/glances/pmoves-sitrep.jinja`.

`pmoves-glances.conf` sets `disable=True` for `[ip]` (local + public address
lookup), `[cloud]` (cloud metadata probes) and `[connections]`, and
`check_update=false` (no PyPI version check — the release is pinned). Glances
honours `disable=True` in any plugin section `[gd:config]`. The template never
reads `ip`, `network`, `connections`, `ports` or container `ports` either, so
output is address-free twice over.

Real output, z890, 2026-10-07 (disk rows trimmed):

```text
== PMOVES sitrep :: PMOVES-Z890 :: Windows 11 SP0 64bit :: up 2:08:31 :: glances 4.5.7 ==
CPU     36.0% of 20 logical cores | load 0.00/0.00/0.00
MEM     77.4% used 24.4G / 31.5G | available 7.10G
SWAP     7.8% used 4.99G / 64.0G
GPU0   NVIDIA GeForce RTX 3090 Ti | mem 7.5% | util 19% | 32C
DISK    85.0% 3.09T / 3.64T D:\
DOCKER reachable: 53 containers | 0 not running/healthy
  mem  1.80GB pmoves-agent-zero-1
WSLVM  vmmemWSL 4.72GB (15.0% of RAM) -- the WSL2/Docker VM; .wslconfig caps it
TOP MEM (excl. processes without a cmdline, e.g. vmmemWSL)
  1. Everything.exe 1.59GB | 0.4% CPU
ALERTS 1
  WARNING MEM max 81.7 (ongoing)
== GLANCES CANNOT SEE: WSL distro state, Windows event logs, .wslconfig -- see GLANCES_RUNBOOK.md "Blind spots" ==
```

What the template guarantees (render-tested in
`pmoves/tests/config/test_glances_sitrep_template.py`):

- **"Can't ask" is never "0".** `DOCKER unreachable ... UNKNOWN (not 0)`,
  `DOCKER not probed: glances[containers] extra ... not installed`, and
  `... (containers plugin disabled)` are distinct lines. Disabled `gpu` /
  `processlist` plugins print "not probed" instead of crashing.
- **Sick containers are listed, not fatal.** Upstream only fills `memory_usage`
  for active containers (`running|healthy|paused`; health status such as
  `unhealthy`/`starting` replaces the state). Every other container is listed as
  `!  name [status]`; memory ranking skips containers without a value.
- **vmmemWSL is shown** (`WSLVM` line) — upstream `top_process()` hides it (F7).
- **ASCII only**: Glances opens `--fetch-template` with the platform default
  encoding (cp1252 on Windows). Jinja autoescape is on, so `&`/`<` in names print
  HTML-escaped.
- On a Windows console, Glances output with the stock (emoji) template crashes
  unless `PYTHONIOENCODING=utf-8`; the make target sets it.

### 3.2 Python API (Glances >= 4.4) `[gd:api/python]`

```python
from glances import api

gl = api.GlancesAPI()                       # ~2-5 s: primes every plugin once
pl = gl.plugins()                           # ACTIVE plugins only; a disabled one is not an attribute
mem, swap = gl.mem.get_raw(), gl.memswap.get_raw()
gpus = gl.gpu.get_raw() if "gpu" in pl else None          # [] => no driver or no gpu extra
fs = {m: gl.fs[m]["percent"] for m in gl.fs.keys()}
procs = gl.processlist.get_raw()            # iterate raw: top_process() hides cmdline-less procs
vmmem = [p for p in procs if p["name"] in ("vmmemWSL", "vmmem")]

dw = gl.containers.watchers.get("docker") if "containers" in pl else None
if dw is None or dw.client is None:
    containers = None                       # UNKNOWN, not zero
else:
    containers = [c for c in gl.containers.get_raw() if c["engine"] == "docker"]
    sick = [c for c in containers if c["status"] not in ("running", "healthy", "paused")]
    by_mem = sorted((c for c in containers if c.get("memory_usage")), key=lambda c: c["memory_usage"], reverse=True)
```

Plugin attributes refresh on access with a ~2 s cache. `gl.sensors.get_raw()` is
`[]` on Windows (psutil limitation).

## 4. Start-up wiring per node type

### 4.0 Security rule (non-negotiable)

`glances -w` binds **all interfaces** by default (`-B` default is the wildcard
address, `[gd:quickstart]`; `main.py` in 4.5.7) and the REST API, WebUI and MCP
endpoint are **open unless `--password` is set** (`[gd:api/restful]`,
`[gd:api/mcp]`). Process command lines, mounts and container names are
reconnaissance gold. Upstream's own Docker example publishes 61208-61209 on all
interfaces without a password `[gd:docker]` — **do not copy it**.

1. **Bind loopback:** `-B localhost` (verified on z890 with 4.5.7: listens on the
   IPv4 + IPv6 loopback only).
2. **Password, saved once, interactively:**
   `glances -C <conf> -w -B localhost --password`. Enter + confirm the password,
   then **answer `Yes`** to `Do you want to save the password in <file>? [Yes/No]`
   (`glances/password.py:84-104`, prompt at :102, 4.5.7). The hash lands in `<user>.pwd` under
   `%APPDATA%\glances` (Windows) or `~/.config/glances` (Linux). If you do not
   save it, every later start **blocks on an invisible password prompt** — a
   minimised Startup launcher just hangs (fails closed, silently). Default user is
   `glances`; create/reuse a named pair with `glances -w --username` / `-u <user>`
   `[gd:api/restful]`. Clients use HTTP Basic or a JWT from `/api/4/token`.
3. **Tailnet, never LAN/WAN:** expose only via Tailscale Serve
   (`tailscale serve --bg --https=<tailnet-port> http://localhost:61208`), never a
   published port, never public.
4. **Always pass `-C pmoves/config/glances/pmoves-glances.conf`** (ip/cloud off,
   no update check).
5. **MCP** (`--enable-mcp`, needs `glances[mcp]`, SSE at `/mcp/sse`) inherits the
   web server's auth and is **open without `--password`** `[gd:api/mcp]`. Not
   enabled in PMOVES today; if enabled, rules 1-4 apply unchanged.
6. `pmoves/scripts/claws/setup-glances.sh` violates 1-3 — do not run it (F4).

There is deliberately **no make target that starts a server**.

### 4.1 Windows — per-user Startup folder (no admin)

```powershell
# <PMOVES_ROOT> = clone root. First complete 4.0 rule 2 interactively.
$p = '<PMOVES_ROOT>\pmoves'
$cmd = "@echo off`r`nset PYTHONIOENCODING=utf-8`r`nstart `"pmoves-glances`" /min `"$p\.venv-pmoves\Scripts\glances.exe`" -C `"$p\config\glances\pmoves-glances.conf`" -w -B localhost --port 61208 --password`r`n"
Set-Content -Encoding ascii -Path (Join-Path ([Environment]::GetFolderPath('Startup')) 'pmoves-glances.cmd') -Value $cmd
```

Remove: delete `pmoves-glances.cmd` from `shell:startup`. A Task Scheduler
logon/boot trigger usually needs elevation — only with the operator's OK. Do not
run the Glances container on Windows: under Docker Desktop `--pid host` is the
WSL2 VM, not Windows.

### 4.2 Linux — systemd user unit

`~/.config/systemd/user/pmoves-glances.service`:

```ini
[Unit]
Description=Glances (PMOVES host probe, loopback only)
After=network-online.target

[Service]
ExecStart=%h/<PMOVES_ROOT_REL>/pmoves/.venv-pmoves/bin/glances -C %h/<PMOVES_ROOT_REL>/pmoves/config/glances/pmoves-glances.conf -w -B localhost --port 61208 --password
Restart=on-failure

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload && systemctl --user enable --now pmoves-glances
loginctl enable-linger "$USER"     # run without a login session (may need sudo/polkit)
```

### 4.3 Per node type

| node type | `glances-fetch` | loopback server | notes |
|---|---|---|---|
| Windows workstation / data tier (z890) | before any update, restart, heavy job | Startup folder (4.1) | run on Windows, not in WSL; pair with §6 |
| WSL2 distro on a Windows host | optional | no | inside a distro Glances sees the VM, not the host |
| Linux GPU node (5090, 4090, Spark) | yes | systemd user unit (4.2) | `gpu` extra |
| VPS / KVM (egress, always-on) | yes | systemd user unit, Tailscale Serve only | fills the missing hardware blocks (handoff T3) |

### 4.4 Exports worth using later (not wired — F12)

Glances 4.5.7 ships exporters `[gd:gw/index]`; two fit PMOVES:

- **Prometheus** `[gd:gw/prometheus]`: `--export prometheus` with
  `[prometheus] host=localhost port=9091 prefix=glances` serves an exporter for
  the existing monitoring stack, whose host `node` job is disabled
  (`pmoves/monitoring/prometheus/prometheus.yml:14-17`). Upstream says use the
  wildcard bind inside containers — PMOVES keeps loopback/tailnet (4.0).
- **NATS** `[gd:gw/nats]`: `--export nats` with `[nats] host=... prefix=glances`
  publishes JSON per plugin to `<prefix>.<plugin>` — the PMOVES bus.

Both need the `export` extra (heavy: pulls every exporter client) or just the
single client (`prometheus_client`, `nats-py`).

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

| blind spot | narrow read-only command |
|---|---|
| WSL distro state / WSL version | `wsl -l -v` · `wsl --status` · `wsl --version` |
| Windows event logs (Docker Desktop, WSL, Hyper-V) | `Get-WinEvent -LogName Application -MaxEvents 50 \| ? ProviderName -match 'Docker\|Wsl'` · same with `-LogName System` and `'Hyper-V\|vmcompute\|Wsl'` |
| `.wslconfig` (caps the WSL2/Docker VM) | `Get-Content $env:USERPROFILE\.wslconfig` |
| Docker Desktop version / pending update | `docker version --format '{{.Client.Version}} / {{.Server.Version}}'` · `docker desktop update --check-only` (checks, never applies) |
| processes *inside* the WSL VM | `docker stats --no-stream` (if Docker is reachable) |
| sensors on Windows | none (psutil); GPU temperature still comes from the `gpu` plugin |

All read-only; none starts, stops or reconfigures WSL or Docker.

### 6.1 `.wslconfig` facts (Microsoft docs, read 2026-10-07)

Source: https://learn.microsoft.com/en-us/windows/wsl/wsl-config

- `[wsl2] memory=` (default **50 % of Windows RAM**) and `[wsl2] swap=` (default
  25 % of RAM, rounded up to whole GB) cap the single VM that every distro and
  Docker Desktop share.
- `autoMemoryReclaim` (`disabled | gradual | dropCache`; **unknown values are
  treated as `dropCache`**) and `sparseVhd` are **still under `[experimental]`**
  in the current docs — not promoted to `[wsl2]`.
- Changes apply only after the VM fully stops ("the 8 second rule"); `wsl
  --shutdown` is the fast path and stops **every** distro — on a data-tier node
  that is a full container outage.
- Docker Desktop's Resource Saver on WSL only pauses the engine and **does not
  reduce Docker's memory**; Docker recommends WSL's `autoMemoryReclaim` instead,
  and with WSL integration enabled Resource Saver never engages
  (https://docs.docker.com/desktop/use-desktop/resource-saver/).

**z890 as of 2026-10-07** (WSL 2.7.14):

```ini
[wsl2]
memory=12GB      ; added 2026-10-07, NOT yet applied - needs wsl --shutdown in a planned window
swap=8GB
[experimental]
autoMemoryReclaim=Gradual
sparseVhd=true
```

Backup: `%USERPROFILE%\.wslconfig.bak-20261007`. Basis: 53 containers measured
at 9.6 GiB total; the VM peaked at 15.8 GiB (the 50 % default ceiling of 31.5 GiB)
on 2026-10-06. If Postgres/ClickHouse/Neo4j OOM inside the VM after applying,
raise `memory`. Microsoft documents the value as lowercase `gradual`; whether the
capitalised `Gradual` is matched or falls through to `dropCache` is unverified
(F14). After applying, `glances-fetch`'s `WSLVM` line should stay under ~12 GB.

## 7. Incident: 2026-10-06, z890 — Docker Desktop updated under a live stack

**What happened**

1. Docker Desktop updated **4.93 -> 4.94 in place while the PMOVES stack was
   running** on z890 (a data-tier node).
2. The restart found the WSL **VHD already attached**; Docker Desktop failed with
   **`Wsl/Service/E_UNEXPECTED`**.
3. Host **memory was near exhaustion** (WSL VM at its default ~15.8 GB ceiling
   plus desktop apps), which made every recovery step slower and riskier.

**How Glances fits.** Before: `glances-fetch` shows `MEM ... !! CRITICAL` and
the `WSLVM` size — the "do not update/restart now" signal. During: it keeps
working with Docker down and says `DOCKER unreachable`, not "0 containers"; pair
it with §6 (`wsl -l -v`, `Get-WinEvent`) — Glances cannot see WSL/VHD state.

**Prevention** (Docker Desktop -> Settings -> **Software updates**,
https://docs.docker.com/desktop/settings-and-maintenance/settings/):

- **Always download updates** — *off* by default; keep it **off** on data-tier
  nodes so nothing is staged in the background.
- **Automatically check for updates** — on by default; it only *notifies*. Do
  not act on the notification ("update and restart") while the stack is up.
- **Automatically update components** — applies to Docker Desktop **4.92 and
  earlier** only.
- CLI: `docker desktop update --check-only` checks without applying; never run
  `docker desktop update --quiet` ("quietly check and apply") on a live data-tier
  node (https://docs.docker.com/reference/cli/docker/desktop/update/).
- Update only in a planned window: `make -C pmoves down-all` (graceful reverse
  order) -> update -> bring-up -> data-tier checks. Apply `.wslconfig` changes in
  the same window (§6.1).
- Never restart Docker Desktop or WSL while `MEM` is critical; free memory first.

**Recovery ladder** (least destructive first; stop at the first rung that works):

1. Read-only diagnosis: `glances-fetch`, `wsl -l -v`, `wsl --status`, `Get-WinEvent` (§6).
2. Quit Docker Desktop from the tray, wait for `WSLVM` to drop, start it again.
3. Terminate only the Docker distro: `wsl --terminate docker-desktop`.
4. **`wsl --shutdown` — last resort on a data-tier node**: kills every distro and
   container at once, databases mid-write included
   (https://learn.microsoft.com/en-us/windows/wsl/basic-commands). Only after the
   data-tier containers are confirmed stopped or already dead; record it in the
   register; run the data-tier checks (`SUPABASE_SAFE_RESTART_RUNBOOK.md`) after.

## 8. Follow-ups (recorded, not fixed here unless marked)

| id | item | where |
|---|---|---|
| F1 | **Partly fixed in this PR** (uv.exe detection). `venv-bringup` still fails on Windows: `consciousness-service/requirements.lock` pins Linux-only wheels (`nvidia-cufile`) | `pmoves/services/consciousness-service/requirements.txt` -> `requirements.lock` |
| F2 | `glances-autodetect.ps1` does not use Glances; VRAM falls back to WMI `AdapterRAM` (4 GB cap) so a 3090 Ti reports 4 GB; no profile matches -> node type `unknown` | `deploy/provision/glances-autodetect.ps1:164-170, :379` |
| F3 | No compose/service wiring for Glances (per node, loopback, Tailscale Serve); compose files are protected — own lane | `fleet-bringup-todos-2026-09-01.md:54-69` |
| F4 | `claws/setup-glances.sh`: all-interface binds without password (mirrors upstream's Docker example `[gd:docker]`), unpinned `latest-full`, pip fallback, `py3nvml`, `/api/3` | `pmoves/scripts/claws/setup-glances.sh:25-30,40-47,57,65` |
| F5 | Showtime hooks 2-5 (§5) | `services/showtime-api/health_probe.py`, `tools/flight_check_retro.py`, `pmoves/mk/preflight.mk`, `services/showtime-api/updater.py` |
| F6 | Recommends `wsl --shutdown` as the *first* fix for "Docker daemon not responding"; MS docs: it stops all distros, "use wisely" | `pmoves/docs/operations/BRING_UP_WSL2.md:179-185` |
| F7 | Upstream issue (draft below) — **operator files it**, not agents | nicolargo/glances |
| F8 | **Fixed in this PR**: bring-up requirements now `glances[containers,gpu,web]>=4.5.7,<4.6` | `pmoves/tools/bringup/requirements.txt` |
| F9 | `z890-glances.conf` describes old hardware (GTX 1650, 32 GB, Windows 10) and another user's export paths | `pmoves/config/profiles/hermes/z890-glances.conf:1-53` |
| F10 | Skill tells agents `pip install glances[web]` then `glances -w` (pip; all interfaces; no password) | `.claude/skills/node-4090-probe/SKILL.md:97` |
| F11 | `glances-autodetect.sh` installs via apt/pip fallbacks, not uv | `deploy/provision/glances-autodetect.sh:115-150` |
| F12 | Wire Prometheus and/or NATS export (§4.4), loopback/tailnet only | `pmoves/monitoring/prometheus/prometheus.yml:14-17` |
| F13 | `.wslconfig` example omits `[experimental] autoMemoryReclaim` (Docker's recommended memory lever on WSL) and that changes need a full VM stop | `pmoves/docs/operations/BRING_UP_GUIDE.md:106-112` |
| F14 | Verify how WSL parses `autoMemoryReclaim=Gradual` (docs list lowercase; unknown -> `dropCache`) | z890 `%USERPROFILE%\.wslconfig` |

### F7 — upstream issue draft (ready to file; operator's call)

**Title:** `GlancesAPI.top_process()` silently drops processes with an empty cmdline (hides `vmmemWSL` on Windows)

**Body:**

> **Version:** Glances 4.5.7 (also present on develop as of 2026-10-07), Windows 11, Python 3.12.
>
> `glances/api.py` `top_process()` filters the process list with
> `if p['cmdline'] and 'glances' not in (p['cmdline'] or ())`. The intent is to
> exclude Glances itself, but the `p['cmdline']` truthiness test also drops every
> process whose cmdline is empty or inaccessible. On Windows that includes
> `vmmemWSL` — the WSL2 VM, typically the largest memory consumer on a Docker
> Desktop host — so `--fetch` "TOP PROCESS by MEM" never shows it.
>
> **Repro:**
> ```python
> from glances import api
> gl = api.GlancesAPI()
> raw = [p['name'] for p in gl.processlist.get_raw() if p['name'] == 'vmmemWSL']
> top = [p['name'] for p in gl.top_process(limit=50, sorted_by='memory_percent')]
> print(raw, 'vmmemWSL' in top)   # ['vmmemWSL'] False   (vmmemWSL ~3.8 GB, 11 % of RAM)
> ```
>
> **Suggested fix:** exclude only Glances' own PID (or match on `name`), and keep
> cmdline-less processes:
> ```python
> me = os.getpid()
> all_but_glances = [p for p in self._stats.get_plugin('processlist').get_raw()
>                    if p.get('pid') != me and 'glances' not in (p.get('cmdline') or ())]
> ```

## 9. Sources

Glances (develop docs, read 2026-10-07; checked against installed 4.5.7):

- `[gd:config]` https://glances.readthedocs.io/en/develop/config.html — file locations (`%APPDATA%\glances\glances.conf`), `[global] check_update`, per-plugin `disable=`
- `[gd:cmds]` https://glances.readthedocs.io/en/develop/cmds.html — `-C`, `--disable-plugin`/`--enable-plugin` (comma lists), `-B`, `--username`, `--password`, `-t`, `--stdout`, `--export`, `--disable-check-update`, `--enable-mcp`
- `[gd:fetch]` https://glances.readthedocs.io/en/develop/fetch.html — `--fetch`, `--fetch-template`, default template with `gl.ip['address']`
- `[gd:api/python]` https://glances.readthedocs.io/en/develop/api/python.html
- `[gd:api/restful]` https://glances.readthedocs.io/en/develop/api/restful.html — v4 endpoints, Basic + JWT (`/api/4/token`), `--username`/`-u`
- `[gd:api/mcp]` https://glances.readthedocs.io/en/develop/api/mcp.html — `--enable-mcp`, `/mcp/sse`, auth inheritance
- `[gd:quickstart]` https://glances.readthedocs.io/en/develop/quickstart.html — default bind, password, DNS rebinding
- `[gd:docker]` https://glances.readthedocs.io/en/develop/docker.html · `[gd:aoa/containers]` https://glances.readthedocs.io/en/develop/aoa/containers.html · `[gd:aoa/gpu]` https://glances.readthedocs.io/en/develop/aoa/gpu.html
- `[gd:gw/index]` https://glances.readthedocs.io/en/develop/gw/index.html · `[gd:gw/prometheus]` https://glances.readthedocs.io/en/develop/gw/prometheus.html · `[gd:gw/nats]` https://glances.readthedocs.io/en/develop/gw/nats.html
- Release: https://github.com/nicolargo/glances/releases/tag/v4.5.7 · extras: https://github.com/nicolargo/glances/blob/v4.5.7/pyproject.toml
- Installed source read: `glances/api.py`, `glances/outputs/glances_stdout_fetch.py`, `glances/main.py`, `glances/password.py`, `glances/stats.py`, `glances/plugins/containers/engines/docker.py`

Platform:

- WSL config: https://learn.microsoft.com/en-us/windows/wsl/wsl-config · WSL commands: https://learn.microsoft.com/en-us/windows/wsl/basic-commands
- Docker Desktop settings (Software updates, Resource Saver): https://docs.docker.com/desktop/settings-and-maintenance/settings/ · Resource Saver: https://docs.docker.com/desktop/use-desktop/resource-saver/ · `docker desktop update`: https://docs.docker.com/reference/cli/docker/desktop/update/
- Tailscale Serve: https://tailscale.com/kb/1242/tailscale-serve

Repo: `pmoves/tools/bringup/requirements.txt`, `pmoves/configs/cli_tools.yaml` (glances),
`pmoves/mk/preflight.mk` (Glances block; showtime targets), `pmoves/config/glances/`,
`pmoves/tests/config/test_glances_sitrep_template.py`, `pmoves/config/fork_registry.json`
(`Pmoves-Glancer`), `pmoves/docs/handoffs/fleet-bringup-todos-2026-09-01.md:54-105`.
