---
name: hermes-agent-integration
description: >
  Launch, manage, and troubleshoot HERMES Agent (NousResearch) within PMOVES.AI.
  Covers profile creation, gateway start/stop, skill installation, NATS bridge
  health checks, cron job management, and cross-platform delegation.
disable-model-invocation: true
---

# hermes-agent-integration

Manage HERMES Agent as a first-class PMOVES citizen.

## What it does

| Command | Purpose |
|---------|---------|
| Launch gateway | `hermes gateway run` with pmoves-hermes profile |
| Install skill | `hermes skills install <url>` into pmoves namespace |
| Health check | Verify gateway + MCP + NATS bridge are online |
| Delegate task | Spawn leaf subagent for bounded PMOVES work |
| Cron job | Schedule recurring PMOVES maintenance via Hermes cron |
| Profile switch | `hermes profile use pmoves-hermes` per room role |

## Prerequisites

1. Hermes Agent installed:
   ```bash
   curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
   ```
2. PMOVES-hermes profile created:
   ```bash
   hermes profile create pmoves-hermes
   ```
3. Secrets populated via CHIT funnel:
   ```bash
   make -C pmoves secrets-funnel
   # then copy relevant keys into ~/.hermes/profiles/pmoves-hermes/.env
   ```

## Quick commands

### Launch gateway (foreground)
```bash
hermes --profile pmoves-hermes gateway run
```

### Launch gateway (background service)
```bash
hermes --profile pmoves-hermes gateway install
hermes --profile pmoves-hermes gateway start
```

### Health check
```bash
# Gateway HTTP health
curl -sf http://localhost:7700/api/health || echo "HERMES GATEWAY DOWN"

# Hermes CLI status
hermes --profile pmoves-hermes status

# NATS bridge -- listen for test event
hermes --profile pmoves-hermes chat -q "publish a test message to hermes.gateway.health.v1"
```

### Install a PMOVES skill
```bash
hermes --profile pmoves-hermes skills install https://raw.githubusercontent.com/POWERFULMOVES/hermes-skills-pmoves/main/pmoves-health/SKILL.md
```

### Run a cron job
```bash
hermes --profile pmoves-hermes cron create "0 9 * * *" --prompt "Run pmoves smoke tests and report to NATS" --deliver nats:hermes.cron.executed.v1
```

### Delegate a task
```bash
hermes --profile pmoves-hermes chat -q "delegate a task to review pmoves/docs for stale links"
```

## NATS Subjects

Hermes Agent publishes to these subjects when integrated:

| Subject | Payload | When |
|---------|---------|------|
| `hermes.gateway.launched.v1` | `{room, node, profile, timestamp}` | Gateway start |
| `hermes.gateway.health.v1` | `{status, uptime_ms, version}` | Periodic health |
| `hermes.mcp.toolcall.v1` | `{tool, args, result, latency_ms}` | MCP execution |
| `hermes.skill.curated.v1` | `{skill_name, action, version}` | Skill install/update |
| `hermes.cron.executed.v1` | `{job_id, output, exit_code}` | Cron completion |
| `hermes.delegate.completed.v1` | `{task_id, summary, artifacts}` | Subagent finish |

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Gateway port conflict | Change port in profile config or stop other service on 7700 |
| Model not responding | `hermes --profile pmoves-hermes doctor` then `hermes model` |
| NATS events not publishing | Verify NATS_URL in profile .env; check `nats sub hermes.gateway.health.v1` |
| Skills not loading | `hermes --profile pmoves-hermes skills list` then `/reload-skills` |
| Secrets redaction blocking | `hermes config set security.redact_secrets false` (restart required) |

## Related

- `pmoves/docs/AGENTS/HERMES_AGENT_INTEGRATION.md` -- full integration spec
- `pmoves/configs/tac_trees/node-hermes-agent.tac.yaml` -- TAC roadmap
- `.claude/agents/hermes-agent.md` -- Three-Body agent definition
- `pmoves/config/rooms/hermes-agent.room.control.json` -- room manifest
