# AGNOTE: DGX Spark Integration

## Node: pmoves-dgx-spark
- **Hardware**: Gigabyte GB10 Grace-Blackwell workstation
- **Memory**: 128GB unified memory
- **Role**: GPU inference via Ollama
- **Access**: Tailscale tag:gpu, port 11434
- **Provider**: ollama_spark in Agent Zero model_providers.yaml
- **Default Model**: gemma4:31b
- **NATS Subjects**: mesh.gpu.* (7 streams defined in pmoves/nats/mesh_gpu_streams.yaml)
- **TAC Tree**: pmoves/configs/tac_trees/dgx-spark.tac.yaml (278 lines, 6 phases)

## Status
- ✅ Tailscale ACL rules configured (exit node consume, DGX Spark inference, GPU→PMOVES mesh)
- ✅ Network inventory registered (5 nodes added)
- ✅ Makefile include added (nvidia-dgx-spark.mk)
- ✅ Ollama Spark provider configured (http://pmoves-dgx-spark:11434)
- ✅ PMOVES MAX preset created (GLM-5-turbo + GLM-5.1 + HuggingFace embed)
- ✅ JetStream streams defined (7 mesh.gpu.* streams)
- ✅ Flare model namespace updated (dgx-spark added to gemma-4-e2b, e4b, 31b)

## Remaining
- ⏳ NATS JetStream streams not deployed (defined only)
- ⏳ Ollama installation verification on GB10
- ⏳ Model auto-pull on boot configuration

Added: 2026-04-17
