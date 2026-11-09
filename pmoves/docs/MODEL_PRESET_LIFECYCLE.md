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
3. CHECK   make a0-model-sync-check (--check, --target agent-zero only)
           writes nothing. Exit 0 = clean, 1 = drift (live presets missing or
           their parsed presets differ; the provenance header is ignored),
           2 = UNDECIDED (registry unreachable, empty chat lane, or live file
           unreadable). Fleet sweeps score 1 as drift and 2 as no verdict -
           a registry outage is never reported as drift.
4. APPLY   make a0-model-sync (--apply-presets) archives the live file to
           pmoves/data/model-sync/review/ (CB-4) and overwrites in place.
           Without the flag, when a live presets file already exists a review
           copy lands in pmoves/data/model-sync/review/ (OUTSIDE the
           bind-mounted usr/plugins/_model_config dir); when no live file
           exists yet (fresh node) it is written in place.
           Review copies and archives are named
           presets.yaml.<instance>-<path hash>.{new,bak-<timestamp>}, so
           variants never collide; archives are pruned to the newest
           A0_PRESETS_BACKUP_KEEP (default 10, 0 = keep all) per instance+path.

## Per-node compatibility (env contracts, nothing hardcoded)

| Setting              | Env var                 | Default                          |
|----------------------|-------------------------|----------------------------------|
| presets output root  | per-instance usr var (below) | docked: ./data/agent-zero/usr (compose default) |
| ollama lane api_base | PMOVES_OLLAMA_BASE_URL  | http://pmoves-ollama:11434 (the compose service) |
| TensorZero base      | TENSORZERO_BASE_URL     | http://tensorzero-gateway:3000   |
| cloud lane order     | MODEL_CLOUD_FALLBACK_ORDER | ollama_cloud,cloudflare_free,coding_plan |
| instance stamp       | make INSTANCE=<name> (command line only) or A0_MODEL_SYNC_INSTANCE | docked |
| alternate output     | make OUT=<path> (command line only) or A0_MODEL_SYNC_OUT | (instance usr dir) |
| archives kept        | A0_PRESETS_BACKUP_KEEP  | 10                               |

Each instance resolves its output through the SAME var its compose file binds
to /a0/usr (models_sync.py A0_INSTANCE_USR_ENV):

| INSTANCE        | usr-dir var        | compose file                               |
|-----------------|--------------------|--------------------------------------------|
| docked          | AGENT_ZERO_USR_DIR | docker-compose.yml / docker-compose.agents.yml |
| darkxside       | DARKXSIDE_USR_DIR  | docker-compose.darkxside-sidecar.yml       |
| darkxside-vm    | A0VM_USR_DIR       | docker-compose.agent-zero-darkxside-vm.yml |
| darkxside-inst  | A0INST_USR_DIR     | docker-compose.agent-zero-instances.yml    |
| spark           | SPARK_USR_DIR      | docker-compose.spark-sidecar.yml           |

A node relocating usr to any drive gets presets written exactly where the
container reads them. Relative values resolve against pmoves/ (compose
--project-directory semantics); absolute paths land anywhere on the node.
Only docked has an in-repo default. Any other instance whose var is unset
(or an instance not in the table) exits 2 unless OUT=<path> is given, so a
variant run can never overwrite the docked live presets.
INSTANCE and OUT are read from the make command line only; an exported shell
variable of the same name is ignored.

SPARK's local GPU lane is the checked-in variant
`pmoves/config/agent-zero/model-presets-spark.yaml` (Default = host-Ollama
GPU variants, cloud lanes kept by name). See PATTERNS.md, Known Road - a local
model lane for an Agent Zero node.

## Degradation ladder (config never goes empty)

live registry rows -> template-derived rows (parsed at runtime from the
template yaml) -> last-resort minimal rows (only if the template itself is
unreadable, or parses but yields no chat preset). Generating an EMPTY preset
set over an existing live file is refused with exit 2, and the degraded
result is re-checked, so no rung can write a header-only file.

## Rules

- Do not hand-edit generated presets.yaml. Fix the registry (source of
  truth) or the template (fallback defaults) and regenerate.
- The docked template (model-presets-docked.yaml) is the checked-in fallback
  for this generator; it derives fallback rows from it at runtime. Per-instance
  variant presets (e.g. model-presets-darkxside.yaml, seeded by
  docker-compose.darkxside-sidecar.yml) are checked in and seeded separately;
  the generator does not read them.
- Presets named Default, TensorZero, Registry or Fallback-N belong to the
  generator and are rewritten on every sync. Any other name is a hand-kept
  lane and is carried over verbatim.
- Preset writes go through the make targets. Raw docker/compose invocations
  for preset management are forbidden (Known Roads).
