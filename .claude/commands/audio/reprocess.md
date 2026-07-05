# Audio Reprocess

Reprocess audio tracks on the 4090 GPU node — Whisper transcription + enhancement pipeline.

## Usage

```
/audio:reprocess <action> [track_id | --batch | --status]
```

## Actions

| Action | Description |
|--------|-------------|
| `single <track_id>` | Reprocess a single audio track |
| `--batch` | Reprocess all pending tracks |
| `--status` | Check reprocess queue status |

## Pipeline

1. **Whisper Transcription** — `openai-whisper` on 4090 GPU (model: `large-v3`)
2. **Enhancement** — noise reduction + speaker diarization + normalization
3. **Publish** — result to NATS `media.audio.reprocess.complete.v1`

## Examples

### Reprocess single track
```
/audio:reprocess single track_abc123
```
```bash
curl -X POST http://localhost:8080/api/v1/audio/reprocess \
  -H "Content-Type: application/json" \
  -d '{"track_id": "track_abc123", "model": "large-v3"}'
```

### Batch reprocess
```
/audio:reprocess --batch
```

### Status check
```
/audio:reprocess --status
```

## 4090 Troubleshooting

- **GPU OOM**: Reduce batch size or use `model: medium` instead of `large-v3`
- **Model loading**: Ensure Whisper model is cached at `/models/whisper/`
- **CUDA errors**: Verify `nvidia-smi` shows GPU available and driver matches CUDA version
- **FFmpeg missing**: Install via `apt-get install ffmpeg`

## NATS Subjects

| Subject | Direction | Description |
|---------|-----------|-------------|
| `media.audio.reprocess.request.v1` | Subscribe | Incoming reprocess requests |
| `media.audio.reprocess.complete.v1` | Publish | Completed reprocess results |
| `media.audio.reprocess.failed.v1` | Publish | Failed reprocess (for retry queue) |
