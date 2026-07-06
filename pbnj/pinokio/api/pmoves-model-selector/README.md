# PMOVES Model Selector (Pinokio launcher)

A **UI over the live PMOVES model plane** — it does not embed any model ids. It
reads the model catalog from the registry and gpu-orchestrator APIs at runtime,
lets you pick a model, and drives load/unload through the gpu-orchestrator. It
also launches a local **GGUF serving lane** (`llama-server`, gfx1201/RDNA4 fork)
on the fixed port **8090**, which TensorZero consumes as the `llamacpp_rocm`
provider.

> No hardcoded model ids live anywhere in this launcher. Every model that
> appears in a picker comes from an API response evaluated at click time.

## What it does

| Menu item | Script | Effect |
|-----------|--------|--------|
| Install (build llama.cpp gfx1201) | `install.js` | Clone `tlee933/llama.cpp-rdna4-gfx1201`, `cmake -B build -DGGML_HIP=ON -DAMDGPU_TARGETS=gfx1201`, build `llama-server`. Optional operator-supplied `hf.download` (never a default id). |
| Start llama-server (GGUF, :8090) | `start.js` | `filepicker` a `*.gguf`, then serve it with `HIP_VISIBLE_DEVICES=0,1 llama-server --host 127.0.0.1 --port 8090 --tensor-split 0.5,0.5`. Captures the http URL. |
| Select & Load Model | `select-model.js` | GET registry `:8110/api/models` + gpu-orchestrator `:8200/api/gpu/models` → `input` select picker → POST `:8200/api/gpu/models/load`. |
| Unload Model | `select-model.js` (`action: unload`) | GET `:8200/api/gpu/models/loaded` → picker → POST `:8200/api/gpu/models/unload/{provider}/{model_id}`. |
| Update / Reset | `update.js` / `reset.js` | Rebuild / remove the gfx1201 fork. Downloaded `models/` are left untouched. |

## API contract

```
registry            GET  http://127.0.0.1:8110/api/models
                    → { "items": [ { "model_id": "...", "provider_type": "...", ... } ] }
gpu-orchestrator    GET  http://127.0.0.1:8200/api/gpu/models
                    → { "loaded": [...], "registry": [ { "id": "...", "provider": "..." } ] }
gpu-orchestrator    GET  http://127.0.0.1:8200/api/gpu/models/loaded  → { "models": [...] }
gpu-orchestrator    POST http://127.0.0.1:8200/api/gpu/models/load    body { "model_id": "...", "provider": "..." }
gpu-orchestrator    POST http://127.0.0.1:8200/api/gpu/models/unload/{provider}/{model_id}
llama-server (GGUF) GET  http://127.0.0.1:8090/v1/models      → TensorZero `llamacpp_rocm` provider (http://<host>:8090/v1)
```

The picker builds each option's value as `{"provider": ..., "model_id": ...}`.
For registry entries the loadable id is `model_id` (e.g. `qwen3-coder:30b`), **not**
the catalog UUID `id`; for gpu-orchestrator registry entries it is `id`. Items
are deduped on `provider/model_id`.

### Intentional fixed port 8090 (exception to `{{port}}`)

The Pinokio best-practice is to allocate `{{port}}` to avoid conflicts. This
launcher **intentionally pins 8090** because:

- TensorZero's `llamacpp_rocm` provider is configured for `http://<host>:8090/v1`
  (`pmoves/tensorzero/config/tensorzero.toml`), so the serving port cannot float.
- Port 8080 is reserved fleet-wide for Agent Zero (`HERMES_AGENT_INTEGRATION.md`),
  which is why the GGUF lane moved to 8090.

This is the documented deviation from the `{{port}}` convention.

## Usage examples

### curl

```bash
# What can I load?
curl -s http://127.0.0.1:8110/api/models        | jq '.items[] | {model_id, provider_type}'
curl -s http://127.0.0.1:8200/api/gpu/models    | jq '{loaded, registry}'

# Load / unload
curl -s -X POST http://127.0.0.1:8200/api/gpu/models/load \
  -H 'content-type: application/json' \
  -d '{"model_id":"qwen3-coder:30b","provider":"ollama"}'
curl -s -X POST http://127.0.0.1:8200/api/gpu/models/unload/ollama/qwen3-coder:30b

# GGUF lane (once start.js is running)
curl -s http://127.0.0.1:8090/v1/models
```

### Python

```python
import requests

catalog = requests.get("http://127.0.0.1:8110/api/models").json()["items"]
pick = catalog[0]  # choose interactively in real use — never hardcode
requests.post(
    "http://127.0.0.1:8200/api/gpu/models/load",
    json={"model_id": pick["model_id"], "provider": pick["provider_type"]},
)
```

### JavaScript

```js
const catalog = (await (await fetch("http://127.0.0.1:8110/api/models")).json()).items;
const pick = catalog[0]; // choose interactively — never hardcode
await fetch("http://127.0.0.1:8200/api/gpu/models/load", {
  method: "POST",
  headers: { "content-type": "application/json" },
  body: JSON.stringify({ model_id: pick.model_id, provider: pick.provider_type }),
});
```

## Post-merge operator step (live symlink)

This launcher currently lives inside a temporary git worktree, so a symlink from
`~/pinokio/api/` would dangle. **After this branch merges to `main`**, the operator
should create the live link from the canonical repo checkout:

```bash
# Replace /path/to/your/checkout with wherever this repo is cloned on the operator machine.
ln -sfn /path/to/your/checkout/pbnj/pinokio/api/pmoves-model-selector \
        "$HOME/pinokio/api/pmoves-model-selector"
```

## Launcher conformance (exit-checklist confirmations)

Mirrored against `/home/pmoves-knuckles/pinokio/prototype/system/examples/mochi/start.js`
and `.claude/PINOKIO_LAUNCHER_GUIDE.md`:

- **URL capture (guide "Critical Pattern Lock" + mochi lines 21-40):** `start.js`
  step 3 uses `on: [{ event: "/(http:\\/\\/[0-9.:]+)/", done: true }]`, and step 4
  sets `local.set { url: "{{input.event[1]}}" }` — the mandated pattern exactly.
- **Example lock-in:** `start.js`'s `daemon: true` + `shell.run` + capture + `local.set`
  shape mirrors mochi `start.js` lines 1-42; the sibling `pbnj/.../pmoves-agent-zero/start.js`
  (lines using `event: "/(http:\\/\\/[0-9.:]+)/"` + `{{input.event[1]}}`) was the
  in-repo cross-check.
- **Dynamic menu (guide best-practice #7):** `pinokio.js` returns menu items from
  `info.exists(...)` / `info.running(...)` / `info.local("start.js")`, mirroring
  `pmoves-agent-zero/pinokio.js`; `default: true` set on the active step.
- **AI bundle (guide "AI Libraries"):** `install.js` declares `requires: { bundle: "ai" }`
  so ROCm/HIP prerequisites install before the build.
- **`{{port}}` exception:** documented above — 8090 is pinned by TensorZero.
- **No hardcoded models:** verified — every picker item is derived from a live API
  response; the merge logic was unit-checked against the real `:8110/api/models`
  payload and yields `{provider:"ollama", model_id:"qwen3-coder:30b"}`.
- **Cross-platform note:** the GGUF/ROCm build is Linux-only (gfx1201/AMD), so
  `pinokio.json` declares `"platform": ["linux"]`. The select/load/unload UI is
  transport-only and portable.

## Smoke results (recorded at author time, honest)

- `registry :8110` — container `pmoves-model-registry-1` **Up (healthy)** but its
  port is **not published to the host** in the current compose run
  (`8110/tcp`, no host mapping). Verified in-container: `/healthz` → `{"status":"healthy"}`,
  `/api/models` → `{"items":[{"model_id":"qwen3-coder:30b","provider_type":"ollama",...}]}`
  (1 model; catalog being populated in parallel).
- `gpu-orchestrator :8200` — **down** (no container running); load/unload round-trip
  not exercised.
- `llama-server :8090` — **down** (fork not yet built; the long GPU build was
  intentionally not run — `install.js` only encodes it).
