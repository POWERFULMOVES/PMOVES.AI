# Higgs Audio: Upstream Embedding Mismatch Bug

**Status:** Root cause identified (Session 12 follow-up research)
**Severity:** Non-blocking (13 other engines available)
**Affects:** `SUP3RMASS1VE/Ultimate-TTS-Studio-SUP3R-Edition` — Higgs Audio handler
**First observed:** Session 11 (2026-04-13)
**Root cause isolated:** Session 12 (2026-04-14)
**Related upstream issue:** [`boson-ai/higgs-audio#176`](https://github.com/boson-ai/higgs-audio/issues/176) — same root cause, manifests one step earlier at `HiggsAudioTokenizer.__init__`
**Filing-ready issue body:** [`higgs-upstream-embedding-bug-draft.md`](higgs-upstream-embedding-bug-draft.md)

---

## TL;DR

The HuggingFace repo `bosonai/higgs-audio-v2-generation-3B-base` was **republished on 2026-04-04** in a new single-file format. The vendored `higgs_audio/` subtree inside `SUP3RMASS1VE/Ultimate-TTS-Studio-SUP3R-Edition` has not been updated to match — when it hits the new flat config, it silently falls through to an empty Llama default (vocab_size=32000) while still using `pad_token_id=128001` from the top-level config, which crashes `torch.nn.Embedding` with `padding_idx (128001) >= num_embeddings (32000)`.

This is **not** a `resize_token_embeddings()` oversight — the vendored code was correct against the **previous** version of the checkpoint. The bug is a checkpoint-format drift that only appeared when the HF repo was republished nine days before this report.

## Error path (precise)

1. `app/higgs_audio/higgs_audio/model/configuration_higgs_audio.py:168-169`
   ```python
   elif text_config is None:
       text_config = CONFIG_MAPPING["llama"]()   # → LlamaConfig(vocab_size=32000)
   ```
2. `app/higgs_audio/higgs_audio/model/modeling_higgs_audio.py:900`
   ```python
   self.embed_tokens = nn.Embedding(
       self.vocab_size,                     #   32000 (Llama default, wrong)
       config.text_config.hidden_size,      #    4096
       self.padding_idx,                    #  128001 (from top-level pad_token_id)
   )
   ```
3. PyTorch raises `ValueError: Padding_idx must be within num_embeddings` in `torch/nn/modules/sparse.py`.

CPU fallback (`app/higgs_audio_handler.py:334-350`) simply retries the same construction → same failure. Hardware-agnostic.

## Three concrete fixes (any one unblocks Higgs)

| Option | Location | Effort | Risk |
|--------|----------|--------|------|
| **A — Pin to pre-2026-04-04 checkpoint** | `app/higgs_audio_handler.py:436-442` (add `revision=<sha>` to `snapshot_download`) | Low | Model frozen at old version |
| **B — Upgrade to `AutoModelForTextToWaveform`** | `app/higgs_audio_handler.py:324-328` (replace vendored loader with new transformers-native API) | Medium | Requires `transformers>=5.3.0.dev0` + adapter for prompt-building logic |
| **C — Sync vendored subtree** | `app/higgs_audio/` (pull latest `boson-ai/higgs-audio`) | Low-Medium | Gated on upstream fix for boson-ai/higgs-audio#176 |

**Recommendation:** Option A (pin to pre-2026-04-04 revision) for fastest unblock. Use `huggingface_hub.list_repo_commits("bosonai/higgs-audio-v2-generation-3B-base")` to find the most recent commit dated before 2026-04-04.

## Reproducer

1. Install and launch Ultimate-TTS-Studio-SUP3R-Edition via Pinokio: `pterm run ultimate-tts-studio-sup3r-edition.pinokio.git`
2. In the Gradio UI at `http://localhost:7860`, select the **Higgs Audio** engine and submit any text
3. Observe:
   ```
   🎤 Initializing Higgs Audio engine on cuda...
   ❌ Failed to initialize Higgs Audio engine: Padding_idx must be within num_embeddings
   🔄 Attempting CPU fallback...
   ❌ CPU fallback also failed: Padding_idx must be within num_embeddings
   ```

Equivalent reproducer via PMOVES production path:
```bash
curl -X POST http://localhost:8055/v1/voice/synthesize \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello world","provider":"ultimate_tts","engine":"higgs"}'
```
The flute-gateway surfaces the upstream traceback as an `UltimateTTSError` → HTTP 502.

## Workaround (operational, available now)

Until upstream fix lands, **skip Higgs Audio**. Three alternative engines cover the same use cases with comparable or better quality:

| Higgs use case | PMOVES alternative | Quality |
|----------------|---------------------|---------|
| Expressive narration | **VoxCPM** (44.1 kHz) | Highest fidelity; verified in Session 11 |
| Voice cloning from short reference | **F5-TTS** (24 kHz) | 8.5x real-time, best cloning verified |
| Multi-language emotional speech | **Fish Speech S2 Pro** (44.1 kHz) | 13 languages, user-verified UI |

The PMOVES production path defaults to these engines; Higgs is only reachable when explicitly requested via `engine=higgs`.

## Upstream filing status

**Related existing issue (one step earlier in the same stack):**
- [`boson-ai/higgs-audio#176`](https://github.com/boson-ai/higgs-audio/issues/176) — `HiggsAudioTokenizer.__init__() got an unexpected keyword argument 'acoustic_model_config'` (opened 2026-04-13)
  - This is in the upstream `boson-ai/higgs-audio` repo, not the SUP3R fork
  - Same checkpoint-format mismatch; trips earlier because the `boson_multimodal` snapshot is older than the vendored subtree in SUP3R
  - Both issues share the same underlying root cause

**New issue to file at SUP3RMASS1VE/Ultimate-TTS-Studio-SUP3R-Edition** (user action):
- **Filing-ready body:** `higgs-upstream-embedding-bug-draft.md` in this same directory — copy-paste into a new GitHub issue
- Verified: no existing issue in the SUP3R repo references `Padding_idx`, `num_embeddings`, or the 2026-04-04 checkpoint break
- Title: `Higgs Audio engine fails to initialize after upstream checkpoint update (Padding_idx must be within num_embeddings)`

## Cross-references

- TAC tree: `pmoves/docs/TAC/TAC_VOICE_PRODUCTION.md` Phase 4 (Known Bugs)
- Engine inventory: `pmoves/configs/tts-engine-capabilities.yaml`
- Production test harness: `pmoves/tools/test_all_tts_engines.py`
- Filing-ready issue body: `higgs-upstream-embedding-bug-draft.md`
- Precise file:line references:
  - Config fallthrough: `app/higgs_audio/higgs_audio/model/configuration_higgs_audio.py:168-169`
  - Embedding crash site: `app/higgs_audio/higgs_audio/model/modeling_higgs_audio.py:900`
  - Handler entry point: `app/higgs_audio_handler.py:312-351`
  - Snapshot download (fix A location): `app/higgs_audio_handler.py:436-442`
