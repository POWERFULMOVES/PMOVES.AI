# Media Audio Service

The media-audio worker coordinates the end-to-end audio analysis flow.  It is
responsible for orchestrating Whisper-based transcription/alignment,
Pyannote-powered diarisation, and emotion/feature extraction before persisting
results into Supabase and emitting `analysis.audio.v1` envelopes over NATS.

## Environment variables

| Variable | Description |
| --- | --- |
| `MINIO_ENDPOINT` / `S3_ENDPOINT` | MinIO/S3 endpoint used to fetch media |
| `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY` | Credentials for MinIO/S3 |
| `MINIO_SECURE` | Set to `true` for HTTPS MinIO endpoints |
| `SUPABASE_URL`, `SUPABASE_KEY` | Required to persist segments/emotions |
| `NATS_URL` | Broker URL for `analysis.audio.v1` publication |
| `EMOTION_MODEL` | Hugging Face model for emotion classification |
| `SEA_LLM_MODEL` | Optional SeaLLMs audio model (takes precedence over `EMOTION_MODEL`) |
| `PYANNOTE_AUTH_TOKEN` | Hugging Face token for Pyannote diarisation |
| `FFMPEG_WHISPER_URL` | Optional URL to delegate WhisperX transcription to the `ffmpeg-whisper` service |
| `AUDIO_DEFAULT_NAMESPACE` | Default namespace when none supplied in requests |
| `WHISPER_DEVICE` | Override device detection (`cpu`/`cuda`) |
| `WHISPER_COMPUTE_TYPE` | Override WhisperX compute type (`int8`, `float16`, etc.) |

> **GPU builds**: the requirements ship CPU wheels by default for faster local
> testing. When targeting NVIDIA GPUs replace `torch`/`torchaudio` with the
> appropriate `+cu*` wheels from `download.pytorch.org`.

SeaLLM support is provided through the standard Hugging Face `transformers`
pipeline. Supply any published SeaLLM audio checkpoint (for example
`SeaLLMs/SeaVoice-7B`) via `SEA_LLM_MODEL` to activate it—no additional Python
package is required.

The companion `ffmpeg-whisper` service honours the same MinIO settings and adds
two additional variables:

| Variable | Description |
| --- | --- |
| `MEDIA_AUDIO_URL` | Base URL for the media-audio service (`http://media-audio:8082`) |
| `MEDIA_AUDIO_TIMEOUT` | Timeout (seconds) when forwarding transcripts |

## Local testing

Install dependencies and run the tests from the repository root:

```bash
pip install -r services/media-audio/requirements.txt pytest
pytest services/media-audio/tests -q
```

The test suite includes a fixture that demonstrates the orchestration contract
between the transcription and audio services, ensuring that transcripts are
merged with emotions/features before persistence and event emission.

