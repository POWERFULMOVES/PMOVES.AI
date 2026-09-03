# IDE / Harness / Pinokio Fleet Console Integration Plan

**Status:** PROPOSAL (2026-09-03) — from the delegated repo audit (file:line citations throughout).
Operator directive: VS Code (and KiloCode-class harnesses) need proper PMOVES.AI plugin/extension/MCP
config so nodes run with slick integration; PMOVES-pinokio mirrors + enhances this as the user-facing
launcher for services AND cli harnesses/agents; services should launch, autonetwork-scan, dispatch,
self-heal, and transform PMOVES.AI as capabilities come online — enabling optimal deployment, load
and resource sharing.

## 1. VS Code gaps (9, from audit)

1. **No MCP client**: extensions.json:2-22 recommends 18 extensions, zero MCP-capable (no Cline/
   Continue/native MCP), no `.vscode/mcp.json`. Yet mcp_inventory.json:189-201 already serves
   docker-gateway SSE :8090 and cipher :8105. Fix: add `vscode` to inventory clients + generator
   renderer (RENDERERS at mcp_config_generator.py:317-324) → emit `.vscode/mcp.json`.
2. **Compose schemas unmapped**: settings.json:62-65 covers only workflow + room manifests; none of
   the 23+ `pmoves/docker-compose*.yml` overlays get the docker-compose schema (typo-blind 6-tier
   stack). Map schemastore docker-compose.json to both `pmoves/` and `PMOVES-*/` globs.
3. **Windows venv path**: settings.json:83 hardcodes interpreter w/o `bin/python` vs
   `Scripts/python.exe` split (Makefile:244-249 documents the trap — it already bit the Makefile).
   Platform-conditional settings or makefile-tools detection.
4. **Task coverage ~12/878**: tasks.json covers 12 targets vs 875 unique (Makefile 561 + mk/*.mk
   314). Missing high-value: up-voice/flute smokes (3363,4430,4447), channel-monitor-up (2799),
   up-pinokio + bridge smokes (4308-4346), health-summary (1844), venv-bringup (239),
   overlay-up-<tier> (canonical Known Road).
5. **No problemMatcher + makefile tools unconfigured**: settings.json:81 disables configureOnOpen
   with no makefile.path → the recommended extension never targets pmoves/Makefile.
6. **launch.json thin**: 4 configs, none for flute/voice supervisors, cipher :8105, Hi-RAG :8086,
   pinokio_bridge :8130/nats_event_bus :8131, channel-monitor :8097; no pytest-current-file.
7. **Remote parity**: no WSL/Remote-Tunnels recs for Windows hosts; devcontainer extension set
   diverges from extensions.json.
8. **Terminal env parity**: NATS_URL injected but not TS_Z890/CIPHER token paths or the with-env.sh
   loader convention (AGENTS.md:48-54); PowerShell defaultProfile fights the bash/MSYS hooks.
9. **Search noise**: no excludes for `.venv-pmoves` (3GB) at pmoves/ level; no cspell PMOVES
   dictionary (cipher/supabase/nats flagged endlessly).

## 2. Harness gaps (KiloCode-class, 6)

1. **Known-Roads hooks are Claude-only** (.claude/PATTERNS.md:76-105); kilorules.md never mentions
   them — a KiloCode agent can run raw `docker compose up` ungated. Fix: known-roads section +
   kilocode-known-roads skill.
2. **Fail-open permissions**: render_kilocode (mcp_config_generator.py:234-257) auto-allows
   `bash:'allow'`, `edit '**':'allow'`, `<server>_*:'allow'` — contradicts Claude's protected globs.
   Add deny-by-default renderer option for protected paths (compose overlays, migrations, schemas).
3. **Rules are persona-themed, not operational**: load-bearing contracts (env loader, overlay
   layering trap, funnel location, Three-Body governance, CHIT signing) live only in AGENTS.md.
   Add a Non-Obvious Rules pointer at kilorules.md top.
4. **Skill duplication**: 25 skills = 12 kilocode-* + 13 minimax-* near-duplicates; missing
   nats-subject-audit, worktree hygiene, overlay discipline, mcp-inventory regen.
5. **kilo.json drift risk**: no CI parity check vs mcp_inventory.json (tracked_clients at
   mcp_config_generator.py:497 supports it) — add kilo-parity gate.
6. **No hook mirrors**: document in kilorules.md which Claude-hook protections are absent so the
   agent self-compensates (always with-env.sh, never raw docker).

## 3. Pinokio mirror — fleet console (3 moves)

1. **Registry-driven menu**: pmoves-services pinokio.js menu() fetches sentinel `/registry.json`
   and renders one row per announced service (slug/url/health/tier from pmoves_announcer schema
   __init__.py:62-69; tier icons from ServiceTier enum :41-50) — mirrors
   pmoves-agent-defaults.json's per-node capability model into the UI.
2. **Sibling apps, not a mega-app**: `pmoves-fleet` (scanner: make fleet-status + sentinel curl,
   per-node health chips), `pmoves-dispatch` (agent dispatch over the EXISTING pinokio_bridge
   :8130 / nats_event_bus :8131 pair from make up-pinokio — reuse, don't rebuild). Per-service
   atomic launchers per PINOKIO_LAUNCHER_GUIDE.md (URL-capture on:[{event,done:true}] pattern).
3. **Self-heal in the launcher**: extend status.js (currently 3 compose ps calls, status.js:6-29)
   to curl each registry service's health URL; on red → the Known-Road recovery
   (`make secrets-funnel && make up-<svc>`) via shell.run.

## 4. Autonetwork / self-heal — `pmoves/services/fleet_sentinel/`

One small always-on service (NOT a pinokio script or cron — the NATS subscription must persist;
channel-monitor is the proven pattern to copy):
- **Listener**: reuse ServiceAnnouncementListener verbatim (nats_service_listener.py:63-131; queue
  group 'service-listeners' dedupes multi-sentinel) → update_nats_cache (:188) into the existing
  4-level-fallback registry (service_registry.py: env → Supabase catalog → NATS cache → Docker DNS).
- **Health poller**: 30s loop over registry health_check_urls (announce payload carries it,
  pmoves_announcer :65,145) using the parallel-HTTP pattern from flight_check_retro.py; staleness =
  2× the BackgroundAnnouncer interval (60s default, :267-285).
- **Self-heal**: N=3 consecutive failures → canonical recovery via subprocess with with-env.sh env
  (never source env.shared, AGENTS.md:48-54); rate-limit 1 restart/service/10min; every action to a
  jsonl trail (known-roads.jsonl discipline, PATTERNS.md:101).
- **HTTP surface**: GET /registry.json (Pinokio consumes this — launchers need no NATS client),
  /healthz, /actions (restart history).
- **Producers**: services embed the existing announcer template (announce() with retry+backoff).

This is the capability-triggered transformation mechanism: a service that starts announcing
APPEARS in the registry → Pinokio menu row appears → health chip goes live → self-heal owns it →
fleet load/resource sharing optimizes around real capability, not static config.

## Sequencing
1. `.vscode` fixes (schemas, venv, tasks, launch, mcp.json via generator) — one PR, pure config
2. kilocode renderer deny-default + known-roads skill + kilo-parity gate — one PR
3. fleet-sentinel service (listener + poller + /registry.json) — the runtime PR
4. Pinokio registry-driven menu + pmoves-fleet + pmoves-dispatch apps — fork PR (PMOVES-pinokio)
5. Producer rollout: announcer embedded service-by-service as they're touched
