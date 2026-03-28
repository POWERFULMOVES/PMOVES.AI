# Claude -> Codex Parity Map (PMOVES)
_Last updated: 2026-03-28_

This map translates common `.claude/commands/*` workflows into Codex-native
operations (`make`, `curl`, and existing PMOVES scripts).

## KRISS KROSS ownership

- `Codex` is parity owner when Codex is lane lead ("on the 1s and 2s"):
  Codex writes Codex command mappings and signs parity release readiness.
- `Claude` is counterpoint/scout in Codex-led windows: Claude collects failing
  checks, review comments, and alternative diffs in a separate branch lane.
- If both agents touch parity scope, use KRISS KROSS overlay:
  one owner lane + one scout lane + explicit release signature.

## Parity authority workflow

1. Update command mappings in this file.
2. Run `make -C pmoves codex-parity-check` to generate coverage report.
3. If preparing merge gates, run `make -C pmoves codex-parity-check-strict`.
4. Attach `pmoves/docs/AGENTS/CODEX_CLAUDE_PARITY_GAPS.md` in PR notes.

## Health and bring-up

| Claude command | Codex equivalent |
| --- | --- |
| `/health:quick` | `make -C pmoves codex-health-quick` |
| `/health:check-all` | `make -C pmoves verify-all` |
| `/deploy:up` | `SUPABASE_RUNTIME=cli make -C pmoves up` |
| `/deploy:smoke-test` | `make -C pmoves smoke` |
| `/deploy:preflight` | `make -C pmoves preflight` |
| `/deploy:bootstrap-env` | `make -C pmoves env-setup && make -C pmoves env-check` |
| `/deploy:secrets-funnel` | `make -C pmoves secrets-funnel` |

## Retrieval and research

| Claude command | Codex equivalent |
| --- | --- |
| `/search:hirag` | `curl -X POST http://localhost:8086/hirag/query -H "Content-Type: application/json" -d '{"query":"<q>","top_k":10,"rerank":true}'` |
| `/search:supaserch` | `make -C pmoves supaserch-smoke` then query HTTP fallback `http://localhost:8099/v1/search?q=<q>` |
| `/search:deepresearch` | `make -C pmoves deepresearch-smoke` or `make -C pmoves deepresearch-smoke-in-net` |

## CHIT, geometry, and EvoSwarm

| Claude command | Codex equivalent |
| --- | --- |
| `/chit:bus` | `curl -fsS http://localhost:8086/hirag/admin/stats | jq .` |
| `/chit:encode` | publish through PMOVES producers (`pmoves-yt`, `hi-rag-v2`) and validate via `make -C pmoves smoke` |
| `/chit:decode` | use geometry calibration/report endpoints and retrieval assertions |
| `/chit:visualize` | use geometry UI/demo targets (`make -C pmoves web-geometry`) |
| `/chit:bpm` | `curl -fsS http://localhost:8086/geometry/calibration/report | jq .` and validate bpm-derived geometry metadata |
| `/chit:floos` | `make -C pmoves pr-monitor-flows` then `make -C pmoves pr-monitor-chit-packet` |
| EvoSwarm checks | `curl -fsS http://localhost:8113/healthz` and `curl -fsS http://localhost:8113/config | jq .` |

## Agent orchestration and MCP

| Claude command | Codex equivalent |
| --- | --- |
| `/agents:status` | `curl -fsS http://localhost:8080/healthz | jq .` and `curl -fsS http://localhost:8091/healthz | jq .` |
| `/agents:execute` | `curl -fsS http://localhost:8080/healthz | jq .` then execute task through Agent Zero MCP bridge |
| `/agents:mcp-query` | `curl -fsS http://localhost:8080/mcp/health | jq .` then authenticated `/mcp/*` calls |
| `/agents:subordinate` | delegate via NATS `agent.handoff.request.v1` and capture completion on `agent.handoff.completed.v1` |
| `/agents:task-status` | monitor active tasks through Agent Zero runtime status and NATS task subjects |
| `/botz:mcp` | BotZ config: `PMOVES-BoTZ/config/codex/mcp_gateway.json` and PMOVES root codex profile |
| Claude Cipher MCP (`pmoves-cipher` in `.claude/mcp.json`) | `uv run --directory ./pmoves-cipher-mcp python -m cipher_mcp.server` and verify `curl -fsS http://localhost:8096/health` |

## High-priority parity wave (Mar 2026)

| Claude command | Codex equivalent |
| --- | --- |
| `/agent-sdk:create` | `pmoves agent-sdk create <role> --model openai::qwen3:8b` |
| `/agent-sdk:run` | `pmoves agent-sdk run <agent-id> "<task>"` |
| `/agent-sdk:resume` | `pmoves agent-sdk resume list` then `pmoves agent-sdk resume <session-id>` |
| `/agent-sdk:handoff` | publish NATS `agent.handoff.request.v1` and await `agent.handoff.accepted.v1`/`agent.handoff.completed.v1` |
| `/archon:status` | `curl -sf http://localhost:8091/healthz | jq .` and `curl -sf -o /dev/null -w "%{http_code}" http://localhost:3737/` |
| `/archon:forms` | `curl -sf http://localhost:8091/api/forms | jq '.[] | {id,name,agent_type,status}'` |
| `/archon:prompts` | `curl -sf http://localhost:8091/api/prompts | jq '.[] | {id,name,tags,updated_at}'` |
| `/cipher:store` | `curl -s -X POST http://localhost:8096/api/memory -H "Content-Type: application/json" -d '{"content":"<content>","category":"<category>","source":"codex"}'` |
| `/cipher:search` | `curl -s "http://localhost:8096/api/memory/search?q=<query>&limit=10"` |
| `/cipher:reasoning` | store/retrieve reasoning traces with category `reasoning_trace` via Cipher memory API |
| `/gpu:status` | `curl -s http://localhost:8200/api/gpu/status | jq .` |
| `/gpu:models` | `curl -s "http://localhost:8200/api/gpu/models?include_unloaded=true" | jq .` |
| `/gpu:optimize` | `curl -s -X POST http://localhost:8200/api/gpu/optimize | jq .` |
| `/n8n:workflows` | `curl -s -H "X-N8N-API-KEY: $N8N_API_KEY" http://localhost:5678/api/v1/workflows | jq .` |
| `/n8n:execute` | `curl -X POST -H "X-N8N-API-KEY: $N8N_API_KEY" http://localhost:5678/api/v1/workflows/<id>/run` |
| `/n8n:nodes` | query PMOVES n8n MCP node docs under `PMOVES-BoTZ/features/n8n/n8n-mcp/data/` |
| `/n8n:suggest` | run n8n MCP suggestion flow via `pmoves-n8n-agent` for AI-assisted workflow synthesis |
| `/nats:status` | `curl -s http://localhost:8222/varz` and `curl -s http://localhost:8222/jsz` |
| `/nats:streams` | `curl -s http://localhost:8222/jsz?streams=1` |
| `/nats:monitor` | `nats sub "<subject-pattern>" --count 20` |
| `/nats:publish` | `nats pub "<subject>" '<json-payload>'` |
| `/yt:help` | use `.claude/commands/yt/help.md` as the YouTube operations index |
| `/yt:list-channels` | `cat pmoves/config/channel_monitor.json | jq '.channels[] | {channel_name,channel_id,enabled,auto_process}'` |
| `/yt:add-channel` | update `pmoves/config/channel_monitor.json` with channel source and restart `channel-monitor` |
| `/yt:add-playlist` | update `pmoves/config/channel_monitor.json` with playlist source and restart `channel-monitor` |
| `/yt:remove-channel` | remove source from `pmoves/config/channel_monitor.json` and restart `channel-monitor` |
| `/yt:toggle-channel` | toggle `enabled` in `pmoves/config/channel_monitor.json` and restart `channel-monitor` |
| `/yt:ingest-video` | `curl -X POST http://localhost:8077/yt/ingest -H "Content-Type: application/json" -d '{"url":"<youtube-url>","namespace":"pmoves.manual"}'` |
| `/yt:pending` | inspect pending/discovered queue via channel-monitor logs and Supabase status tables |

## Wave-2 completion map (Mar 2026)

| Claude command | Codex equivalent |
| --- | --- |
| `/botz:init` | bootstrap BoTZ runtime using `PMOVES-BoTZ/config/codex/mcp_gateway.json` plus `make -C pmoves codex-config` |
| `/botz:profile` | set BoTZ profile via BoTZ config and verify with `make -C pmoves codex-health-quick` |
| `/botz:secrets` | run `make -C pmoves secrets-funnel` and validate with `make -C pmoves secrets-audit` |
| `/crush:setup` | configure local Crush/TensorZero provider lane and validate with `make -C pmoves codex-health-quick` |
| `/crush:status` | inspect Crush/GPU provider health through TensorZero and GPU status endpoints |
| `/db:backup` | run backup workflow for active runtime DB (`make -C pmoves supa-status` then DB backup script) |
| `/db:migrate` | apply migrations with `make -C pmoves supabase-bootstrap` |
| `/db:query` | query runtime DB via `docker exec`/`psql` against Supabase/Postgres containers |
| `/deploy:audit-layers` | run `make -C pmoves audit-layers-static && make -C pmoves audit-layers-runtime` |
| `/discord:notify` | publish notification payloads via `services/publisher-discord` webhook path and verify `/healthz` on `:8094` |
| `/health:metrics` | inspect Prometheus/Grafana targets: `make -C pmoves monitoring-report` |
| `/hyperdim:animate` | run Hyperdimensions animation path via geometry UI lane (`make -C pmoves web-geometry`) |
| `/hyperdim:export` | export Hyperdimensions/geometry packet artifacts from geometry services and overlays |
| `/hyperdim:render` | render Hyperdimensions boundary views using geometry + EvoSwarm control-plane endpoints |
| `/jellyfin:sync` | trigger bridge refresh and validate with `make -C pmoves jellyfin-verify` |
| `/k8s:deploy` | apply deployment manifests from K8s ops lane for target environment |
| `/k8s:logs` | inspect pod logs via `kubectl logs` for target namespace/workload |
| `/k8s:status` | inspect cluster workload state via `kubectl get pods,svc -A` |
| `/langextract:extract` | execute extraction lane using configured provider (`tensorzero`/Workers AI) |
| `/langextract:process` | run LangExtract processing pipeline against queued items |
| `/langextract:provider` | set provider route and validate via `LANGEXTRACT_PROVIDER` plus health checks |
| `/langextract:status` | inspect LangExtract runtime health/telemetry outputs |
| `/minio:presign` | validate presign service with `make -C pmoves smoke-presign-put` |
| `/minio:status` | verify storage endpoint and credentials with `make -C pmoves preflight` |
| `/minio:upload` | upload through presign PUT flow and confirm object availability |
| `/model:load` | load runtime model profile via `make -C pmoves model-apply` or `model-swap` |
| `/model:unload` | unload/retire model lane using model profile controls and GPU optimize path |
| `/notebook:query` | query notebook service/API state and data path on `:8095` |
| `/notebook:sync` | sync notebook ingestion/indexing through notebook ops workflow |
| `/observability:alerts` | inspect alert status in Grafana/Prometheus alerting lanes |
| `/observability:dashboard` | open runtime dashboards (`Grafana`, services overview) and verify panels |
| `/observability:query` | run Prometheus/Loki queries for live runtime diagnostics |
| `/pipecat:connect` | validate Flute/Pipecat connectivity using voice session endpoints |
| `/tensorzero:models` | query TensorZero model registry endpoint and active providers |
| `/tts:test-all` | run full TTS validation across configured voices/providers |
| `/tts:voices` | list available TTS voices from the runtime provider |
| `/voice:status` | inspect voice pipeline health (`Flute`, TTS backend) |
| `/voice:synthesize` | synthesize sample output via Flute `/v1/voice/synthesize/prosodic` |
| `/workitems:claim` | claim work item in team queue and emit tracking note via PR/CHIT flow |
| `/workitems:complete` | close work item and record completion evidence in trail/docs |
| `/workitems:list` | list current work items from task board/queue source |
| `/ultrathink` | run deep-dive reasoning mode and attach structured output to execution notes |

## Voice stack (Flute/TTS/Pipecat)

| Claude command | Codex equivalent |
| --- | --- |
| `/pipecat:status` | `curl -fsS http://localhost:8055/healthz | jq .` |
| `/tts:status` | `curl -fsS http://localhost:7861/gradio_api/info | jq .` |
| `/tts:synthesize` | Flute synth endpoint `POST /v1/voice/synthesize/prosodic` |

## Runtime services and tests

| Claude command | Codex equivalent |
| --- | --- |
| `/test:smoke` | `make -C pmoves smoke` |
| `/test:pr` | `make -C pmoves verify-all` |
| `/yt:status` | `make -C pmoves channel-monitor-smoke` and `curl -fsS http://localhost:8077/healthz` |
| `/yt:check-now` | `make -C pmoves channel-monitor-discord-drop-smoke` |
| `/discord:status` | `curl -fsS http://localhost:8094/healthz` |
| `/jellyfin:status` | `curl -fsS http://localhost:8093/healthz` |
| `/notebook:status` | `curl -fsS http://localhost:8095/healthz` |

## Git and worktree operations

| Claude command | Codex equivalent |
| --- | --- |
| `/worktree:list` | `git worktree list` |
| `/worktree:create` | `git worktree add <path> -b <branch> <base>` |
| `/worktree:switch` | `git -C <worktree-path> checkout <branch>` |
| `/worktree:cleanup` | `git worktree prune` |
| `/github:actions` | `gh run list --limit 20` |
| `/github:pr-review` | `gh pr checks <pr-number>` and `gh pr view <pr-number> --comments` |
| `/github:issues` | `gh issue list --limit 20` |
| `/github:security` | `gh api repos/POWERFULMOVES/PMOVES.AI/code-scanning/alerts` |
| `/pr-monitor` | `make -C pmoves pr-monitor` then `make -C pmoves pr-monitor-live` |

## Submodule integration audit

| Claude practice | Codex equivalent |
| --- | --- |
| Manual review of module docs | `make -C pmoves codex-audit` |
| Update command docs | Update `pmoves/docs/AGENTS/CODEX_OPERATOR_HOME.md` and this parity map |
| Measure command coverage | `make -C pmoves codex-parity-check` |

## Infrastructure (Known Roads)

| Claude command | Codex equivalent |
| --- | --- |
| `/deploy:services` (volume reset) | `make -C pmoves volume-reset SERVICE=...` |
| `/deploy:services` (volume list) | `make -C pmoves volume-list` |
| docker prune (safe) | `make -C pmoves docker-prune` |
| docker prune (aggressive) | `make -C pmoves docker-prune-all` |
| branch audit | `make -C pmoves branch-audit` |
| branch cleanup | `make -C pmoves branch-cleanup EXECUTE=1` |

Fleet remote access parity:

| Claude practice | Codex equivalent |
| --- | --- |
| tailnet device inventory | `tailscale status --json` or `curl -H "Authorization: Bearer $TAILSCALE_API_KEY" https://api.tailscale.com/api/v2/tailnet/-/devices` |
| stale node delete | `curl -X DELETE -H "Authorization: Bearer $TAILSCALE_API_KEY" https://api.tailscale.com/api/v2/device/<deviceId>` |
| RustDesk relay audit | `pmoves/docs/operations/RUSTDESK_SELF_HOSTED.md` plus remote `systemctl status hbbs hbbr fleet-audit-watcher` on KVM2 |
| fleet policy audit | `curl -H "Authorization: Bearer $TAILSCALE_API_KEY" -H "Accept: application/hujson" https://api.tailscale.com/api/v2/tailnet/-/acl` and compare to `pmoves/configs/tailscale-acl-policy.json` |

For z890 rebuild manifests, translate raw `docker compose build` steps to the nearest Known Road whenever one exists. Raw targeted builds are fallback preparation only; the final bring-up should still go through the make target path.

## Guidance

- Keep Claude and Codex workflows semantically aligned, not text-identical.
- Prefer stable Make targets over ad-hoc one-off shell snippets.
- For every new Claude command added to `.claude/commands/`, add a Codex mapping here and rerun `codex-parity-check`.
