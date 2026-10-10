# Operator brief — secrets manifest changes (2026-09-23)

**For:** the operator (DARKXSIDE). **From:** PMOVES-4090-CLAUDE, lane `feat/mcp-node-capacity-hosting`.
**Parent plan:** `mcp_node_capacity_hosting_plan_2026-09-23.md` (Phases A2 and F).

## Why this is an operator brief and not a PR
`pmoves/chit/secrets_manifest*.yaml` is a **zero-access** path in the damage-control guard. The Known Road domains in `.claude/hooks/damage-control/known_roads.py:184-189` are compose, schema, topic, dockerfile, migrations and launcher. **None covers the manifest**, so no agent road opens it (checked 2026-09-23). Adding a `secrets-manifest` road would be a guard widening, which is a security change needing its own justification. This brief does not propose one.

Format and order come from `pmoves/docs/SECRETS_PIPELINE_REFERENCE.md` §Manifest Structure (v2): **example → manifest → funnel**. Never hand-edit `env.shared` or the tier files.

## Constraint measured today
`make -C pmoves gh-secret-capacity-audit`: `env:Prod` **100/100 (at cap)**, repository scope 90/100, env:PMOVES 1/100. Declared 169, present 133, **32 orphans** (present, declared nowhere). New keys therefore **cannot enter Prod** until room is freed.

## Step 0 — free room (before adding anything)
Reconcile the 32 orphans listed by `gh-secret-capacity-audit`: declare the ones in use and delete the dead ones. Candidates that look like duplicates of each other (verify in use before deleting): `GH_PAT` / `GH_DARKXSIDE` / `CATACLYSMSTUDIOS_GH_PAT` / `HUNNINBEAR_GH_PAT`; `DOCKER_PAT` / `DOCKERHUB_TOKEN`; `GHCR_TOKEN` / `GHCR_APP_*`. Re-run the audit afterwards and record the new headroom from that run.

## Step 1 — the three missing keys
Add each to its `.example` first, then to `secrets_manifest_v2.yaml`, then set the GitHub secret, then run the funnel. The shape follows the reference entry. **Tier and file targets marked VERIFY** should be checked against the consumer before committing; they're my best reading, not a measurement.

```yaml
- id: airtable_api_key
  source: {type: cgp, label: AIRTABLE_API_KEY}
  targets:
  - {file: .env.generated, key: AIRTABLE_API_KEY}
  - github_secret: AIRTABLE_API_KEY        # Prod has no room until Step 0
  required: false
  tier: agent                               # VERIFY: consumer is the Docker MCP airtable server (docker_mcp_secret_map.yaml)
- id: tavily_api_key
  source: {type: cgp, label: TAVILY_API_KEY}
  targets:
  - {file: .env.generated, key: TAVILY_API_KEY}
  - github_secret: TAVILY_API_KEY
  required: false
  tier: agent                               # VERIFY: consumer is the Docker MCP tavily server
- id: mcp_gateway_auth_token
  source: {type: cgp, label: MCP_GATEWAY_AUTH_TOKEN}
  targets:
  - {file: .env.generated, key: MCP_GATEWAY_AUTH_TOKEN}
  - {file: env.tier-agent, key: MCP_GATEWAY_AUTH_TOKEN}   # VERIFY: docker-compose.mcp-gateway.yml:75 reads it via COMPOSE_ENV_FILES
  - github_secret: MCP_GATEWAY_AUTH_TOKEN
  required: false
  tier: agent
```
Then: `make -C pmoves secrets-funnel-from-prod` (runnerless nodes) → `make -C pmoves docker-mcp-secrets-hydrate PROFILE=<node profile>` → `make -C pmoves gh-secret-capacity-audit`.

**MCP_GATEWAY_AUTH_TOKEN follow-up (agent PR, Phase A2):** once the funnel carries it, `scripts/mcp-toolkit-gateway-listen.sh:156-176` stops minting its own token and fails closed when it's unset, and the inventory's `pmoves-docker-gateway-sse` header switches from `CIPHER_API_TOKEN` to `MCP_GATEWAY_AUTH_TOKEN`. Until the funnel carries the key, that PR would break hermes + kilocode, so it waits for this brief.

## Step 2 — per-repo secret routing (Phase F)
Today `github_secret: <NAME>` has **no repo or scope field**, so it can only target PMOVES.AI. Two parts:
- **Agent PR (unguarded code):** teach `pmoves/tools/secrets_sync.py` an optional form, `github_secret: {name: N8N_API_KEY, repo: POWERFULMOVES/PMOVES-N8N}`, keeping the plain string form byte-compatible. Extend `gh-secret-capacity-audit` to measure each named repo's scope. Tests prove the old form is unchanged.
- **Operator (manifest):** after that lands, retarget the n8n entries (2 keys, the pilot) to the n8n fork. Confirm the fork's CI reads them and that the fork starts from its own checkout, then delete them from `env:Prod`.

Order after the pilot: open-notebook (15), supabase (14), jellyfin (4), then the rest. Re-run the audit after each move.
