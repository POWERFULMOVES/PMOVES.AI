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
assembles a valid audio operator-result. If the gradio endpoint name differs from
`/tts`, adjust `RealOmniVoiceClient.synthesize`'s `api_name` (inspect the live app
via `gradio_client`'s `Client(...).view_api()`).

## Fleet / ROCm
voice.omnivoice routes fleetwide (needs:[voice]); NVIDIA nodes are confirmed.
Knuckles (AMD/ROCm) advertises `voice` but OmniVoice's CUDA-pinned installer needs
a ROCm torch swap — **TODO-validate seam** before routing live voice to knuckles.
