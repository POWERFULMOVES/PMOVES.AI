# Model Preset Lifecycle (Agent Zero) - reproducible per-node deployment

Doctrine: presets are NEVER handwritten and NEVER hardcoded. The model
registry is the single config authority. Files on disk are GENERATED; the
checked-in template (pmoves/config/agent-zero/model-presets-docked.yaml) is
only a fallback source, and even its rows are DERIVED at runtime.

## Pipeline (make targets only - Known Roads)

1. FETCH   sync-dynamic reads the live Supabase registry (v_service_models /
           v_active_models) over REST, falling back to psql in the DB container.
2. GEN     the generator emits presets.yaml: TensorZero lane first (when its
           chat-lane row exists), then the best direct provider lane, then
           concrete-row fallbacks. Unresolvable ids are skipped, never invented.
3. CHECK   make a0-model-sync-check (--check) writes nothing and exits 1 when
           the live presets are missing or differ. Fleet sweeps score nodes.
4. APPLY   make a0-model-sync (--apply-presets) overwrites in place. Without
           the flag, a review copy lands in pmoves/data/model-sync/review/
           (OUTSIDE the bind-mounted usr/plugins/_model_config dir).

## Per-node compatibility (env contracts, nothing hardcoded)

| Setting              | Env var                 | Default (matches compose)        |
|----------------------|-------------------------|----------------------------------|
| presets output root  | AGENT_ZERO_USR_DIR      | ./data/agent-zero/usr            |
| ollama lane api_base | PMOVES_OLLAMA_BASE_URL  | http://pmoves-ollama-1:11434     |
| TensorZero base      | TENSORZERO_BASE_URL     | http://tensorzero-gateway:3000   |
| cloud lane order     | MODEL_CLOUD_FALLBACK_ORDER | ollama_cloud,cloudflare_free,coding_plan |
| instance stamp       | make INSTANCE=<name>    | docked                           |
| alternate output     | make OUT=<path>         | (compose default path)           |

AGENT_ZERO_USR_DIR is the SAME var docker-compose binds to /a0/usr, so a node
relocating usr to any drive gets presets written exactly where the container
reads them. Relative values resolve against pmoves/ (compose
--project-directory semantics); absolute paths land anywhere on the node.
The darkxside variant uses its own USR_DIR var - set it when generating for
that instance (INSTANCE=darkxside OUT=<its usr path>).

SPARK's local GPU lane is the checked-in variant
`pmoves/config/agent-zero/model-presets-spark.yaml` (Default = host-Ollama
GPU variants, cloud lanes kept by name). See PATTERNS.md, Known Road - a local
model lane for an Agent Zero node.

## Degradation ladder (config never goes empty)

live registry rows -> template-derived rows (parsed at runtime from the
template yaml) -> last-resort minimal rows (only if the template itself is
unreadable). Generating an EMPTY preset set over an existing live file is
refused with exit 2.

## Rules

- Do not hand-edit generated presets.yaml. Fix the registry (source of
  truth) or the template (fallback defaults) and regenerate.
- The template yaml is the only checked-in model config; generators derive
  fallback rows from it at runtime.
- Preset writes go through the make targets. Raw docker/compose invocations
  for preset management are forbidden (Known Roads).
