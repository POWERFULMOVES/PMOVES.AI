# Higgs Audio engine fails to initialize after upstream checkpoint update (`Padding_idx must be within num_embeddings`)

**Repo:** `SUP3RMASS1VE/Ultimate-TTS-Studio-SUP3R-Edition`
**Affected engine:** Higgs Audio (`higgs_audio_handler.py`)
**Hardware-agnostic:** Yes — CPU fallback fails with the same error, ruling out any CUDA/device cause.
**Related upstream:** [`boson-ai/higgs-audio#176`](https://github.com/boson-ai/higgs-audio/issues/176) (opened 2026-04-13; same root cause, manifests one step earlier at `HiggsAudioTokenizer.__init__`).

---

## Summary

After the `bosonai/higgs-audio-v2-generation-3B-base` HuggingFace checkpoint
was republished on **2026-04-04** in the new transformers-native format
(`architectures: ["HiggsAudioV2ForConditionalGeneration"]`, `model_type: "higgs_audio_v2"`,
flat config with no nested `text_config`), the vendored `higgs_audio/` model
code inside `Ultimate-TTS-Studio-SUP3R-Edition` can no longer construct the
model. It silently falls back to a default `LlamaConfig` (vocab_size=32000)
while still using `pad_token_id=128001` from the top-level config, which
violates the `padding_idx < num_embeddings` invariant on the embedding layer.

## Reproduction

1. Install and launch Ultimate-TTS-Studio-SUP3R-Edition via Pinokio.
2. In the Gradio UI, select the **Higgs Audio** engine and submit any text.
3. Observe the following in the console:

```
🎤 Initializing Higgs Audio engine on cuda...
❌ Failed to initialize Higgs Audio engine: Padding_idx must be within num_embeddings
🔄 Attempting CPU fallback...
❌ CPU fallback also failed: Padding_idx must be within num_embeddings
```

The error is **hardware-agnostic** — CPU fallback fails identically, so this
is not a CUDA/device issue. The model was initialized on an RTX 5090 (CUDA
12.4), but the same failure occurs on CPU-only machines per the traceback.

## Root cause

The HuggingFace repo `bosonai/higgs-audio-v2-generation-3B-base` was updated
in place on **2026-04-04** (`lastModified: 2026-04-04T19:47:40Z`, sha
`0ff4877`). The new `config.json` is flat — no nested `text_config`:

```json
{
  "architectures": ["HiggsAudioV2ForConditionalGeneration"],
  "model_type": "higgs_audio_v2",
  "vocab_size": 128256,
  "hidden_size": 3072,
  "pad_token_id": 128001,
  "audio_token_id": 128016,
  "audio_bos_token_id": 128013,
  ...
}
```

But the vendored `higgs_audio/model/configuration_higgs_audio.py` in this
repo still expects the legacy composition schema (`model_type: "higgs_audio"`,
nested `text_config` sub-object). In its `__init__`, when `text_config=None`
is encountered, it falls back to an **empty default Llama config**:

https://github.com/SUP3RMASS1VE/Ultimate-TTS-Studio-SUP3R-Edition/blob/main/higgs_audio/higgs_audio/model/configuration_higgs_audio.py#L168-L169

```python
elif text_config is None:
    text_config = CONFIG_MAPPING["llama"]()   # → LlamaConfig(vocab_size=32000, hidden_size=4096)
```

Later in the same `__init__` (line 239), it still assigns
`self.pad_token_id = 128001` from the top-level kwargs. Then in
`modeling_higgs_audio.py` line 900:

https://github.com/SUP3RMASS1VE/Ultimate-TTS-Studio-SUP3R-Edition/blob/main/higgs_audio/higgs_audio/model/modeling_higgs_audio.py#L889-L900

```python
self.padding_idx = config.pad_token_id                           # = 128001
self.vocab_size  = config.text_config.vocab_size                 # = 32000  (Llama default)
...
self.embed_tokens = nn.Embedding(
    self.vocab_size,                     #   32000
    config.text_config.hidden_size,      #    4096 (Llama default)
    self.padding_idx,                    #  128001  ← OUT OF RANGE
)
```

PyTorch raises `ValueError: Padding_idx must be within num_embeddings` in
`torch/nn/modules/sparse.py`. The CPU fallback path in
`higgs_audio_handler.py::initialize_engine` (lines 334-350) simply retries
the same construction, so it fails with the same error.

## Why this broke now

This is **not** a tokenizer drift / `resize_token_embeddings()` oversight
inside the vendored code — the vendored code was correct against the
**previous** version of the checkpoint. The HF repo was republished
~nine days before this report (2026-04-04) in a new single-file
`AutoModelForTextToWaveform` format. The vendored `higgs_audio/` subtree in
this repo has not been updated to match; `git log app/higgs_audio_handler.py`
upstream shows zero commits.

The same root cause is reported upstream at `boson-ai/higgs-audio`:

- https://github.com/boson-ai/higgs-audio/issues/176 — `HiggsAudioTokenizer.__init__() got an unexpected keyword argument 'acoustic_model_config'` (2026-04-13)

That issue trips one step earlier — in the tokenizer load — because the
`boson_multimodal` snapshot is older than the vendored `higgs_audio/` subtree
in SUP3R, which gets past the tokenizer step and then dies at the embedding
constructor instead. Both issues share the same underlying checkpoint-format
mismatch.

## Suggested fixes (any one of these unblocks Higgs)

**Option A — pin to pre-2026-04-04 checkpoint (fast, minimal blast radius).**
In `app/higgs_audio_handler.py` around line 261, set a pinned revision on the
snapshot download calls in `_ensure_local_higgs_snapshots` (line 436-442):

```python
model_local = snapshot_download(
    repo_id=self.model_path,
    revision="<sha-of-last-working-commit-before-2026-04-04>",  # pin
    ...
)
```

The last-known-good sha can be found via
`huggingface_hub.list_repo_commits("bosonai/higgs-audio-v2-generation-3B-base")`
and selecting the most recent commit dated before 2026-04-04.

**Option B — upgrade to the new `transformers`-native loader.** The new
checkpoint advertises `auto_model: "AutoModelForTextToWaveform"` in its
`transformersInfo`. Replace the vendored `HiggsAudioServeEngine` call
(line 324-328 of `higgs_audio_handler.py`) with:

```python
from transformers import AutoProcessor, AutoModelForTextToWaveform
processor = AutoProcessor.from_pretrained(local_model_path)
model = AutoModelForTextToWaveform.from_pretrained(
    local_model_path,
    torch_dtype=torch.bfloat16,
    device_map=self.device,
)
```

and retire the vendored `higgs_audio/` subtree entirely. This requires
`transformers>=5.3.0.dev0` (per the checkpoint's `transformers_version`
field) and an adapter around the existing prompt-building logic.

**Option C — sync the vendored subtree.** Pull the latest
`boson-ai/higgs-audio` copy into `app/higgs_audio/` and wait for upstream
issue #176 to land a fix. Lowest control, highest dependency on upstream.

## Workaround (for users hitting this now)

Ultimate-TTS-Studio-SUP3R-Edition ships **13 other engines** that do not
share this code path. Any of the following produce comparable quality
without patching anything:

| Higgs use case | Alternative in this repo |
|---|---|
| Expressive narration | VoxCPM (44.1 kHz) |
| Short-reference voice cloning | F5-TTS (24 kHz, 8.5x real-time) |
| Multi-language emotional speech | Fish Speech S2 Pro (44.1 kHz, 13 languages) |

Simply select a different engine in the Gradio UI until the Higgs handler
is updated.

## Exact file:line references

- **Error origin:** `app/higgs_audio/higgs_audio/model/modeling_higgs_audio.py:900`
- **Root-cause fallback:** `app/higgs_audio/higgs_audio/model/configuration_higgs_audio.py:168-169`
- **Handler entry point:** `app/higgs_audio_handler.py:312-351` (`initialize_engine`)
- **Snapshot download (fix location A):** `app/higgs_audio_handler.py:436-442`

## Environment

- OS: Windows 11, Python 3.10 (Pinokio-managed venv)
- GPU: NVIDIA RTX 5090, CUDA 12.4
- torch: (per Pinokio install profile)
- Reproduces on CPU fallback — not hardware-specific
- Upstream model checkpoint sha `0ff4877` (lastModified 2026-04-04)

---

*Filed from the PMOVES.AI production voice lane after verification that no
existing issue in this repo references `Padding_idx`, `num_embeddings`, or
the 2026-04-04 checkpoint break.*
