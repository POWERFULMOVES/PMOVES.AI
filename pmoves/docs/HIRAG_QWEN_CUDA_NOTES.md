# Hi‑RAG v2 • Qwen Reranker (CUDA Torch)
_Last updated: 2025-08-29_

Use a CUDA‑enabled Torch build for **Qwen/Qwen3‑Reranker‑4B** in the v2 gateway.

## Build
```
docker compose build hi-rag-gateway-v2   --build-arg TORCH_CUDA_VERSION=cu121   --build-arg TORCH_SKIP_CUDA=0
```

The Dockerfile installs Torch/TorchVision/Torchaudio using NVIDIA wheels. To skip (CPU‑only), set `TORCH_SKIP_CUDA=1`.

## Run (GPU)
- Ensure Docker uses the NVIDIA runtime and grant GPUs to the container.
- Example Compose override:
```yaml
services:
  hi-rag-gateway-v2:
    deploy:
      resources:
        reservations:
          devices:
            - capabilities: ["gpu"]
```
Or run with `--gpus all` via CLI.

## Env
```
RERANK_PROVIDER=qwen
QWEN_RERANK_MODEL=Qwen/Qwen3-Reranker-4B
```
