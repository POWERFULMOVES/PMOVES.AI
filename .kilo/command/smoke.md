Run PMOVES smoke tests for the 5090 GPU node.

## Implementation

Run the core smoke harness:

```bash
make -C pmoves smoke
```

For GPU strict validation (rerank assertions):

```bash
GPU_SMOKE_STRICT=true make -C pmoves smoke-gpu
```

For model readiness check:

```bash
make -C pmoves model-readiness
```

Full verification (smoke + health + GPU):

```bash
make -C pmoves smoke && GPU_SMOKE_STRICT=true make -C pmoves smoke-gpu && make -C pmoves model-readiness
```

## GPU-Specific Checks

```bash
nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader
ollama list
curl -sf http://localhost:8087/hirag/admin/stats | python3 -m json.tool 2>/dev/null | head -20
```

## Notes

- GPU services: hi-rag-gateway-v2-gpu (:8087), ffmpeg-whisper (:8078), media-video (:8079)
- If GPU smoke fails, check CUDA: `nvidia-smi` and Docker GPU runtime
- Capture evidence for AGNOTE4482 handoff
