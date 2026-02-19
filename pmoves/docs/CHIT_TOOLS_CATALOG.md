# CHIT Tools Catalog

> **Part of the [PMOVES.AI Integration Layer](INTEGRATIONS_OVERVIEW.md)** | Category: CHIT & Geometry

This catalog documents all CHIT-related Python tools in `pmoves/tools/`. Each tool participates in some part of the CGP (CHIT Geometry Packet) lifecycle: encoding, decoding, security, spectral filtering, event mapping, or multi-agent consensus.

For protocol documentation, see the [CHIT Documentation Suite](PMOVESCHIT/README.md).

---

## Secret Encoding & Decoding

### `chit_encode_secrets.py`

Encode environment secrets from an `.env` file into a CHIT Geometry Packet (CGP) JSON. Each secret becomes a 3D anchor point via SHA-256 hashing.

```bash
python -m pmoves.tools.chit_encode_secrets \
  --env-file env.shared \
  --out ~/.config/pmoves/chit/env.cgp.json \
  [--keys ANTHROPIC_API_KEY OPENAI_API_KEY] \
  [--namespace pmoves.secrets] \
  [--passphrase <pass>]
```

| Field | Description |
|-------|-------------|
| **Input** | Key=value `.env` file |
| **Output** | Hex-encoded, HMAC-signed CGP JSON (`chit.cgp.v0.2`) |
| **Make target** | `make -C pmoves chit-export` |
| **Pipeline step** | Step 3 of secrets funnel |

---

### `chit_decode_secrets.py`

Decode a CHIT Geometry Packet back into plaintext environment secrets. Supports selective key extraction.

```bash
python -m pmoves.tools.chit_decode_secrets \
  --cgp ~/.config/pmoves/chit/env.cgp.json \
  [--out env.decrypted] \
  [--keys ANTHROPIC_API_KEY]
```

| Field | Description |
|-------|-------------|
| **Input** | CGP JSON file |
| **Output** | Plaintext env file or stdout |
| **CLI skill** | `/chit:decode` (for CGP packets, not just secrets) |

---

### `chit_manifest_sync.py`

Sync v1 CHIT secrets manifest from the richer v2 source. Normalizes secret labels across upstream naming variations (e.g., `SUPABASE_SERVICE_KEY` from `SUPABASE_SERVICE_ROLE_KEY`).

| Field | Description |
|-------|-------------|
| **Input** | `secrets_manifest_v2.yaml` (98 entries) |
| **Output** | `secrets_manifest.yaml` (v1 format) |
| **Make target** | `make -C pmoves chit-manifest-sync` |
| **Pipeline step** | Step 2 of secrets funnel |

---

## Security & Validation

### `chit_security.py`

Core CHIT cryptographic operations library. Not a CLI tool --- imported by other tools.

| Operation | Method |
|-----------|--------|
| **Signing** | HMAC-SHA256 packet signing |
| **Key derivation** | PBKDF2 from passphrase |
| **Encryption** | AES-GCM anchor encryption/decryption |
| **Verification** | Signature integrity checks |

---

### `chit_security_validator.py`

Validates incoming CHIT Geometry Packets for security and schema compliance. Supports CGP versions v0.1, v0.2, and v1.0.

| Field | Description |
|-------|-------------|
| **Validation** | Schema version, signature verification, anchor format |
| **Integration** | HTTP client for Hi-RAG geometry events endpoint |
| **Models** | Pydantic models for CGP validation |

---

### `chit_credential_demo.py`

Full credential lifecycle demonstration: encode, verify, rotate, and report.

```bash
# Encode secrets into CGP
python -m pmoves.tools.chit_credential_demo encode \
  --env-file env.shared --out env.cgp.json [--keys ...]

# Verify CGP integrity
python -m pmoves.tools.chit_credential_demo verify \
  --cgp env.cgp.json [--passphrase ...]

# Rotate specific keys
python -m pmoves.tools.chit_credential_demo rotate \
  --cgp env.cgp.json --keys KEY1 KEY2 [--env-file ...]

# Scan for exposed credentials
python -m pmoves.tools.chit_credential_demo report \
  --path <dir-or-file>
```

| Field | Description |
|-------|-------------|
| **Input** | Env files, CGP files, directories |
| **Output** | CGP JSON, verification results, redaction report (JSON) |
| **Scans for** | API keys, tokens, passwords --- reports redaction status |

---

## Codebook & Manifest Generation

### `chit_codebook_gen.py`

Generate CHIT codebook JSONL from source JSONL for structured dataset creation.

```bash
python pmoves/tools/chit_codebook_gen.py \
  <input.jsonl> <output.jsonl> [--max 1000]
```

| Field | Description |
|-------|-------------|
| **Input** | JSONL with `text`/`title`/`summary` fields |
| **Output** | Structured JSONL with normalized `text` field |
| **Use case** | Training data preparation for CHIT models |

---

### `generate_chit_v2.py`

Generate `secrets_manifest_v2.yaml` with tiered secret mappings and GitHub/Docker targets. Run once to bootstrap the manifest.

| Field | Description |
|-------|-------------|
| **Output** | `secrets_manifest_v2.yaml` with 98 entries |
| **Tiers** | data, api, llm, media, agent, worker |
| **Targets** | Env files, GitHub secrets, Docker secrets |

---

## Decoders

### `chit/chit_decoder.py`

Decode CHIT Geometry Packets to original text content. Supports exact (lossless) recovery when embedded text is present, and geometry-only (lossy/retrieval) mode via FAISS similarity search against a corpus.

```bash
python -m pmoves.tools.chit.chit_decoder \
  --cgp packet.json \
  --corpus corpus.jsonl \
  [--mode auto|exact|geometric]
```

| Field | Description |
|-------|-------------|
| **Input** | CGP JSON + optional corpus JSONL |
| **Output** | Recovered text content |
| **Modes** | `auto` (try exact, fall back to geometric), `exact`, `geometric` |
| **Optional** | T5 learning-based decoder (future) |

---

### `chit/chit_decoder_mm.py`

Decode CHIT Geometry Packets to multimodal content (images via CLIP, optional audio via CLAP). Maps CGP geometry to the nearest media files by embedding similarity.

```bash
python -m pmoves.tools.chit.chit_decoder_mm \
  --cgp packet.json \
  --image-dir ./images \
  [--audio-dir ./audio]
```

| Field | Description |
|-------|-------------|
| **Input** | CGP JSON + image directory (+ optional audio directory) |
| **Output** | Matched media filenames with similarity scores |
| **Models** | CLIP (images), CLAP (audio) |

---

## Events & Consensus

### `events_to_cgp.py`

Map summary events (health metrics, finance data) to CHIT Geometry CGPs. Optionally POST to Hi-RAG gateway's geometry endpoint.

```bash
python -m pmoves.tools.events_to_cgp \
  --file event.json \
  [--topic override] \
  [--gateway http://localhost:8086] \
  [--post] [--print]
```

| Field | Description |
|-------|-------------|
| **Input** | Event JSON (health, finance, or custom) |
| **Output** | CGP JSON (printed or POSTed to `/geometry/event`) |
| **Mappers** | `cgp_mappers` module for domain-specific encoding |

---

### `maca_tensorzero.py`

MACA (Multi-Agent Consensus Alignment) integration with TensorZero gateway. Enables LLM-backed consensus voting on geometry packets across multiple agents.

| Field | Description |
|-------|-------------|
| **Class** | `MACATensorZeroConsensus` |
| **API** | Async HTTP to TensorZero `/v1/chat/completions` |
| **Output** | Structured consensus results with voting metadata |
| **Use case** | Agent agreement on CGP interpretation |

---

## Spectral Filtering

### `zeta_filter.py`

Zeta-inspired spectral filter using the first N Riemann zeta zeros. Applies scale-invariant weighting (`1/log(gamma_n)` decay) to CGP spectrum arrays.

| Field | Description |
|-------|-------------|
| **Class** | `ZetaInspiredFilter(num_zeros=10)` |
| **Method** | `.filter_spectrum(spectrum)` --- weighted output |
| **Analysis** | `.analyze_spectrum()` --- entropy, dominance detection |
| **Foundation** | [Integrating Math into PMOVES.AI](PMOVESCHIT/Integrating%20Math%20into%20PMOVES.AI.md) |

---

## Registry & Tagging (Non-CHIT, Integration Layer)

### `skill_tag_injector.py`

Inject `PMOVES.AI-CONTEXT-TAGS` blocks into submodule `CLAUDE.md` files from the skill registry.

```bash
python -m pmoves.tools.skill_tag_injector \
  [--registry pmoves/configs/submodule_skill_registry.json]
```

| Field | Description |
|-------|-------------|
| **Input** | `submodule_skill_registry.json` |
| **Output** | Updated `CLAUDE.md` files with context-tag blocks |
| **Tags** | Skills, context files, domain tags, tier labels |

---

### `skill_registry_validate.py`

Validate the submodule-skill registry completeness against `.gitmodules` and skill files.

```bash
python -m pmoves.tools.skill_registry_validate \
  [--registry pmoves/configs/submodule_skill_registry.json] \
  [--strict]
```

| Field | Description |
|-------|-------------|
| **Checks** | Registry entries match `.gitmodules` submodules |
| **Validates** | Skill file references exist, no orphaned entries |
| **Make target** | `make -C pmoves skill-registry-validate` |

---

## Tool-to-Pipeline Mapping

| Tool | Secrets Funnel Step | CLI Skill | Make Target |
|------|-------------------|-----------|-------------|
| `chit_encode_secrets.py` | Step 3 (export) | `/chit:encode` | `chit-export` |
| `chit_decode_secrets.py` | --- | `/chit:decode` | --- |
| `chit_manifest_sync.py` | Step 2 (sync) | --- | `chit-manifest-sync` |
| `secrets_sync.py` | Step 4 (generate) | `/deploy:secrets-funnel` | `secrets-funnel-sync` |
| `secrets_hardening_audit.py` | Step 5 (audit) | `/deploy:audit-layers` | `secrets-audit` |
| `chit_security_validator.py` | --- | --- | --- |
| `chit_credential_demo.py` | --- | --- | --- |
| `events_to_cgp.py` | --- | `/chit:bus` | --- |
| `smoke_gpu.py` | --- | `/gpu:status` | `smoke-gpu` |
| `skill_registry_validate.py` | --- | --- | `skill-registry-validate` |
| `skill_tag_injector.py` | --- | --- | --- |

---

## Related Documentation

- [Secrets Pipeline Reference](SECRETS_PIPELINE_REFERENCE.md) --- how these tools compose into the 6-step funnel
- [GPU Orchestration Guide](GPU_ORCHESTRATION_GUIDE.md) --- GPU-specific tools and make targets
- [CHIT Documentation Suite](PMOVESCHIT/README.md) --- protocol specs, quickstart, API reference
- [Integration Layer Overview](INTEGRATIONS_OVERVIEW.md) --- master entry point for all integration docs
