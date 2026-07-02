# Cloud-Hybrid HERMES + Agent Zero Provider Standup Implementation Plan (rev 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up node-aware HERMES Agent + Agent Zero on Knuckles routed through TensorZero — cloud coding plans orchestrate, local worker siblings are selected dynamically via HuggingFace APIs + Supabase model-registry (no hardcoded local model IDs), loaded by gpu-orchestrator, served by vLLM/llama.cpp/Ollama, and trail-signed via shape-worker capsules.

**Architecture:** TensorZero (:3030 host / tensorzero-gateway:3000 in-network) routes everything. Static config carries only cloud provider endpoints (API contracts) and routing-function shells. Worker model rows are **registry-managed**: `model-registry` (:8110, Supabase-backed) is the catalog; candidates enter only via `POST /api/model-candidates` with trusted agent identity + CHIT `signed_trail_ref`; `gpu-orchestrator` (:8200) loads/unloads with VRAM tracking; `vllm-orchestrator` registers running vLLM instances into TZ dynamically; a shape-worker sidecar emits `content.lexicon.shaped.v1` / `mesh.shape.handshake.v1` capsules from worker inference results. A sync tool splices registry-generated `[models.*]` blocks into a marker-delimited section of `tensorzero.toml`; **bootstrap lane aliases route to cloud parents**, so workers degrade to their cloud siblings until local candidates are promoted.

**Tech Stack:** TensorZero TOML, `pmoves/config/provider_catalog.yaml` + `provider_cascade.py`, model-registry FastAPI (+`hf_client.py`, `migrate_tensorzero.py`), gpu-orchestrator, vllm-orchestrator (`tensorzero.py`), spark-shape-worker, HuggingFace plugin/MCP (`hf` CLI, model search, `hf-mem`), Hermes Agent CLI, docker compose profiles (`agents`, `orchestration`), pytest, Pinokio launcher.

## Global Constraints

- **No hardcoded local model IDs in committed config.** Local worker model rows exist only in Supabase (via model-registry API) and in the marker-delimited *generated* section of `tensorzero.toml` (refreshed by the sync tool, reviewed as an artifact). Cloud provider endpoints, env var names, and function shells are legitimate static config.
- Canonical env vars per `provider_catalog.yaml`: `Z_AI_API_KEY`, `MOONSHOT_API_KEY`, `ALIBABA_PRO_CODING_PLAN`. New: `KILOCODE_API_KEY`, `OLLAMA_API_KEY`, `HF_TOKEN`. Legacy names are aliases only.
- Model candidates REQUIRE CHIT signing: `POST /api/model-candidates` rejects entries without `signed_trail_ref` + trusted `agent_id`. Use the `pmoves-chit-sign` skill; identity `B850-CLAUDE`.
- Every PR < 400 lines (generated TOML section counts as artifact diff — keep bootstrap minimal); commit format `<type>(<scope>): <subject>`.
- NEVER print/commit secret values. `pmoves/env.tier-llm` is zero-access. `~/.hermes/**` secrets never enter git. NATS URLs in committed files use env placeholders.
- Tests: `cd pmoves && python -m pytest tests/ -q` green before each PR.
- Claim before edits / release after, in `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md`.
- TZ endpoint from host: `http://127.0.0.1:3030/openai/v1`; model syntax `tensorzero::function_name::<fn>`.
- llama.cpp/vLLM local serving binds **:8090** (8080 is Agent Zero's; existing `llamacpp_rocm` blocks all carry weight 0.0 — moving them is safe and required).
- Spec deviations documented in spec rev 3: no `pmoves_embed` function (reuse `gemma_embed_local`); Alibaba canonical env is `ALIBABA_PRO_CODING_PLAN`.

---

## PR 1 — feat(providers): cloud tier + registry-managed worker lanes — branch `feat/provider-cloud-hybrid-tier`

### Task 1: Claim the lane and cut the branch

**Files:**
- Modify: `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md`

- [ ] **Step 1:** `grep -n "CLAIM" pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md | tail -5` to learn the row format.
- [ ] **Step 2:** Append, matching that format:

```
CLAIM :: B850-CLAUDE :: feat/provider-cloud-hybrid-tier + feat/hermes-knuckles-standup + feat/pinokio-model-selector :: HERMES/A0 cloud-hybrid standup, dynamic model plane (TAC phase_3_b850_knuckles) :: 2026-07-02
```

- [ ] **Step 3:**

```bash
git add pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md
git commit -m "docs(agnote): B850-CLAUDE claims cloud-hybrid provider standup lane"
git checkout -b feat/provider-cloud-hybrid-tier
```

### Task 2: Add kilocode, ollama_cloud, huggingface to provider_catalog.yaml

**Files:**
- Modify: `pmoves/config/provider_catalog.yaml` (append after `ollama_spark:`)

**Interfaces:**
- Produces: provider slugs `kilocode`, `ollama_cloud`, `huggingface`; `tz_model_key`s `chat_kilocode`, `chat_ollama_cloud_default`, `chat_hf_router` used by Task 3.

- [ ] **Step 1: Verify live default model IDs (cloud plans are API contracts — pick from the live list, never memory)**

```bash
curl -s https://kilocode.ai/api/openrouter/models | python3 -c "import json,sys; print([m['id'] for m in json.load(sys.stdin).get('data',[])][:20])" || echo "list-unavailable: use activation-time verify"
curl -s https://router.huggingface.co/v1/models | python3 -c "import json,sys; print([m['id'] for m in json.load(sys.stdin).get('data',[])][:20])" || echo "list-unavailable: use activation-time verify"
curl -s -H "Authorization: Bearer $OLLAMA_API_KEY" https://ollama.com/v1/models 2>/dev/null | head -c 400 || echo "needs key — verify at activation"
```

Record the chosen coding-capable id per provider in the catalog `model_name` fields below (placeholders shown as `<verified-*>` MUST be replaced with a live id from these lists before commit).

- [ ] **Step 2: Append three provider entries** (schema identical to existing entries; weights 0.0, cascade-activated):

```yaml
  kilocode:
    env_var: KILOCODE_API_KEY
    key_pattern: ".*"
    api_base: "https://kilocode.ai/api/openrouter"
    tz_type: openai
    tier: llm
    coding_stack: kilocode_plan
    models:
      chat_kilocode:
        model_name: "<verified-kilocode-coding-id>"
        tz_model_key: chat_kilocode
        serves:
          - function: pmoves_orchestrator_coding
            variant_name: cloud_kilocode
            role: secondary
            weight: 0.0
        vram_mb: 0

  ollama_cloud:
    env_var: OLLAMA_API_KEY
    key_pattern: ".*"
    api_base: "https://ollama.com/v1"
    tz_type: openai
    tier: llm
    models:
      chat_ollama_cloud_default:
        model_name: "<verified-ollama-cloud-id>"
        tz_model_key: chat_ollama_cloud_default
        serves:
          - function: pmoves_orchestrator_chat
            variant_name: cloud_ollama_default
            role: primary
            weight: 0.0
          - function: pmoves_orchestrator_coding
            variant_name: cloud_ollama_default
            role: fallback
            weight: 0.0
        vram_mb: 0

  huggingface:
    env_var: HF_TOKEN
    key_pattern: "^hf_"
    api_base: "https://router.huggingface.co/v1"
    tz_type: openai
    tier: llm
    models:
      chat_hf_router:
        model_name: "<verified-hf-router-coding-id>"
        tz_model_key: chat_hf_router
        serves:
          - function: pmoves_orchestrator_coding
            variant_name: cloud_hf_router
            role: fallback
            weight: 0.0
        vram_mb: 0
```

- [ ] **Step 3:** `python3 -c "import yaml; yaml.safe_load(open('pmoves/config/provider_catalog.yaml')); print('OK')"` → `OK`. Confirm no `<verified-` strings remain: `grep -c "verified-" pmoves/config/provider_catalog.yaml` → 0.
- [ ] **Step 4:**

```bash
git add pmoves/config/provider_catalog.yaml
git commit -m "feat(providers): add kilocode, ollama_cloud, huggingface providers (cascade-activated)"
```

### Task 3: TensorZero — cloud models, function shells, registry-managed section, :8090 fix

**Files:**
- Modify: `pmoves/tensorzero/config/tensorzero.toml`

**Interfaces:**
- Consumes: `tz_model_key`s from Task 2; existing `chat_zai_glm51`, `chat_moonshot`, `chat_alibaba_qwen`.
- Produces: functions `pmoves_orchestrator_coding`, `pmoves_orchestrator_chat`, `pmoves_worker_glm`, `pmoves_worker_qwen`, `pmoves_worker_hermes`, `pmoves_worker_kimi`; lane-alias models `registry_worker_glm`, `registry_worker_qwen`, `registry_worker_hermes`, `registry_worker_kimi` inside the REGISTRY-MANAGED markers (bootstrap = cloud parents). Task 4's sync tool owns everything between the markers from then on.

- [ ] **Step 1: Port fix**

```bash
sed -i 's|http://pmoves-9850x3d-r9700:8080/v1|http://pmoves-9850x3d-r9700:8090/v1|g' pmoves/tensorzero/config/tensorzero.toml
```

Add above the first `llamacpp_rocm` block: `# Port 8090: 8080 is reserved for Agent Zero fleet-wide (HERMES_AGENT_INTEGRATION.md).`

- [ ] **Step 2: Cloud model blocks** (model_name values = the verified ids committed in Task 2; keep the two files in lockstep):

```toml
[models.chat_kilocode]
routing = ["kilocode_primary"]

[models.chat_kilocode.providers.kilocode_primary]
type = "openai"
api_base = "https://kilocode.ai/api/openrouter"
model_name = "<same-verified-id-as-catalog>"
api_key_location = "env::KILOCODE_API_KEY"

[models.chat_ollama_cloud_default]
routing = ["ollama_cloud_primary"]

[models.chat_ollama_cloud_default.providers.ollama_cloud_primary]
type = "openai"
api_base = "https://ollama.com/v1"
model_name = "<same-verified-id-as-catalog>"
api_key_location = "env::OLLAMA_API_KEY"

[models.chat_hf_router]
routing = ["hf_router_primary"]

[models.chat_hf_router.providers.hf_router_primary]
type = "openai"
api_base = "https://router.huggingface.co/v1"
model_name = "<same-verified-id-as-catalog>"
api_key_location = "env::HF_TOKEN"
```

- [ ] **Step 3: Registry-managed section with bootstrap lane aliases** (workers degrade to cloud parents until the registry promotes local candidates — no local model IDs committed):

```toml
# ============================================================================
# BEGIN REGISTRY-MANAGED MODELS (generated — do not hand-edit)
# Source of truth: model-registry :8110 (Supabase pmoves_core.*).
# Refresh: python pmoves/tools/tz_registry_sync.py
# Bootstrap state: lane aliases route to same-family CLOUD PARENTS until
# signed local candidates are promoted through /api/model-candidates.
# ============================================================================

[models.registry_worker_glm]
routing = ["bootstrap_parent"]

[models.registry_worker_glm.providers.bootstrap_parent]
type = "openai"
api_base = "https://api.z.ai/api/coding/paas/v4"
model_name = "glm-5.1"
api_key_location = "env::Z_AI_API_KEY"

[models.registry_worker_qwen]
routing = ["bootstrap_parent"]

[models.registry_worker_qwen.providers.bootstrap_parent]
type = "openai"
api_base = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
model_name = "qwen3-coder-plus"
api_key_location = "env::ALIBABA_PRO_CODING_PLAN"

[models.registry_worker_hermes]
routing = ["bootstrap_parent"]

[models.registry_worker_hermes.providers.bootstrap_parent]
type = "openai"
api_base = "https://openrouter.ai/api/v1"
model_name = "nousresearch/hermes-3-llama-3.1-405b"
api_key_location = "env::OPENROUTER_API_KEY"

[models.registry_worker_kimi]
routing = ["bootstrap_parent"]

[models.registry_worker_kimi.providers.bootstrap_parent]
type = "openai"
api_base = "https://api.moonshot.ai/v1"
model_name = "moonshot-v1-32k"
api_key_location = "env::MOONSHOT_API_KEY"

# ============================================================================
# END REGISTRY-MANAGED MODELS
# ============================================================================
```

(The hermes bootstrap id: verify against `curl -s https://openrouter.ai/api/v1/models | grep -o '"nousresearch/[^"]*"' | head` and use a live id.)

- [ ] **Step 4: Function shells** — orchestrator variants reference static cloud models; worker variants reference ONLY lane aliases:

```toml
[functions.pmoves_orchestrator_coding]
type = "chat"

[functions.pmoves_orchestrator_coding.variants.cloud_zai_glm51]
type = "chat_completion"
model = "chat_zai_glm51"
temperature = 0.2
max_tokens = 8192
weight = 1.0

[functions.pmoves_orchestrator_coding.variants.cloud_kimi]
type = "chat_completion"
model = "chat_moonshot"
temperature = 0.2
max_tokens = 8192
weight = 0.0

[functions.pmoves_orchestrator_coding.variants.cloud_alibaba]
type = "chat_completion"
model = "chat_alibaba_qwen"
temperature = 0.2
max_tokens = 8192
weight = 0.0

[functions.pmoves_orchestrator_coding.variants.cloud_kilocode]
type = "chat_completion"
model = "chat_kilocode"
temperature = 0.2
max_tokens = 8192
weight = 0.0

[functions.pmoves_orchestrator_coding.variants.cloud_ollama_default]
type = "chat_completion"
model = "chat_ollama_cloud_default"
temperature = 0.2
max_tokens = 8192
weight = 0.0

[functions.pmoves_orchestrator_coding.variants.cloud_hf_router]
type = "chat_completion"
model = "chat_hf_router"
temperature = 0.2
max_tokens = 8192
weight = 0.0

[functions.pmoves_orchestrator_chat]
type = "chat"

[functions.pmoves_orchestrator_chat.variants.cloud_ollama_default]
type = "chat_completion"
model = "chat_ollama_cloud_default"
temperature = 0.7
max_tokens = 8192
weight = 1.0

[functions.pmoves_orchestrator_chat.variants.cloud_zai_glm51]
type = "chat_completion"
model = "chat_zai_glm51"
temperature = 0.7
max_tokens = 8192
weight = 0.0

[functions.pmoves_worker_glm]
type = "chat"

[functions.pmoves_worker_glm.variants.lane]
type = "chat_completion"
model = "registry_worker_glm"
temperature = 0.2
max_tokens = 8192
weight = 1.0

[functions.pmoves_worker_qwen]
type = "chat"

[functions.pmoves_worker_qwen.variants.lane]
type = "chat_completion"
model = "registry_worker_qwen"
temperature = 0.2
max_tokens = 8192
weight = 1.0

[functions.pmoves_worker_hermes]
type = "chat"

[functions.pmoves_worker_hermes.variants.lane]
type = "chat_completion"
model = "registry_worker_hermes"
temperature = 0.7
max_tokens = 8192
weight = 1.0

[functions.pmoves_worker_kimi]
type = "chat"

[functions.pmoves_worker_kimi.variants.lane]
type = "chat_completion"
model = "registry_worker_kimi"
temperature = 0.2
max_tokens = 8192
weight = 1.0
```

- [ ] **Step 5:** `python3 -c "import tomllib; tomllib.load(open('pmoves/tensorzero/config/tensorzero.toml','rb')); print('OK')"` → `OK`
- [ ] **Step 6:**

```bash
git add pmoves/tensorzero/config/tensorzero.toml
git commit -m "feat(tensorzero): orchestrator/worker function shells + registry-managed lane aliases; llamacpp_rocm to :8090"
```

### Task 4: Registry→TZ sync tool (TDD)

**Files:**
- Create: `pmoves/tools/tz_registry_sync.py`
- Create: `pmoves/tests/test_tz_registry_sync.py`

**Interfaces:**
- Consumes: `GET http://127.0.0.1:8110/api/tensorzero/config` (full TOML from Supabase); markers from Task 3.
- Produces: `sync_registry_section(static_toml_text: str, registry_toml_text: str) -> str` — replaces content between `BEGIN/END REGISTRY-MANAGED MODELS` markers with `[models.*]` blocks from the registry TOML whose keys start with `registry_`; CLI `python pmoves/tools/tz_registry_sync.py [--registry-url URL] [--dry-run]`.

- [ ] **Step 1: Write the failing test**

```python
"""tz_registry_sync: splice registry-generated model blocks into tensorzero.toml."""
import tomllib

from tools.tz_registry_sync import sync_registry_section

STATIC = """
[models.chat_static]
routing = ["p"]

[models.chat_static.providers.p]
type = "openai"
api_base = "https://example.com/v1"
model_name = "m"
api_key_location = "none"

# BEGIN REGISTRY-MANAGED MODELS (generated - do not hand-edit)
[models.registry_worker_glm]
routing = ["bootstrap_parent"]

[models.registry_worker_glm.providers.bootstrap_parent]
type = "openai"
api_base = "https://old.example/v1"
model_name = "old"
api_key_location = "none"
# END REGISTRY-MANAGED MODELS

[functions.f]
type = "chat"
"""

REGISTRY = """
[models.registry_worker_glm]
routing = ["ollama_local"]

[models.registry_worker_glm.providers.ollama_local]
type = "openai"
api_base = "http://pmoves-ollama:11434/v1"
model_name = "selected-by-registry"
api_key_location = "none"

[models.not_registry_prefixed]
routing = ["x"]
"""


def test_replaces_marker_section_with_registry_models():
    out = sync_registry_section(STATIC, REGISTRY)
    parsed = tomllib.loads(out)
    glm = parsed["models"]["registry_worker_glm"]["providers"]["ollama_local"]
    assert glm["model_name"] == "selected-by-registry"
    assert "chat_static" in parsed["models"]          # outside markers untouched
    assert "not_registry_prefixed" not in parsed["models"]  # only registry_* spliced
    assert "f" in parsed["functions"]


def test_idempotent():
    once = sync_registry_section(STATIC, REGISTRY)
    twice = sync_registry_section(once, REGISTRY)
    assert once == twice


def test_missing_markers_raises():
    import pytest
    with pytest.raises(ValueError):
        sync_registry_section("[models.x]\nrouting=[]\n", REGISTRY)
```

- [ ] **Step 2:** `cd pmoves && python -m pytest tests/test_tz_registry_sync.py -v` → FAIL (module missing).
- [ ] **Step 3: Implement `pmoves/tools/tz_registry_sync.py`**

```python
#!/usr/bin/env python3
"""Splice model-registry-generated [models.*] blocks into tensorzero.toml.

The static file owns everything outside the marker pair; the registry owns
everything inside. Only model tables whose key starts with ``registry_`` are
spliced, so the registry cannot clobber static cloud provider blocks.

CLI:
    python pmoves/tools/tz_registry_sync.py [--registry-url http://127.0.0.1:8110] [--dry-run]
"""
from __future__ import annotations

import argparse
import re
import sys
import urllib.request
from pathlib import Path

PMOVES = Path(__file__).resolve().parents[1]
TZ_TOML = PMOVES / "tensorzero" / "config" / "tensorzero.toml"
BEGIN_RE = re.compile(r"^# BEGIN REGISTRY-MANAGED MODELS.*$", re.M)
END_RE = re.compile(r"^# END REGISTRY-MANAGED MODELS.*$", re.M)
TABLE_RE = re.compile(r"^\[((?:models)\.registry_[A-Za-z0-9_.]*)\]", re.M)


def _extract_registry_tables(registry_toml_text: str) -> str:
    """Return only [models.registry_*] tables (with their provider subtables)."""
    lines = registry_toml_text.splitlines()
    out: list[str] = []
    keep = False
    for line in lines:
        header = re.match(r"^\[([A-Za-z0-9_.]+)\]", line)
        if header:
            key = header.group(1)
            keep = key.startswith("models.registry_")
        if keep:
            out.append(line)
    return "\n".join(out).strip() + ("\n" if out else "")


def sync_registry_section(static_toml_text: str, registry_toml_text: str) -> str:
    begin = BEGIN_RE.search(static_toml_text)
    end = END_RE.search(static_toml_text)
    if not begin or not end or end.start() < begin.end():
        raise ValueError("REGISTRY-MANAGED MODELS markers missing or malformed")
    body = _extract_registry_tables(registry_toml_text)
    return (
        static_toml_text[: begin.end()]
        + "\n"
        + body
        + static_toml_text[end.start() :]
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--registry-url", default="http://127.0.0.1:8110")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with urllib.request.urlopen(f"{args.registry_url}/api/tensorzero/config", timeout=15) as resp:
        registry_text = resp.read().decode("utf-8")
    static_text = TZ_TOML.read_text(encoding="utf-8")
    merged = sync_registry_section(static_text, registry_text)
    if args.dry_run:
        sys.stdout.write(merged)
        return 0
    TZ_TOML.write_text(merged, encoding="utf-8")
    print(f"synced registry-managed models into {TZ_TOML}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4:** `cd pmoves && python -m pytest tests/test_tz_registry_sync.py -v` → 3 PASSED.
- [ ] **Step 5:**

```bash
git add pmoves/tools/tz_registry_sync.py pmoves/tests/test_tz_registry_sync.py
git commit -m "feat(tensorzero): registry-to-TOML sync tool for marker-delimited model section"
```

### Task 5: Function↔model reference gate (TDD)

**Files:**
- Create: `pmoves/tests/test_tz_function_model_refs.py`

- [ ] **Step 1: Write the test**

```python
"""Every TZ function variant must reference a defined model.

Worker functions (pmoves_worker_*) may ONLY reference registry_ lane aliases —
this is the no-hardcoded-local-models gate.
"""
import tomllib
from pathlib import Path

PMOVES = Path(__file__).resolve().parents[1]
TZ_TOML = PMOVES / "tensorzero" / "config" / "tensorzero.toml"


def _tz():
    with open(TZ_TOML, "rb") as fh:
        return tomllib.load(fh)


def test_all_variant_model_refs_resolve():
    tz = _tz()
    defined = set(tz.get("models", {})) | set(tz.get("embedding_models", {}))
    dangling = [
        (fn, var, v["model"])
        for fn, f in tz.get("functions", {}).items()
        for var, v in (f.get("variants") or {}).items()
        if "model" in v and v["model"] not in defined
    ]
    assert not dangling, f"variants reference undefined models: {dangling}"


def test_worker_functions_use_registry_lanes_only():
    tz = _tz()
    offenders = [
        (fn, var, v["model"])
        for fn, f in tz.get("functions", {}).items()
        if fn.startswith("pmoves_worker_")
        for var, v in (f.get("variants") or {}).items()
        if not str(v.get("model", "")).startswith("registry_")
    ]
    assert not offenders, (
        "worker variants must reference registry_ lane aliases (Supabase-managed), "
        f"got: {offenders}"
    )
```

- [ ] **Step 2:** `cd pmoves && python -m pytest tests/test_tz_function_model_refs.py -v` → 2 PASSED against Task 3 output. Teeth-check: temporarily change one worker variant model to `chat_moonshot`, expect FAIL, revert.
- [ ] **Step 3:** Full suite `cd pmoves && python -m pytest tests/ -q` → green.
- [ ] **Step 4:**

```bash
git add pmoves/tests/test_tz_function_model_refs.py
git commit -m "test(tensorzero): function-model reference gate; workers must use registry lanes"
```

### Task 6: Env plumbing — tier example, tier manifest, canonical aliases

**Files:**
- Modify: `pmoves/env.tier-llm.example` (after `MOONSHOT_API_KEY=`)
- Modify: `pmoves/tools/fix_tier_manifest.py` (env.tier-llm dict, ~line 25)
- Modify: `pmoves/bootstrap/registry.json` (`canonical_aliases`)

- [ ] **Step 1: env example additions**

```bash
# Kilo Code coding plan — https://kilocode.ai (OpenRouter-compatible)
KILOCODE_API_KEY=

# Ollama Pro (cloud) — https://ollama.com/settings/keys
OLLAMA_API_KEY=

# HuggingFace router/hub token — https://huggingface.co/settings/tokens
HF_TOKEN=

# Alibaba coding plan (canonical per provider_catalog.yaml; DASHSCOPE_API_KEY is the legacy alias)
ALIBABA_PRO_CODING_PLAN=
```

- [ ] **Step 2: tier manifest** — check existing first (`grep -n "MOONSHOT\|Z_AI\|HF_TOKEN" pmoves/tools/fix_tier_manifest.py`), then add missing rows alphabetically:

```python
    "ALIBABA_PRO_CODING_PLAN": ["env.tier-llm"],
    "DASHSCOPE_API_KEY": ["env.tier-llm"],
    "HF_TOKEN": ["env.tier-llm"],
    "KILOCODE_API_KEY": ["env.tier-llm"],
    "MOONSHOT_API_KEY": ["env.tier-llm"],
    "OLLAMA_API_KEY": ["env.tier-llm"],
    "Z_AI_API_KEY": ["env.tier-llm"],
```

- [ ] **Step 3: canonical aliases** — inspect shape (`python3 -c "import json; print(json.dumps(json.load(open('pmoves/bootstrap/registry.json'))['canonical_aliases'], indent=2)[:800])"`) then append matching entries for: `KIMI_API_KEY→MOONSHOT_API_KEY`, `ALIBABA_API_KEY→ALIBABA_PRO_CODING_PLAN`, `DASHSCOPE_API_KEY→ALIBABA_PRO_CODING_PLAN`, `ZAI_API_KEY→Z_AI_API_KEY`, `HUGGINGFACE_TOKEN→HF_TOKEN`.
- [ ] **Step 4:** JSON parse check + `make -C pmoves naming-drift-check || true` (fix any NEW findings this change causes).
- [ ] **Step 5:**

```bash
git add pmoves/env.tier-llm.example pmoves/tools/fix_tier_manifest.py pmoves/bootstrap/registry.json
git commit -m "feat(providers): env slots + tier manifest + canonical aliases (kilocode/ollama-cloud/hf/alibaba)"
```

### Task 7: Open PR 1

- [ ] **Step 1:**

```bash
git push -u origin feat/provider-cloud-hybrid-tier
gh pr create --title "feat(providers): cloud-hybrid tier — kilocode/ollama-cloud/hf + registry-managed worker lanes" --body "$(cat <<'EOF'
## Summary
- Spec rev 3 (docs/superpowers/specs/2026-07-02-hermes-agent-zero-provider-standup-design.md): cloud coding plans orchestrate; local workers are Supabase/registry-managed — NO hardcoded local model IDs
- provider_catalog.yaml: +kilocode, +ollama_cloud, +huggingface (weight 0.0, cascade-activated)
- tensorzero.toml: orchestrator/worker function shells; REGISTRY-MANAGED marker section with cloud-parent bootstrap lanes; llamacpp_rocm 8080→8090 (Agent Zero owns 8080)
- tz_registry_sync.py: splices model-registry (:8110) generated blocks into the marker section
- Gates: function→model reference test + workers-must-use-registry-lanes test
- Env slots + tier manifest + canonical aliases

## Test plan
- pytest tests/test_tz_registry_sync.py tests/test_tz_function_model_refs.py -v
- Full: python -m pytest tests/ -q

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 2:** CI green; report PR URL.

---

## PR 2 — Knuckles live standup: dynamic model plane + HERMES + Agent Zero — branch `feat/hermes-knuckles-standup`

### Task 8: Bring up the model plane + TZ restart + key fill-list

- [ ] **Step 1: Secrets + orchestration services**

```bash
make -C pmoves secrets-funnel
docker compose -f pmoves/docker-compose.yml --profile orchestration up -d model-registry gpu-orchestrator
docker compose -f pmoves/docker-compose.yml restart tensorzero-gateway
curl -sf http://127.0.0.1:8110/healthz && curl -sf http://127.0.0.1:8200/healthz 2>/dev/null || curl -sf http://127.0.0.1:8200/status
curl -sf http://127.0.0.1:3030/health
```

Expected: registry + gpu-orchestrator + TZ healthy. If registry migrations are missing in the live Supabase, apply `pmoves/supabase/migrations/20260522000000_model_fitness_candidates.sql` + `20260527060000_tighten_model_fitness_rls.sql` via the repo's migration path (`make -C pmoves db-migrate` or documented equivalent) — data tier is live on this node (S1 schema applied 2026-07-02).

- [ ] **Step 2: Key fill-list WITHOUT reading values**

```bash
for k in Z_AI_API_KEY MOONSHOT_API_KEY ALIBABA_PRO_CODING_PLAN KILOCODE_API_KEY OLLAMA_API_KEY HF_TOKEN MINIMAX_API_KEY OPENROUTER_API_KEY; do
  docker compose -f pmoves/docker-compose.yml exec -T tensorzero-gateway sh -c "[ -n \"\$$k\" ] && echo \"$k: SET\" || echo \"$k: EMPTY\""
done
```

Report EMPTY rows to operator (GH/CHIT source update → `make -C pmoves secrets-funnel`).

- [ ] **Step 3: Orchestrator function smokes** (skip EMPTY-key variants):

```bash
curl -s http://127.0.0.1:3030/openai/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"tensorzero::function_name::pmoves_orchestrator_coding","messages":[{"role":"user","content":"Reply with the single word: ready"}],"max_tokens":10}' | python3 -m json.tool | head -20
```

Repeat for `pmoves_orchestrator_chat` and each `pmoves_worker_*` (bootstrap lanes → cloud parents).

### Task 9: HF research → signed candidates → fitness → load (the dynamic sibling pipeline)

**No model IDs come from this plan.** Selection uses live APIs, per family lane (glm, qwen, hermes, kimi):

- [ ] **Step 1: Research via HuggingFace plugin/MCP** — for each lane, use the `huggingface-skills:huggingface-best` + `hf-cli` skills (hf MCP search) with criteria: same model family as the cloud parent, instruct/coder variant, ROCm-servable (safetensors for vLLM, or GGUF for llama.cpp), fits 64GB total VRAM (verify with `huggingface-skills:hf-mem` — `hf-mem <repo-id>`), permissive/open license, recent (≤12 months). Record per lane: chosen repo id, quant/format, est. VRAM, serving backend (vllm | llamacpp | ollama), evidence links.
- [ ] **Step 2: Sign + register each candidate**

```bash
# Per lane: sign the selection trail first (produces signed_trail_ref)
# via Skill: pmoves-chit-sign (payload = lane, hf_id, criteria, evidence)
curl -s -X POST http://127.0.0.1:8110/api/model-candidates -H 'Content-Type: application/json' -d '{
  "agent_id": "B850-CLAUDE",
  "hf_id": "<researched-repo-id>",
  "intended_lane": "worker_glm",
  "signed_trail_ref": "<ref-from-chit-sign>",
  "notes": "cloud-hybrid worker sibling; criteria: family-match, hf-mem fit, ROCm backend"
}' | python3 -m json.tool
```

(Adjust field names to `ModelCandidateRecord` in `pmoves/services/model-registry/main.py` — read the model class before posting.) Then enrich: `curl -s -X POST http://127.0.0.1:8110/api/models/<id>/enrich-hf`.

- [ ] **Step 3: Load via gpu-orchestrator** (it owns backend choice through `ollama_client`/`vllm_client`):

```bash
curl -s -X POST http://127.0.0.1:8200/models/load -H 'Content-Type: application/json' \
  -d '{"provider": "<vllm|ollama>", "model_id": "<researched-id>"}' | python3 -m json.tool
curl -s http://127.0.0.1:8200/models/loaded | python3 -m json.tool
```

(Read `LoadModelRequest` in `pmoves/services/gpu-orchestrator/api/routes.py` for exact fields first.) For vLLM lanes, `vllm-orchestrator`'s `register_model_with_tensorzero()` registers the running instance into TZ.

- [ ] **Step 4: Fitness smoke per loaded candidate** — one coding prompt + latency/tokens-per-sec measurement → `POST /api/model-fitness` with score + evidence.
- [ ] **Step 5: Promote lanes** — ensure registry marks the candidate active for its lane so `/api/tensorzero/config` emits `[models.registry_worker_<lane>]` pointing at the local endpoint; then:

```bash
python pmoves/tools/tz_registry_sync.py
docker compose -f pmoves/docker-compose.yml restart tensorzero-gateway
cd pmoves && python -m pytest tests/test_tz_function_model_refs.py -q   # still green post-sync
```

Re-run the `pmoves_worker_*` smokes — responses should now come from local endpoints (verify via gpu-orchestrator `/models/loaded` + TZ logs). Any lane without a viable local candidate stays on its cloud-parent bootstrap — record it honestly.

- [ ] **Step 6: Shape-worker sidecar on Knuckles** — start `pmoves/services/spark-shape-worker` (compose service `spark-shape-worker` with this node's NATS env) and observe one `mesh.shape.handshake.v1` or `content.lexicon.shaped.v1` emission after a worker inference:

```bash
docker compose -f pmoves/docker-compose.yml up -d spark-shape-worker
docker run --rm --network pmoves_pmoves_bus natsio/nats-box:latest \
  sh -c 'nats --server "$NATS_URL" sub "mesh.shape.handshake.v1" --count 1 --timeout 60s' | head -5
```

If the worker's subscribed inference-result subjects don't yet carry TZ worker traffic, record GAP with the exact subject names from `spark-shape-worker/main.py` — do not fake the handshake.

### Task 10: HERMES update + pmoves-hermes-knuckles profile

Live files only (`~/.hermes/profiles/pmoves-hermes-knuckles/`, never committed).

- [ ] **Step 1:** `hermes update && hermes --version && hermes doctor` (currently v0.15.1, 20 commits behind).
- [ ] **Step 2:** `hermes profile create pmoves-hermes-knuckles && hermes profile use pmoves-hermes-knuckles`
- [ ] **Step 3:** Merge into the profile `config.yaml` (schema: `providers:` keyed map — fields `name`, `base_url`, `api_key`/`key_env`, `api_mode`, `default_model`, `models`, `context_length`):

```yaml
model:
  default: "tensorzero::function_name::pmoves_orchestrator_coding"
  provider: tensorzero
providers:
  tensorzero:
    name: tensorzero
    base_url: "http://127.0.0.1:3030/openai/v1"
    api_key: "none"
    api_mode: chat_completions
    default_model: "tensorzero::function_name::pmoves_orchestrator_coding"
    models:
      - "tensorzero::function_name::pmoves_orchestrator_coding"
      - "tensorzero::function_name::pmoves_orchestrator_chat"
      - "tensorzero::function_name::pmoves_worker_glm"
      - "tensorzero::function_name::pmoves_worker_qwen"
      - "tensorzero::function_name::pmoves_worker_hermes"
      - "tensorzero::function_name::pmoves_worker_kimi"
    context_length: 128000
delegation:
  model: "tensorzero::function_name::pmoves_worker_hermes"
  provider: tensorzero
  max_concurrent_children: 2
  max_iterations: 50
toolsets:
  enabled: [web, terminal, file, messaging, cronjob, code_execution, skills, memory]
gateway:
  port: 7700
security:
  redact_secrets: true
```

- [ ] **Step 4:** `hermes doctor` clean; `hermes chat -q "Reply with the single word: orchestrated"` answers via TZ (confirm in TZ logs).
- [ ] **Step 5:** Delegation smoke: `hermes chat -q "Use delegate_task to have a subagent reply with the single word: sibling"` → runs on `pmoves_worker_hermes`.
- [ ] **Step 6:** Populate profile `.env` (only `NATS_URL` needed — TZ holds provider keys); verify gitignore covers `.hermes` patterns (add `**/.hermes/` if missing — commit in Task 12).

### Task 11: Gateway + NATS + Agent Zero

- [ ] **Step 1:** `hermes --profile pmoves-hermes-knuckles gateway run &` then `curl -sf http://localhost:7700/api/health`.
- [ ] **Step 2:** NATS observation: `nats sub "hermes.>" --count 1 --timeout 30s` via nats-box on `pmoves_pmoves_bus` (env `$NATS_URL`). If this Hermes build has no native NATS publisher: record GAP "NATS bridge = TAC Phase 4 item" — do not fake.
- [ ] **Step 3:** `make -C pmoves up-agents` → `curl -sf http://127.0.0.1:8080/healthz` (A0 already points at `tensorzero::function_name::agent_zero`; no rewiring).
- [ ] **Step 4:** A0 round-trip via `agents:status` + `agents:execute` skills ("Reply with the single word: zero-online"); confirm TZ log shows the inference.

### Task 12: Repo updates, TAC flips, AGNOTE — commit PR 2

**Files:**
- Modify: `pmoves/config/profiles/hermes/b850.yaml` — model/delegation → TZ functions (mirror Task 10 yaml; keep NATS/toolsets/rocm sections; NO local model IDs — lane functions only)
- Modify: `pmoves/config/profiles/hermes/spark.yaml` — same TZ-first pattern
- Modify: `pmoves/configs/tac_trees/node-hermes-agent.tac.yaml` — `node_b850` → done; `phase_3_b850_knuckles` → DONE; spark note "config ready, node offline 2026-07-02"
- Modify: `pmoves/docs/AGENTS/HERMES_AGENT_INTEGRATION.md` — provider mapping table → cloud-hybrid tiers + canonical env names + dynamic model plane (registry/gpu-orch/vllm/shape-worker)
- Modify: `pmoves/docs/AGENTS/AGNOTE4482.md` — audit record "Cloud-Hybrid Provider Standup — Knuckles (2026-07-02)": work performed, candidate lanes with chosen HF ids + fitness scores (as evidence, quoted from Supabase — the DB stays canonical), key fill-list, GPU/CPU + gfx1201 findings, GAPs, ACK `B850-CLAUDE`

- [ ] **Step 1:** Apply the five edits.
- [ ] **Step 2:** `cd pmoves && python -m pytest tests/ -q` green.
- [ ] **Step 3:**

```bash
git checkout -b feat/hermes-knuckles-standup
git add pmoves/config/profiles/hermes/b850.yaml pmoves/config/profiles/hermes/spark.yaml
git commit -m "feat(hermes-profile): b850+spark v2 — TZ-first, registry-lane workers, no pinned models"
git add pmoves/configs/tac_trees/node-hermes-agent.tac.yaml
git commit -m "feat(hermes-tac): phase_3_b850_knuckles done; spark config-ready"
git add pmoves/docs/AGENTS/HERMES_AGENT_INTEGRATION.md pmoves/docs/AGENTS/AGNOTE4482.md
git commit -m "docs(hermes-docs): dynamic model plane + Knuckles standup audit record"
git push -u origin feat/hermes-knuckles-standup
gh pr create --base main --title "feat(hermes): Knuckles live standup — dynamic model plane, TZ-first profiles" --body "Stacked on feat/provider-cloud-hybrid-tier. Candidates live in Supabase (signed trails); evidence in AGNOTE audit record. 🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

---

## PR 3 — Pinokio model-selector launcher + SPARK runbook — branch `feat/pinokio-model-selector`

### Task 13: Pinokio launcher — local model selection driving the registry APIs

**Files:**
- Create: `pmoves/integrations/pinokio/pmoves-model-selector/{pinokio.json,pinokio.js,install.js,start.js,select-model.js,reset.js,update.js,README.md}`
- Live: `ln -sfn <repo>/pmoves/integrations/pinokio/pmoves-model-selector ~/pinokio/api/pmoves-model-selector`

**MANDATORY pre-work (CLAUDE.md Pinokio workflow):** load `.claude/PINOKIO_LAUNCHER_GUIDE.md`; `PINOKIO_HOME=/home/pmoves-knuckles/pinokio` (verified from `~/.pinokio/config.json`); example lock-in `prototype/system/examples/mochi/start.js`; URL capture via `on: [{event: "/(http:\\/\\/[0-9.:]+)/", done: true}]` + `local.set {url: "{{input.event[1]}}"}`.

**Behavior (no hardcoded models — the launcher is a UI over the APIs):**
- `select-model.js`: `net` GET `http://127.0.0.1:8110/api/models` + `http://127.0.0.1:8200/models` → present via `input` picker → `net` POST `http://127.0.0.1:8200/models/load` with the picked id → `notify` result. Unload path mirrors with `/models/unload/{provider}/{model_id}`.
- `start.js`: for the GGUF lane, launch `llama-server` (built by `install.js` from the gfx1201 fork `tlee933/llama.cpp-rdna4-gfx1201`, `HIP_VISIBLE_DEVICES=0,1`, `--port 8090 --tensor-split 0.5,0.5`) against a model path returned by the registry (`filepicker` over `models/` as fallback); capture URL per the mandated pattern.
- `install.js`: clone + `cmake -B build -DGGML_HIP=ON -DAMDGPU_TARGETS=gfx1201` + build; no model downloads (models arrive via registry/gpu-orchestrator; `hf.download` step exists but takes repo id from `input`, never a default id).
- README: what it does, the API contract (registry :8110, gpu-orchestrator :8200, llama-server :8090 → TZ `llamacpp_rocm`), curl/Python/JS examples. Note the intentional fixed port 8090 (TZ config pins it — exception to `{{port}}` documented).

- [ ] **Step 1:** Author the 8 files following the guide + example (exit-checklist confirmations recorded in README's "Launcher conformance" section).
- [ ] **Step 2:** Symlink + smoke: install → start → `curl -s http://127.0.0.1:8090/v1/models`; select-model round-trip visible in `curl -s http://127.0.0.1:8200/models/loaded`.
- [ ] **Step 3:**

```bash
git checkout -b feat/pinokio-model-selector
git add pmoves/integrations/pinokio/pmoves-model-selector/
git commit -m "feat(pinokio): model-selector launcher — registry/gpu-orchestrator UI + gfx1201 llama-server lane"
```

### Task 14: SPARK apply runbook (+ live apply if node returns)

**Files:**
- Create: `pmoves/docs/runbooks/SPARK_HERMES_APPLY.md`

- [ ] **Step 1:** Probe: `tailscale status | grep -w pmoves-spark` + `ssh -o ConnectTimeout=5 pmoves-spark 'echo up'`. If up → execute runbook live and record evidence in its "Applied" section; else ship "Pending apply".
- [ ] **Step 2:** Runbook steps: (1) hermes install + update; (2) profile `pmoves-hermes-spark` from `spark.yaml`; (3) secrets funnel on SPARK checkout; (4) **candidate research for SPARK lanes via the same registry pipeline** (its 128GB unified memory changes hf-mem fit — 70B+ lanes) — no pinned ids; (5) gpu-orchestrator/vllm load + `ollama_spark` TZ provider goes live automatically once Ollama serves; (6) shape-worker sidecar (its native role); (7) gateway health + verification checklist mirroring Tasks 8–11.
- [ ] **Step 3:** RELEASE the claim + PR:

```bash
git add pmoves/docs/runbooks/SPARK_HERMES_APPLY.md pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md
git commit -m "docs(hermes-docs): SPARK apply runbook; release B850-CLAUDE standup lane"
git push -u origin feat/pinokio-model-selector
gh pr create --base main --title "feat(pinokio)+docs(spark): model-selector launcher + SPARK apply runbook" --body "Stacked on feat/hermes-knuckles-standup. 🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

### Task 15: Signoff + operator handoff

- [ ] **Step 1:** Tick verified items in `AGNOTE4482_SIGNOFF_CHECKLIST.md` HERMES section (add section if absent). Only what was actually verified; GAPs stay unticked with notes.
- [ ] **Step 2:** Final report: PR links, key fill-list, per-lane candidate outcomes (Supabase ids + fitness scores), gfx1201/backend findings, shape-worker handshake status, SPARK applied-or-pending, operator next commands (GH secret names + `make -C pmoves secrets-funnel`).
