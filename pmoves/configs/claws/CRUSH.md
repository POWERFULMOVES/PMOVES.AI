# Crush — PMOVES model binding

Per-node [Crush](https://github.com/charmbracelet/crush) configs binding the CLI to the
**GLM coding plan** (`glm_coding_plan` in `pmoves/config/provider_catalog.yaml`).

| File | Node | large | small | local fallback |
|---|---|---|---|---|
| `crush-z890.json` | Z890 coordinator | `glm-5-turbo` | `glm-4-flash` | — (delegates GPU to 5090) |
| `crush-4090.json` | 4090 laptop | `glm-5-turbo` | `glm-4-flash` | `qwen3-coder:30b` via local Ollama |

Both also declare `glm-5v-turbo` for vision, matching the `vision_model` in the 4090 node
profile's `glm_coding_plan`.

## Why these live here and not in the fork

`PMOVES-crush/crush.json` is **upstream Charm's own dev config** — gopls/LSP settings for
developing Crush itself. It is not a PMOVES runtime config, and editing it would create
fork drift that `fleet-fork-sync` has to reconcile on every upstream pull.

PMOVES runtime config therefore lives in the parent repo alongside the other per-node CLI
configs (`opencode-*.json`), following the same convention.

## Installing on a node

Crush resolves config from the working directory first, then the user config dir. Copy the
node's file to whichever scope you want:

```bash
# Project scope (per-repo)
cp pmoves/configs/claws/crush-z890.json ./crush.json

# User scope (all repos on that node)
mkdir -p ~/.config/crush && cp pmoves/configs/claws/crush-z890.json ~/.config/crush/crush.json
```

`Z_AI_API_KEY` must be present in the environment — Crush expands `$Z_AI_API_KEY` at load.
It comes from the machine-emitted secrets pipeline; do not inline a key into these files.

## Not yet automated

`make -C pmoves claw-deploy SCOPE=<node>` ships **OpenClaw** config only
(`base-openclaw.json` + `scopes/<scope>.json` → `/root/.openclaw/`). It does not know about
Crush. Installing these is a manual copy until that script grows a Crush stage — worth doing,
but it touches the deploy path and belongs in its own change.

## Costs are zeroed deliberately

`cost_per_1m_*` is `0` on every model here. The GLM lane is a **flat-rate coding plan**, not
per-token billing, and the Ollama lane is local. Zero is the honest value; a made-up per-token
figure would corrupt any spend reporting built on it later.
