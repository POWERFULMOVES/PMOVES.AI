# OmniVoice (voice.omnivoice) — Local Live Acceptance

OmniVoice is Apache-2.0, light, fleetwide — the voice foothold. No API key.

## Bring OmniVoice up (light)
Run `PMOVES-Creator/installs/OMNIVOICE-WEBUI-INSTALLER.bat` (installs the
`omnivoice` package + launches the demo at `http://127.0.0.1:8001`; models pull
from HF on first run). Confirm the page loads at :8001.

## Assert
```bat
set CREATOR_VOICE_TEST=1
PYTHONPATH=pmoves/services/creator-operator python -m pytest ^
  pmoves/services/creator-operator/tests/test_integration_voice.py -v
```
Acceptance = a live synth returns a real `.wav` (>1 KB) and the voice operator
assembles a valid audio operator-result.

**Live-verified 2026-06-10 (4090, OmniVoice 0.1.5, Torch 2.8.0+cu128):** gated test
PASSED — 24 kHz mono 16-bit WAV, ~3 s, peak≈16383 / rms≈2400 (real speech, audible).
The demo exposes **two** named gradio endpoints — there is no `/tts`:
- `/_design_fn(text, lang, ns, gs, dn, sp, du, pp, po, gender, age, pitch, whisper,
  accent, dialect) -> (audio_path, status)` — no reference audio (the default path).
- `/_clone_fn(text, lang, ref_aud, ref_text, instruct, ns, gs, dn, sp, du, pp, po)
  -> (audio_path, status)` — voice cloning from a reference audio.

`du` is Duration (seconds); `du<=0` = auto-estimate. `RealOmniVoiceClient.synthesize`
is wired to these (design by default, clone when `voice_ref` is set) and copies the
returned temp `.wav` into `out_dir`. Re-inspect with `gradio_client`'s
`Client(url).view_api(return_format='dict')` if a future OmniVoice release renames them.

## Production implementation (direct model API — not gradio)
The gradio demo + `RealOmniVoiceClient` is the **try-it / acceptance** path. For a
production voice server, load the model **once** and call `generate()` directly —
no gradio HTTP hop, no temp-file copy (per OmniVoice `docs/OmniVoice.ipynb`):
```python
import soundfile as sf, torch
from omnivoice import OmniVoice  # + OmniVoiceGenerationConfig for param bundles
model = OmniVoice.from_pretrained(
    "k2-fsa/OmniVoice", device_map="cuda:0", dtype=torch.float16,
    load_asr=True,  # loads Whisper so ref_text is OPTIONAL when cloning (auto-transcribe)
)
# Three native modes (== RealOmniVoiceClient's voice_ref / voice_design / neither):
audio = model.generate(text="...", ref_audio="ref.wav", ref_text=None, instruct="四川话")  # clone (+optional instruct stabiliser)
audio = model.generate(text="...", instruct="female, young adult, high pitch, british accent")  # design
audio = model.generate(text="...")  # auto voice (model picks)
sf.write("out.wav", audio[0], 24000)  # returns a batch; audio[0] = waveform @ 24 kHz
```
**instruct categories** (voice-design.md): gender(male/female) · age(child/teenager/
young adult/middle-aged/elderly) · pitch(very low…very high) · style(whisper) ·
english accent (american/british/…, English text only) · chinese dialect (四川话/…,
Chinese text only). Omit any you don't care about; case-insensitive; combine freely.

**Gradio short-name → documented param** (generation-parameters.md):
`ns`=num_step(32) · `gs`=guidance_scale(2.0) · `dn`=denoise(True) ·
`sp`=speed(1.0, >1 faster) · `du`=duration(None/0=auto, **overrides speed**) ·
`pp`=preprocess_prompt(True) · `po`=postprocess_output(True, trims trailing silence —
set False for exact `du`). Sampling: position_temperature(5.0)/class_temperature(0.0,
0=greedy/deterministic). Long-form: text auto-chunks at `audio_chunk_threshold`(30 s)
into ~`audio_chunk_duration`(15 s) segments → near-constant VRAM for arbitrary length.

**Gotchas** (tips.md): short clips (1–2 s) need a `ref_audio`; ref_audio+instruct
conflict → ref_audio wins; Min Nan / Hokkien input only via Tai-lo romanization.

**Custom-voice / eval seams** (examples/): fine-tune from `init_from_checkpoint=
"k2-fsa/OmniVoice"` on a JSONL manifest (`{id, audio_path, text, language_id?}`),
~5k steps @ LR 5e-5 (`examples/run_finetune.sh`, `config/train_config_finetune*.json`;
use the `_sdpa` variant if `flex_attention` is unsupported) — the custom-suit-voice
training path. Eval (WER / speaker-sim / UTMOS) via `pip install omnivoice[eval]` +
`examples/run_eval.sh`. Both are **later-slice seams**, not in the routing PR.

## Fleet / ROCm
voice.omnivoice routes fleetwide (needs:[voice]); NVIDIA nodes are confirmed.
Knuckles (AMD/ROCm) advertises `voice` but OmniVoice's CUDA-pinned installer needs
a ROCm torch swap — **TODO-validate seam** before routing live voice to knuckles.
