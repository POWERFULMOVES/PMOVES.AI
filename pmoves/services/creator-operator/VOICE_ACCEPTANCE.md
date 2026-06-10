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

## Fleet / ROCm
voice.omnivoice routes fleetwide (needs:[voice]); NVIDIA nodes are confirmed.
Knuckles (AMD/ROCm) advertises `voice` but OmniVoice's CUDA-pinned installer needs
a ROCm torch swap — **TODO-validate seam** before routing live voice to knuckles.
