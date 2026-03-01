# Codex Claude Parity Gaps Report
_Generated: 2026-02-28_

## Scope
- Commands source: `.claude\commands`
- Parity map: `pmoves\docs\AGENTS\CODEX_CLAUDE_PARITY_MAP.md`

## Summary
- Claude command tokens: **113**
- Parity map tokens: **70**
- Mapped tokens: **70**
- Missing tokens: **43**
- Coverage: **61.9%**

## Prefix Coverage
| Prefix | Claude Tokens | Mapped Tokens | Missing Tokens |
| --- | ---: | ---: | ---: |
| `agent-sdk` | 4 | 4 | 0 |
| `agents` | 5 | 5 | 0 |
| `archon` | 3 | 3 | 0 |
| `botz` | 4 | 1 | 3 |
| `chit` | 6 | 6 | 0 |
| `cipher` | 3 | 3 | 0 |
| `crush` | 2 | 0 | 2 |
| `db` | 3 | 0 | 3 |
| `deploy` | 7 | 6 | 1 |
| `discord` | 2 | 1 | 1 |
| `github` | 4 | 4 | 0 |
| `gpu` | 3 | 3 | 0 |
| `health` | 3 | 2 | 1 |
| `hyperdim` | 3 | 0 | 3 |
| `jellyfin` | 2 | 1 | 1 |
| `k8s` | 3 | 0 | 3 |
| `langextract` | 4 | 0 | 4 |
| `minio` | 3 | 0 | 3 |
| `model` | 2 | 0 | 2 |
| `n8n` | 4 | 4 | 0 |
| `nats` | 4 | 4 | 0 |
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
| `yt` | 10 | 10 | 0 |

## Missing Tokens by Prefix
- `botz`
  - `botz:init`
  - `botz:profile`
  - `botz:secrets`
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
