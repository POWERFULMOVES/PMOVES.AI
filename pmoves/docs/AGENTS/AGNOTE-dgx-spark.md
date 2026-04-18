# AGNOTE: DGX Spark Integration

## Node: pmoves-dgx-spark
- **Hardware**: Gigabyte GB10 Grace-Blackwell workstation
- **Memory**: 128GB unified memory
- **Role**: GPU inference via Ollama
- **Access**: Tailscale tag:gpu, port 11434
- **Provider**: ollama_spark in Agent Zero model_providers.yaml
- **Default Model**: gemma4:31b
- **NATS Subjects**: mesh.gpu.* (5 streams defined in pmoves/nats/mesh_gpu_streams.yaml)
- **TAC Tree**: pmoves/configs/tac_trees/dgx-spark.tac.yaml (278 lines, 6 phases)

## Status
- ✅ Tailscale ACL rules configured
- ✅ Network inventory registered
- ✅ Makefile include added
- ✅ Ollama Spark provider configured
- ✅ PMOVES Spark preset created
- ⏳ Flare model namespace TODO
- ⏳ NATS JetStream streams (defined, not deployed)

Added: 2026-04-17
