# Codex Claude Parity Gaps Report
_Generated: 2026-02-25_

## Scope
- Commands source: `C:\Users\russe\Documents\GitHub\PMOVES.AI\.claude\commands`
- Parity map: `C:\Users\russe\Documents\GitHub\PMOVES.AI\pmoves\docs\AGENTS\CODEX_CLAUDE_PARITY_MAP.md`

## Summary
- Claude command tokens: **113**
- Parity map tokens: **35**
- Mapped tokens: **35**
- Missing tokens: **78**
- Coverage: **31.0%**

## Prefix Coverage
| Prefix | Claude Tokens | Mapped Tokens | Missing Tokens |
| --- | ---: | ---: | ---: |
| `agent-sdk` | 4 | 0 | 4 |
| `agents` | 5 | 2 | 3 |
| `archon` | 3 | 0 | 3 |
| `botz` | 4 | 1 | 3 |
| `chit` | 6 | 3 | 3 |
| `cipher` | 3 | 0 | 3 |
| `crush` | 2 | 0 | 2 |
| `db` | 3 | 0 | 3 |
| `deploy` | 7 | 6 | 1 |
| `discord` | 2 | 1 | 1 |
| `github` | 4 | 4 | 0 |
| `gpu` | 3 | 0 | 3 |
| `health` | 3 | 2 | 1 |
| `hyperdim` | 3 | 0 | 3 |
| `jellyfin` | 2 | 1 | 1 |
| `k8s` | 3 | 0 | 3 |
| `langextract` | 4 | 0 | 4 |
| `minio` | 3 | 0 | 3 |
| `model` | 2 | 0 | 2 |
| `n8n` | 4 | 0 | 4 |
| `nats` | 4 | 0 | 4 |
| `notebook` | 3 | 1 | 2 |
| `observability` | 3 | 0 | 3 |
| `pipecat` | 2 | 1 | 1 |
| `root` | 2 | 0 | 2 |
| `search` | 3 | 3 | 0 |
| `tensorzero` | 1 | 0 | 1 |
| `test` | 2 | 2 | 0 |
| `tts` | 4 | 2 | 2 |
| `voice` | 2 | 0 | 2 |
| `workitems` | 3 | 0 | 3 |
| `worktree` | 4 | 4 | 0 |
| `yt` | 10 | 2 | 8 |

## Missing Tokens by Prefix
- `agent-sdk`
  - `agent-sdk:create`
  - `agent-sdk:handoff`
  - `agent-sdk:resume`
  - `agent-sdk:run`
- `agents`
  - `agents:execute`
  - `agents:subordinate`
  - `agents:task-status`
- `archon`
  - `archon:forms`
  - `archon:prompts`
  - `archon:status`
- `botz`
  - `botz:init`
  - `botz:profile`
  - `botz:secrets`
- `chit`
  - `chit:bpm`
  - `chit:bus`
  - `chit:floos`
- `cipher`
  - `cipher:reasoning`
  - `cipher:search`
  - `cipher:store`
- `crush`
  - `crush:setup`
  - `crush:status`
- `db`
  - `db:backup`
  - `db:migrate`
  - `db:query`
- `deploy`
  - `deploy:audit-layers`
- `discord`
  - `discord:notify`
- `gpu`
  - `gpu:models`
  - `gpu:optimize`
  - `gpu:status`
- `health`
  - `health:metrics`
- `hyperdim`
  - `hyperdim:animate`
  - `hyperdim:export`
  - `hyperdim:render`
- `jellyfin`
  - `jellyfin:sync`
- `k8s`
  - `k8s:deploy`
  - `k8s:logs`
  - `k8s:status`
- `langextract`
  - `langextract:extract`
  - `langextract:process`
  - `langextract:provider`
  - `langextract:status`
- `minio`
  - `minio:presign`
  - `minio:status`
  - `minio:upload`
- `model`
  - `model:load`
  - `model:unload`
- `n8n`
  - `n8n:execute`
  - `n8n:nodes`
  - `n8n:suggest`
  - `n8n:workflows`
- `nats`
  - `nats:monitor`
  - `nats:publish`
  - `nats:status`
  - `nats:streams`
- `notebook`
  - `notebook:query`
  - `notebook:sync`
- `observability`
  - `observability:alerts`
  - `observability:dashboard`
  - `observability:query`
- `pipecat`
  - `pipecat:connect`
- `root`
  - `pr-monitor`
  - `ultrathink`
- `tensorzero`
  - `tensorzero:models`
- `tts`
  - `tts:test-all`
  - `tts:voices`
- `voice`
  - `voice:status`
  - `voice:synthesize`
- `workitems`
  - `workitems:claim`
  - `workitems:complete`
  - `workitems:list`
- `yt`
  - `yt:add-channel`
  - `yt:add-playlist`
  - `yt:help`
  - `yt:ingest-video`
  - `yt:list-channels`
  - `yt:pending`
  - `yt:remove-channel`
  - `yt:toggle-channel`
