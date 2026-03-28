# vLLM Model Serving

Manage vLLM inference servers on GPU nodes.

## Usage

/vllm start <model> — Start a vLLM server for a model
/vllm status — Show running vLLM servers
/vllm stop <model> — Stop a vLLM server

## Implementation

Start vLLM server:
```bash
docker compose --profile vllm -f pmoves/docker-compose/vllm-models.yml up -d $1
```

Check status:
```bash
docker compose -f pmoves/docker-compose/vllm-models.yml ps
curl -sf http://localhost:8100/v1/models | python3 -m json.tool   # vllm-qwen-7b
curl -sf http://localhost:8130/v1/models | python3 -m json.tool   # vllm-qwen-32b
```

## Available Models

| Profile | Models | Host Port | GPU RAM |
|---------|--------|-----------|---------|
| medium | Qwen 2.5 7B/14B | 8100 | 8-16GB |
| large | Qwen 2.5 32B (TP=2) | 8130 | 24GB+ |
| specialized | Qwen Coder 7B, Qwen 3 VL 8B | 8100 | 8-16GB |

## Notes

- vLLM provides OpenAI-compatible API (host ports 8100/8130, container port 8000)
- Use PMOVES.Flare namespace: pmoves/qwen-3-coder-32b
- TensorZero can route to vLLM endpoints
- GPU orchestrator manages model lifecycle via NATS mesh.gpu.*
